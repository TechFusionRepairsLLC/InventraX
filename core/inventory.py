"""
inventory.py  —  InventraX Database Layer
==========================================
Provides full SQLite-backed persistence for inventory items and assets.

Schema
------
  items  : all inventory fields used by main_window.py
  assets : all asset fields including status and notes
  audit_log : append-only change history for every mutation

Public API (used by main_window.py)
-------------------------------------
  # ── Lifecycle ──
  init_db()                      → create / migrate tables
  get_db_path() → str

  # ── Inventory ──
  add_item(...)   → bool
  update_item(...)→ bool
  remove_item(name) → bool
  get_item(name)  → dict | None
  get_all_items() → list[dict]
  item_exists(name) → bool
  search_items(term) → list[dict]

  # ── Assets ──
  add_asset(...)    → bool
  update_asset(...) → bool
  remove_asset(asset_name, assigned_to) → bool
  get_all_assets()  → list[dict]
  search_assets(term) → list[dict]

  # ── Sync helpers (bridge to main_window in-memory dicts) ──
  load_inventory_to_memory(inventory_data: dict) → int
  save_inventory_from_memory(inventory_data: dict) → int
  load_assets_to_memory(asset_data: list) → int
  save_assets_from_memory(asset_data: list) → int

  # ── Reports / Stats ──
  get_low_stock_items(threshold) → list[dict]
  get_out_of_stock_items()       → list[dict]
  get_total_revenue()            → float
  get_category_summary()         → dict[str, int]
  get_popular_items(limit)       → list[dict]

  # ── Audit ──
  get_audit_log(limit) → list[dict]

  # ── Backup / Export ──
  export_to_excel(filepath) → bool
  import_from_excel(filepath) → tuple[int, list[str]]   (count, errors)
"""

import sqlite3
import logging
import os
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

# ── Optional pandas for Excel I/O ────────────────────────────────────────────
try:
    import pandas as _pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

from config.settings import DB_PATH

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_db_path() -> str:
    return DB_PATH


@contextmanager
def _connection():
    """Yield a sqlite3 connection with WAL mode and foreign keys enabled.
    Auto-commits on success, rolls back on any exception."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows accessible as dicts
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_item(row) -> dict:
    """Convert a sqlite3.Row (items table) → plain dict."""
    return {
        "name":         row["name"],
        "category":     row["category"]     or "",
        "quantity":     row["quantity"]      or 0,
        "location":     row["location"]     or "",
        "serial":       row["serial"]       or "",
        "warranty_date":row["warranty_date"] or "",
        "usage_count":  row["usage_count"]  or 0,
        "price":        row["price"]        or 0.0,
        "sku":          row["sku"]          or "",
        "sold_count":   row["sold_count"]   or 0,
        "sold_revenue": row["sold_revenue"] or 0.0,
        "notes":        row["notes"]        or "",
        "created_at":   row["created_at"]   or "",
        "updated_at":   row["updated_at"]   or "",
    }


def _row_to_asset(row) -> dict:
    """Convert a sqlite3.Row (assets table) → plain dict."""
    return {
        "asset":        row["asset_name"],
        "assigned_to":  row["assigned_to"]  or "",
        "location":     row["location"]     or "",
        "category":     row["category"]     or "",
        "status":       row["status"]       or "Active",
        "notes":        row["notes"]        or "",
        "serial":       row["serial"]       or "",
        "created_at":   row["created_at"]   or "",
        "updated_at":   row["updated_at"]   or "",
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# Schema — create & migrate
# ─────────────────────────────────────────────────────────────────────────────

_ITEMS_DDL = """
CREATE TABLE IF NOT EXISTS items (
    name          TEXT PRIMARY KEY NOT NULL,
    category      TEXT    DEFAULT '',
    quantity      INTEGER DEFAULT 0,
    location      TEXT    DEFAULT '',
    serial        TEXT    DEFAULT '',
    warranty_date TEXT    DEFAULT '',
    usage_count   INTEGER DEFAULT 0,
    price         REAL    DEFAULT 0.0,
    sku           TEXT    DEFAULT '',
    sold_count    INTEGER DEFAULT 0,
    sold_revenue  REAL    DEFAULT 0.0,
    notes         TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT '',
    updated_at    TEXT    DEFAULT ''
);
"""

_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS assets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name   TEXT    NOT NULL,
    assigned_to  TEXT    DEFAULT '',
    location     TEXT    DEFAULT '',
    category     TEXT    DEFAULT '',
    status       TEXT    DEFAULT 'Active',
    notes        TEXT    DEFAULT '',
    serial       TEXT    DEFAULT '',
    created_at   TEXT    DEFAULT '',
    updated_at   TEXT    DEFAULT '',
    UNIQUE(asset_name, assigned_to)
);
"""

_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    table_name TEXT NOT NULL,
    operation  TEXT NOT NULL,   -- INSERT / UPDATE / DELETE
    record_key TEXT NOT NULL,
    details    TEXT DEFAULT ''
);
"""

# Columns added after initial release — applied via ALTER TABLE if missing
_MIGRATIONS = {
    "items": [
        ("serial",        "TEXT    DEFAULT ''"),
        ("warranty_date", "TEXT    DEFAULT ''"),
        ("usage_count",   "INTEGER DEFAULT 0"),
        ("price",         "REAL    DEFAULT 0.0"),
        ("sku",           "TEXT    DEFAULT ''"),
        ("sold_count",    "INTEGER DEFAULT 0"),
        ("sold_revenue",  "REAL    DEFAULT 0.0"),
        ("notes",         "TEXT    DEFAULT ''"),
        ("created_at",    "TEXT    DEFAULT ''"),
        ("updated_at",    "TEXT    DEFAULT ''"),
    ],
    "assets": [
        ("status",     "TEXT DEFAULT 'Active'"),
        ("notes",      "TEXT DEFAULT ''"),
        ("serial",     "TEXT DEFAULT ''"),
        ("created_at", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT DEFAULT ''"),
    ],
}


def init_db() -> None:
    """Create tables if they don't exist; run any pending column migrations."""
    with _connection() as conn:
        conn.execute(_ITEMS_DDL)
        conn.execute(_ASSETS_DDL)
        conn.execute(_AUDIT_DDL)

        # Apply migrations for each table
        for table, columns in _MIGRATIONS.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for col_name, col_def in columns:
                if col_name not in existing:
                    try:
                        conn.execute(
                            f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}"
                        )
                        log.info("Migration: added column %s.%s", table, col_name)
                    except sqlite3.OperationalError as exc:
                        log.warning("Migration skipped (%s.%s): %s", table, col_name, exc)

    log.info("Database initialised at %s", DB_PATH)


def _audit(conn, table: str, operation: str, key: str, details: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (timestamp, table_name, operation, record_key, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (_now(), table, operation, key, details),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Inventory CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_item(
    name:          str,
    category:      str  = "",
    quantity:      int  = 0,
    location:      str  = "",
    serial:        str  = "",
    warranty_date: str  = "",
    usage_count:   int  = 1,
    price:         float = 0.0,
    sku:           str  = "",
    sold_count:    int  = 0,
    sold_revenue:  float = 0.0,
    notes:         str  = "",
) -> bool:
    """
    Insert a new item.  Returns True on success, False if name already exists
    or an error occurs.
    """
    if not name or not name.strip():
        log.warning("add_item: empty name rejected")
        return False
    now = _now()
    try:
        with _connection() as conn:
            conn.execute(
                """
                INSERT INTO items
                  (name, category, quantity, location, serial, warranty_date,
                   usage_count, price, sku, sold_count, sold_revenue, notes,
                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name.strip(), category, quantity, location, serial, warranty_date,
                 usage_count, price, sku, sold_count, sold_revenue, notes, now, now),
            )
            _audit(conn, "items", "INSERT", name, f"qty={quantity}, sku={sku}")
        log.info("add_item: '%s' added", name)
        return True
    except sqlite3.IntegrityError:
        log.warning("add_item: '%s' already exists — use update_item instead", name)
        return False
    except Exception as exc:
        log.error("add_item error: %s", exc)
        return False


def update_item(
    name:          str,
    category:      str   = None,
    quantity:      int   = None,
    location:      str   = None,
    serial:        str   = None,
    warranty_date: str   = None,
    usage_count:   int   = None,
    price:         float = None,
    sku:           str   = None,
    sold_count:    int   = None,
    sold_revenue:  float = None,
    notes:         str   = None,
) -> bool:
    """
    Update an existing item.  Only non-None keyword arguments are changed.
    Returns True on success, False if item not found or error.
    """
    if not name:
        return False

    fields, values = [], []

    for col, val in [
        ("category",      category),
        ("quantity",      quantity),
        ("location",      location),
        ("serial",        serial),
        ("warranty_date", warranty_date),
        ("usage_count",   usage_count),
        ("price",         price),
        ("sku",           sku),
        ("sold_count",    sold_count),
        ("sold_revenue",  sold_revenue),
        ("notes",         notes),
    ]:
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)

    if not fields:
        return True  # nothing to do

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(name)

    try:
        with _connection() as conn:
            cur = conn.execute(
                f"UPDATE items SET {', '.join(fields)} WHERE name = ?", values
            )
            if cur.rowcount == 0:
                log.warning("update_item: '%s' not found", name)
                return False
            _audit(conn, "items", "UPDATE", name,
                   ", ".join(f"{f.split(' =')[0]}={v}" for f, v in zip(fields[:-1], values[:-1])))
        log.info("update_item: '%s' updated", name)
        return True
    except Exception as exc:
        log.error("update_item error: %s", exc)
        return False


def upsert_item(
    name:          str,
    category:      str   = "",
    quantity:      int   = 0,
    location:      str   = "",
    serial:        str   = "",
    warranty_date: str   = "",
    usage_count:   int   = 1,
    price:         float = 0.0,
    sku:           str   = "",
    sold_count:    int   = 0,
    sold_revenue:  float = 0.0,
    notes:         str   = "",
) -> bool:
    """Add if new, update if existing.  Increments usage_count on update."""
    if item_exists(name):
        # Increment usage_count by 1 relative to current value
        existing = get_item(name)
        new_usage = (existing.get("usage_count", 0) + 1) if existing else usage_count
        return update_item(
            name=name, category=category, quantity=quantity,
            location=location, serial=serial, warranty_date=warranty_date,
            usage_count=new_usage, price=price, sku=sku,
            sold_count=sold_count, sold_revenue=sold_revenue, notes=notes,
        )
    else:
        return add_item(
            name=name, category=category, quantity=quantity,
            location=location, serial=serial, warranty_date=warranty_date,
            usage_count=usage_count, price=price, sku=sku,
            sold_count=sold_count, sold_revenue=sold_revenue, notes=notes,
        )


def remove_item(name: str) -> bool:
    """Delete an item by name. Returns True on success."""
    if not name:
        return False
    try:
        with _connection() as conn:
            cur = conn.execute("DELETE FROM items WHERE name = ?", (name,))
            if cur.rowcount == 0:
                return False
            _audit(conn, "items", "DELETE", name)
        log.info("remove_item: '%s' deleted", name)
        return True
    except Exception as exc:
        log.error("remove_item error: %s", exc)
        return False


def get_item(name: str) -> Optional[dict]:
    """Return a single item dict, or None if not found."""
    try:
        with _connection() as conn:
            row = conn.execute("SELECT * FROM items WHERE name = ?", (name,)).fetchone()
        return _row_to_item(row) if row else None
    except Exception as exc:
        log.error("get_item error: %s", exc)
        return None


def get_all_items() -> list:
    """Return all inventory items as a list of dicts, ordered by name."""
    try:
        with _connection() as conn:
            rows = conn.execute("SELECT * FROM items ORDER BY name COLLATE NOCASE").fetchall()
        return [_row_to_item(r) for r in rows]
    except Exception as exc:
        log.error("get_all_items error: %s", exc)
        return []


def item_exists(name: str) -> bool:
    try:
        with _connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM items WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
        return row is not None
    except Exception:
        return False


def search_items(term: str) -> list:
    """
    Case-insensitive search across name, category, location, sku, serial, notes.
    Returns list of matching item dicts.
    """
    if not term:
        return get_all_items()
    pattern = f"%{term.strip()}%"
    try:
        with _connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM items
                WHERE  name          LIKE ? COLLATE NOCASE
                    OR category      LIKE ? COLLATE NOCASE
                    OR location      LIKE ? COLLATE NOCASE
                    OR sku           LIKE ? COLLATE NOCASE
                    OR serial        LIKE ? COLLATE NOCASE
                    OR notes         LIKE ? COLLATE NOCASE
                ORDER BY name COLLATE NOCASE
                """,
                (pattern,) * 6,
            ).fetchall()
        return [_row_to_item(r) for r in rows]
    except Exception as exc:
        log.error("search_items error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Asset CRUD
# ─────────────────────────────────────────────────────────────────────────────

def add_asset(
    asset_name:  str,
    assigned_to: str  = "",
    location:    str  = "",
    category:    str  = "",
    status:      str  = "Active",
    notes:       str  = "",
    serial:      str  = "",
) -> bool:
    """Insert a new asset.  Returns True on success."""
    if not asset_name:
        return False
    now = _now()
    try:
        with _connection() as conn:
            conn.execute(
                """
                INSERT INTO assets
                  (asset_name, assigned_to, location, category, status, notes,
                   serial, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset_name, assigned_to, location, category or asset_name,
                 status, notes, serial, now, now),
            )
            _audit(conn, "assets", "INSERT", asset_name,
                   f"assigned_to={assigned_to}, status={status}")
        log.info("add_asset: '%s' added", asset_name)
        return True
    except sqlite3.IntegrityError:
        log.warning("add_asset: ('%s', '%s') already exists", asset_name, assigned_to)
        return False
    except Exception as exc:
        log.error("add_asset error: %s", exc)
        return False


def update_asset(
    asset_id:    int,
    asset_name:  str  = None,
    assigned_to: str  = None,
    location:    str  = None,
    category:    str  = None,
    status:      str  = None,
    notes:       str  = None,
    serial:      str  = None,
) -> bool:
    """Update an asset by its row ID.  Only non-None fields are changed."""
    fields, values = [], []
    for col, val in [
        ("asset_name",  asset_name),
        ("assigned_to", assigned_to),
        ("location",    location),
        ("category",    category),
        ("status",      status),
        ("notes",       notes),
        ("serial",      serial),
    ]:
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)

    if not fields:
        return True

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(asset_id)

    try:
        with _connection() as conn:
            cur = conn.execute(
                f"UPDATE assets SET {', '.join(fields)} WHERE id = ?", values
            )
            if cur.rowcount == 0:
                return False
            _audit(conn, "assets", "UPDATE", str(asset_id))
        return True
    except Exception as exc:
        log.error("update_asset error: %s", exc)
        return False


def remove_asset_by_id(asset_id: int) -> bool:
    """Delete an asset row by its integer ID."""
    try:
        with _connection() as conn:
            cur = conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            if cur.rowcount == 0:
                return False
            _audit(conn, "assets", "DELETE", str(asset_id))
        return True
    except Exception as exc:
        log.error("remove_asset error: %s", exc)
        return False


def remove_asset(asset_name: str, assigned_to: str = "") -> bool:
    """Delete an asset by name (and optionally assigned_to)."""
    try:
        with _connection() as conn:
            if assigned_to:
                cur = conn.execute(
                    "DELETE FROM assets WHERE asset_name = ? AND assigned_to = ?",
                    (asset_name, assigned_to),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM assets WHERE asset_name = ?", (asset_name,)
                )
            if cur.rowcount == 0:
                return False
            _audit(conn, "assets", "DELETE", asset_name)
        return True
    except Exception as exc:
        log.error("remove_asset error: %s", exc)
        return False


def get_all_assets() -> list:
    """Return all assets ordered by asset_name."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assets ORDER BY asset_name COLLATE NOCASE, assigned_to"
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("get_all_assets error: %s", exc)
        return []


def search_assets(term: str) -> list:
    if not term:
        return get_all_assets()
    pattern = f"%{term.strip()}%"
    try:
        with _connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM assets
                WHERE  asset_name   LIKE ? COLLATE NOCASE
                    OR assigned_to  LIKE ? COLLATE NOCASE
                    OR location     LIKE ? COLLATE NOCASE
                    OR status       LIKE ? COLLATE NOCASE
                    OR notes        LIKE ? COLLATE NOCASE
                ORDER BY asset_name COLLATE NOCASE
                """,
                (pattern,) * 5,
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("search_assets error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Sync helpers  (bridge between SQLite and main_window in-memory dicts)
# ─────────────────────────────────────────────────────────────────────────────

def load_inventory_to_memory(inventory_dict: dict) -> int:
    """
    Pull all items from SQLite into the in-memory inventory_data dict used by
    main_window.py.  Clears and repopulates the dict in-place.
    Returns the number of items loaded.

    Usage in main_window.__init__:
        from core.inventory import init_db, load_inventory_to_memory
        init_db()
        load_inventory_to_memory(inventory_data)
    """
    items = get_all_items()
    inventory_dict.clear()
    for item in items:
        name = item.pop("name")
        inventory_dict[name] = item
    return len(items)


def save_inventory_from_memory(inventory_dict: dict) -> int:
    """
    Push the entire in-memory inventory_data dict into SQLite using upsert.
    Returns the number of items written.

    Usage in main_window before app exit or on explicit save:
        from core.inventory import save_inventory_from_memory
        save_inventory_from_memory(inventory_data)
    """
    count = 0
    for name, d in inventory_dict.items():
        ok = upsert_item(
            name          = name,
            category      = d.get("category",      ""),
            quantity      = d.get("quantity",       0),
            location      = d.get("location",       ""),
            serial        = d.get("serial",         ""),
            warranty_date = d.get("warranty_date",  ""),
            usage_count   = d.get("usage_count",    1),
            price         = d.get("price",          0.0),
            sku           = d.get("sku",            ""),
            sold_count    = d.get("sold_count",     0),
            sold_revenue  = d.get("sold_revenue",   0.0),
            notes         = d.get("notes",          ""),
        )
        if ok:
            count += 1
    log.info("save_inventory_from_memory: %d items written", count)
    return count


def load_assets_to_memory(asset_list: list) -> int:
    """
    Pull all assets from SQLite into the in-memory asset_data list used by
    main_window.py.  Clears and repopulates the list in-place.
    Returns the number of assets loaded.
    """
    assets = get_all_assets()
    asset_list.clear()
    asset_list.extend(assets)
    return len(assets)


def save_assets_from_memory(asset_list: list) -> int:
    """
    Push the entire in-memory asset_data list into SQLite.
    Existing rows with the same (asset_name, assigned_to) are updated;
    new ones are inserted.
    Returns the number of assets written.
    """
    count = 0
    for entry in asset_list:
        name        = entry.get("asset", "")
        assigned_to = entry.get("assigned_to", "")
        if not name:
            continue
        try:
            with _connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM assets WHERE asset_name = ? AND assigned_to = ?",
                    (name, assigned_to),
                ).fetchone()
                now = _now()
                if existing:
                    conn.execute(
                        """
                        UPDATE assets SET location=?, category=?, status=?,
                            notes=?, serial=?, updated_at=?
                        WHERE id=?
                        """,
                        (entry.get("location", ""),
                         entry.get("category", name),
                         entry.get("status", "Active"),
                         entry.get("notes", ""),
                         entry.get("serial", ""),
                         now,
                         existing["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO assets
                          (asset_name, assigned_to, location, category, status,
                           notes, serial, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (name, assigned_to,
                         entry.get("location", ""),
                         entry.get("category", name),
                         entry.get("status", "Active"),
                         entry.get("notes", ""),
                         entry.get("serial", ""),
                         now, now),
                    )
            count += 1
        except Exception as exc:
            log.error("save_assets_from_memory error for '%s': %s", name, exc)
    log.info("save_assets_from_memory: %d assets written", count)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Reports / Stats
# ─────────────────────────────────────────────────────────────────────────────

def get_low_stock_items(threshold: int = 5) -> list:
    """Return items with 0 < quantity <= threshold."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM items WHERE quantity > 0 AND quantity <= ? "
                "ORDER BY quantity ASC",
                (threshold,),
            ).fetchall()
        return [_row_to_item(r) for r in rows]
    except Exception as exc:
        log.error("get_low_stock_items error: %s", exc)
        return []


def get_out_of_stock_items() -> list:
    """Return items with quantity == 0."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM items WHERE quantity = 0 ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [_row_to_item(r) for r in rows]
    except Exception as exc:
        log.error("get_out_of_stock_items error: %s", exc)
        return []


def get_total_revenue() -> float:
    """Sum of sold_revenue across all items."""
    try:
        with _connection() as conn:
            row = conn.execute("SELECT COALESCE(SUM(sold_revenue), 0) FROM items").fetchone()
        return float(row[0]) if row else 0.0
    except Exception as exc:
        log.error("get_total_revenue error: %s", exc)
        return 0.0


def get_category_summary() -> dict:
    """Return {category: total_quantity} dict for chart generation."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT category, SUM(quantity) as total FROM items "
                "GROUP BY category ORDER BY category COLLATE NOCASE"
            ).fetchall()
        return {r["category"]: r["total"] for r in rows}
    except Exception as exc:
        log.error("get_category_summary error: %s", exc)
        return {}


def get_popular_items(limit: int = 5) -> list:
    """Return the top N items by usage_count."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM items ORDER BY usage_count DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_item(r) for r in rows]
    except Exception as exc:
        log.error("get_popular_items error: %s", exc)
        return []


def get_inventory_stats() -> dict:
    """Return a summary dict for the dashboard stat cards."""
    try:
        with _connection() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
            oos       = conn.execute("SELECT COUNT(*) FROM items WHERE quantity=0").fetchone()[0]
            low       = conn.execute(
                "SELECT COUNT(*) FROM items WHERE quantity>0 AND quantity<=5"
            ).fetchone()[0]
            revenue   = conn.execute(
                "SELECT COALESCE(SUM(sold_revenue),0) FROM items"
            ).fetchone()[0]
        return {
            "total_items":     total,
            "out_of_stock":    oos,
            "low_stock":       low,
            "total_revenue":   float(revenue),
        }
    except Exception as exc:
        log.error("get_inventory_stats error: %s", exc)
        return {"total_items": 0, "out_of_stock": 0, "low_stock": 0, "total_revenue": 0.0}


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

def get_audit_log(limit: int = 200) -> list:
    """Return the most recent audit entries as a list of dicts."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.error("get_audit_log error: %s", exc)
        return []


def clear_audit_log() -> bool:
    """Wipe the entire audit log (e.g. after export)."""
    try:
        with _connection() as conn:
            conn.execute("DELETE FROM audit_log")
        return True
    except Exception as exc:
        log.error("clear_audit_log error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Excel Import / Export
# ─────────────────────────────────────────────────────────────────────────────

def export_to_excel(filepath: str) -> bool:
    """
    Export the full inventory and assets to an Excel workbook with two sheets.
    Requires pandas + openpyxl.  Returns True on success.
    """
    if not _PANDAS_AVAILABLE:
        log.error("export_to_excel: pandas not installed")
        return False
    try:
        items  = get_all_items()
        assets = get_all_assets()

        df_items = _pd.DataFrame(items) if items else _pd.DataFrame(
            columns=["name","category","quantity","location","serial",
                     "warranty_date","usage_count","price","sku",
                     "sold_count","sold_revenue","notes"])
        df_assets = _pd.DataFrame(assets) if assets else _pd.DataFrame(
            columns=["asset","assigned_to","location","category","status","notes","serial"])

        # Friendly column names for the spreadsheet
        df_items.rename(columns={
            "name": "Item Name", "category": "Category", "quantity": "Quantity",
            "location": "Location", "serial": "Serial", "warranty_date": "Warranty Date",
            "usage_count": "Usage Count", "price": "Price", "sku": "SKU",
            "sold_count": "Sold Count", "sold_revenue": "Sold Revenue", "notes": "Notes",
        }, inplace=True)
        df_assets.rename(columns={
            "asset": "Asset Name", "assigned_to": "Assigned To",
            "location": "Location", "category": "Category",
            "status": "Status", "notes": "Notes", "serial": "Serial",
        }, inplace=True)

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with _pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df_items.to_excel(writer, sheet_name="Inventory", index=False)
            df_assets.to_excel(writer, sheet_name="Assets", index=False)

        log.info("export_to_excel: written to %s", filepath)
        return True
    except Exception as exc:
        log.error("export_to_excel error: %s", exc)
        return False


def import_from_excel(filepath: str) -> tuple:
    """
    Import inventory items from an Excel file (Inventory sheet expected).
    Returns (count_imported, list_of_error_strings).
    """
    if not _PANDAS_AVAILABLE:
        return 0, ["pandas not installed — cannot import Excel files."]

    errors, count = [], 0
    try:
        df = _pd.read_excel(filepath, sheet_name=0)   # first sheet
    except Exception as exc:
        return 0, [f"Could not open file: {exc}"]

    for idx, row in df.iterrows():
        try:
            name = str(row.get("Item Name", row.get("name", ""))).strip()
            if not name or name.lower() == "nan":
                errors.append(f"Row {idx+2}: missing item name — skipped")
                continue
            ok = upsert_item(
                name          = name,
                category      = str(row.get("Category",      row.get("category",      ""))),
                quantity      = int(row.get("Quantity",      row.get("quantity",      0))),
                location      = str(row.get("Location",      row.get("location",      ""))),
                serial        = str(row.get("Serial",        row.get("serial",        ""))),
                warranty_date = str(row.get("Warranty Date", row.get("warranty_date", ""))),
                usage_count   = int(row.get("Usage Count",   row.get("usage_count",   0))),
                price         = float(row.get("Price",       row.get("price",         0.0))),
                sku           = str(row.get("SKU",           row.get("sku",           ""))),
                sold_count    = int(row.get("Sold Count",    row.get("sold_count",    0))),
                sold_revenue  = float(row.get("Sold Revenue",row.get("sold_revenue",  0.0))),
                notes         = str(row.get("Notes",         row.get("notes",         ""))),
            )
            if ok:
                count += 1
            else:
                errors.append(f"Row {idx+2}: upsert failed for '{name}'")
        except Exception as exc:
            errors.append(f"Row {idx+2}: {exc}")

    log.info("import_from_excel: %d items imported, %d errors", count, len(errors))
    return count, errors