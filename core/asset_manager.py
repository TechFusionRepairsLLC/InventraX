"""
asset_manager.py  —  InventraX Asset Management Layer
======================================================
Full SQLite-backed persistence for asset assignments, history,
maintenance records, and department tracking.

Complements inventory.py — both share the same DB_PATH and the
same _connection() / audit_log infrastructure.

Schema (tables owned by this module)
--------------------------------------
  assets          — current assignment state  (shared with inventory.py)
  asset_history   — every assignment / return / transfer event
  asset_maintenance — maintenance and repair records per asset
  departments     — department reference list

Public API
----------
  # ── Lifecycle ──
  init_asset_tables()

  # ── Assignment ──
  assign_asset(asset_name, assigned_to, department, location,
               assigned_date, item_id, category, status, notes, serial) → bool
  return_asset(asset_name, assigned_to, return_date, return_notes) → bool
  transfer_asset(asset_name, from_user, to_user, to_department,
                 to_location, transfer_date, notes) → bool
  update_asset_status(asset_name, assigned_to, status) → bool

  # ── Query ──
  get_asset(asset_name, assigned_to) → dict | None
  get_all_assets() → list[dict]
  get_assets_by_department(department) → list[dict]
  get_assets_by_status(status) → list[dict]
  get_assets_by_user(assigned_to) → list[dict]
  search_assets(term) → list[dict]
  asset_exists(asset_name, assigned_to) → bool

  # ── History ──
  get_asset_history(asset_name) → list[dict]
  get_recent_activity(limit)    → list[dict]

  # ── Maintenance ──
  log_maintenance(asset_name, maintenance_type, description,
                  performed_by, cost, date, next_due) → bool
  get_maintenance_log(asset_name) → list[dict]
  get_upcoming_maintenance(days_ahead) → list[dict]

  # ── Departments ──
  add_department(name, manager, location) → bool
  get_all_departments() → list[dict]
  remove_department(name) → bool

  # ── Sync helpers (bridge to main_window asset_data list) ──
  load_assets_to_memory(asset_list)          → int
  save_assets_from_memory(asset_list)        → int

  # ── Reports ──
  get_asset_stats()                          → dict
  get_department_asset_summary()             → list[dict]

  # ── Export ──
  export_assets_to_excel(filepath)           → bool
"""

import sqlite3
import logging
import os
from datetime import datetime, date, timedelta
from contextlib import contextmanager
from typing import Optional

try:
    import pandas as _pd
    _PANDAS_AVAILABLE = True
except ImportError:
    _PANDAS_AVAILABLE = False

from config.settings import DB_PATH

log = logging.getLogger(__name__)

# Valid status values — enforced in Python so the UI combo and DB stay in sync
ASSET_STATUSES = ["Active", "In Repair", "Retired", "Lost", "Available", "Reserved", "Disposed"]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers  (mirrors inventory.py style for consistency)
# ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def _connection():
    """
    Yield a WAL-mode sqlite3 connection with foreign keys enabled.
    Auto-commits on success, rolls back on any exception.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return date.today().strftime("%Y-%m-%d")


def _audit(conn, table: str, operation: str, key: str, details: str = "") -> None:
    """Append a row to the shared audit_log table (created by inventory.init_db)."""
    try:
        conn.execute(
            "INSERT INTO audit_log (timestamp, table_name, operation, record_key, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (_now(), table, operation, key, details),
        )
    except sqlite3.OperationalError:
        # audit_log may not exist if inventory.init_db hasn't run yet — non-fatal
        log.debug("audit_log table not found — skipping audit entry")


def _row_to_asset(row) -> dict:
    d = dict(row)
    return {
        "id":           d.get("id",           0),
        "asset":        d.get("asset_name",   ""),
        "item_id":      d.get("item_id",      ""),
        "assigned_to":  d.get("assigned_to",  ""),
        "department":   d.get("department",   ""),
        "location":     d.get("location",     ""),
        "category":     d.get("category",     ""),
        "status":       d.get("status",       "Active"),
        "notes":        d.get("notes",        ""),
        "serial":       d.get("serial",       ""),
        "assigned_date":d.get("assigned_date",""),
        "return_date":  d.get("return_date",  ""),
        "created_at":   d.get("created_at",   ""),
        "updated_at":   d.get("updated_at",   ""),
    }


def _row_to_history(row) -> dict:
    d = dict(row)
    return {
        "id":           d.get("id",           0),
        "asset_name":   d.get("asset_name",   ""),
        "event_type":   d.get("event_type",   ""),
        "from_user":    d.get("from_user",    ""),
        "to_user":      d.get("to_user",      ""),
        "department":   d.get("department",   ""),
        "location":     d.get("location",     ""),
        "event_date":   d.get("event_date",   ""),
        "notes":        d.get("notes",        ""),
        "recorded_at":  d.get("recorded_at",  ""),
    }


def _row_to_maintenance(row) -> dict:
    d = dict(row)
    return {
        "id":               d.get("id",               0),
        "asset_name":       d.get("asset_name",       ""),
        "maintenance_type": d.get("maintenance_type", ""),
        "description":      d.get("description",      ""),
        "performed_by":     d.get("performed_by",     ""),
        "cost":             d.get("cost",             0.0),
        "maintenance_date": d.get("maintenance_date", ""),
        "next_due_date":    d.get("next_due_date",    ""),
        "recorded_at":      d.get("recorded_at",      ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Schema DDL
# ─────────────────────────────────────────────────────────────────────────────

_ASSETS_DDL = """
CREATE TABLE IF NOT EXISTS assets (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name    TEXT    NOT NULL,
    item_id       TEXT    DEFAULT '',
    assigned_to   TEXT    DEFAULT '',
    department    TEXT    DEFAULT '',
    location      TEXT    DEFAULT '',
    category      TEXT    DEFAULT '',
    status        TEXT    DEFAULT 'Active',
    notes         TEXT    DEFAULT '',
    serial        TEXT    DEFAULT '',
    assigned_date TEXT    DEFAULT '',
    return_date   TEXT    DEFAULT '',
    created_at    TEXT    DEFAULT '',
    updated_at    TEXT    DEFAULT '',
    UNIQUE(asset_name, assigned_to)
);
"""

_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS asset_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name  TEXT NOT NULL,
    event_type  TEXT NOT NULL,   -- ASSIGNED / RETURNED / TRANSFERRED / STATUS_CHANGE
    from_user   TEXT DEFAULT '',
    to_user     TEXT DEFAULT '',
    department  TEXT DEFAULT '',
    location    TEXT DEFAULT '',
    event_date  TEXT DEFAULT '',
    notes       TEXT DEFAULT '',
    recorded_at TEXT DEFAULT ''
);
"""

_MAINTENANCE_DDL = """
CREATE TABLE IF NOT EXISTS asset_maintenance (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name       TEXT NOT NULL,
    maintenance_type TEXT DEFAULT '',   -- Repair / Inspection / Upgrade / Cleaning / Other
    description      TEXT DEFAULT '',
    performed_by     TEXT DEFAULT '',
    cost             REAL DEFAULT 0.0,
    maintenance_date TEXT DEFAULT '',
    next_due_date    TEXT DEFAULT '',
    recorded_at      TEXT DEFAULT ''
);
"""

_DEPARTMENTS_DDL = """
CREATE TABLE IF NOT EXISTS departments (
    name      TEXT PRIMARY KEY NOT NULL,
    manager   TEXT DEFAULT '',
    location  TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
"""

# Columns added post-initial-release — applied safely via ALTER TABLE
_ASSET_MIGRATIONS = [
    ("item_id",       "TEXT DEFAULT ''"),
    ("department",    "TEXT DEFAULT ''"),
    ("assigned_date", "TEXT DEFAULT ''"),
    ("return_date",   "TEXT DEFAULT ''"),
    ("serial",        "TEXT DEFAULT ''"),
    ("notes",         "TEXT DEFAULT ''"),
    ("status",        "TEXT DEFAULT 'Active'"),
    ("created_at",    "TEXT DEFAULT ''"),
    ("updated_at",    "TEXT DEFAULT ''"),
]


def init_asset_tables() -> None:
    """
    Create all asset-related tables if they don't exist.
    Run column migrations for the assets table.
    Safe to call multiple times (idempotent).
    """
    with _connection() as conn:
        conn.execute(_ASSETS_DDL)
        conn.execute(_HISTORY_DDL)
        conn.execute(_MAINTENANCE_DDL)
        conn.execute(_DEPARTMENTS_DDL)

        # Migrate assets table — add any columns that are missing
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(assets)")}
        for col_name, col_def in _ASSET_MIGRATIONS:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE assets ADD COLUMN {col_name} {col_def}")
                    log.info("Migration: added assets.%s", col_name)
                except sqlite3.OperationalError as exc:
                    log.warning("Migration skipped (assets.%s): %s", col_name, exc)

    log.info("Asset tables initialised at %s", DB_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Assignment  (create / update / return / transfer)
# ─────────────────────────────────────────────────────────────────────────────

def assign_asset(
    asset_name:    str,
    assigned_to:   str   = "",
    department:    str   = "",
    location:      str   = "",
    assigned_date: str   = "",
    item_id:       str   = "",
    category:      str   = "",
    status:        str   = "Active",
    notes:         str   = "",
    serial:        str   = "",
) -> bool:
    """
    Assign an asset to a person / department.

    If the (asset_name, assigned_to) pair already exists, the record is
    updated instead of raising a duplicate error.

    Parameters
    ----------
    asset_name    : human-readable asset identifier  (e.g. "MacBook Pro #3")
    assigned_to   : person receiving the asset
    department    : department name (optional but recommended)
    location      : physical location
    assigned_date : ISO date string  e.g. "2024-06-01" — defaults to today
    item_id       : link to inventory items.name if asset came from stock
    category      : free-form category tag
    status        : one of ASSET_STATUSES
    notes         : free-form notes
    serial        : serial / asset tag number

    Returns True on success, False on error.
    """
    if not asset_name or not asset_name.strip():
        log.warning("assign_asset: empty asset_name rejected")
        return False

    if status not in ASSET_STATUSES:
        log.warning("assign_asset: unknown status '%s', defaulting to Active", status)
        status = "Active"

    asset_name    = asset_name.strip()
    assigned_date = assigned_date or _today()
    now           = _now()

    try:
        with _connection() as conn:
            existing = conn.execute(
                "SELECT id FROM assets WHERE asset_name=? AND assigned_to=?",
                (asset_name, assigned_to),
            ).fetchone()

            if existing:
                # Update the existing record
                conn.execute(
                    """
                    UPDATE assets
                    SET department=?, location=?, category=?, status=?,
                        notes=?, serial=?, item_id=?, assigned_date=?,
                        return_date='', updated_at=?
                    WHERE asset_name=? AND assigned_to=?
                    """,
                    (department, location, category or asset_name, status,
                     notes, serial, item_id, assigned_date, now,
                     asset_name, assigned_to),
                )
                log.info("assign_asset: updated existing record for '%s' → '%s'",
                         asset_name, assigned_to)
            else:
                conn.execute(
                    """
                    INSERT INTO assets
                      (asset_name, item_id, assigned_to, department, location,
                       category, status, notes, serial, assigned_date,
                       created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (asset_name, item_id, assigned_to, department, location,
                     category or asset_name, status, notes, serial,
                     assigned_date, now, now),
                )
                log.info("assign_asset: '%s' assigned to '%s'", asset_name, assigned_to)

            # Record history event
            _record_history(conn, asset_name,
                            event_type  = "ASSIGNED",
                            to_user     = assigned_to,
                            department  = department,
                            location    = location,
                            event_date  = assigned_date,
                            notes       = notes)

            _audit(conn, "assets", "ASSIGN", asset_name,
                   f"to={assigned_to}, dept={department}, status={status}")
        return True

    except Exception as exc:
        log.error("assign_asset error for '%s': %s", asset_name, exc)
        return False


def return_asset(
    asset_name:   str,
    assigned_to:  str  = "",
    return_date:  str  = "",
    return_notes: str  = "",
) -> bool:
    """
    Mark an asset as returned.  Sets status → 'Available' and records the
    return date.  Appends a RETURNED event to asset_history.

    Returns True on success, False if the asset was not found or an error occurs.
    """
    if not asset_name:
        return False

    return_date = return_date or _today()
    now = _now()

    try:
        with _connection() as conn:
            cur = conn.execute(
                """
                UPDATE assets
                SET status='Available', return_date=?, updated_at=?,
                    notes = CASE WHEN ? != '' THEN ? ELSE notes END
                WHERE asset_name=? AND assigned_to=?
                """,
                (return_date, now, return_notes, return_notes, asset_name, assigned_to),
            )
            if cur.rowcount == 0:
                # Try without assigned_to filter
                cur2 = conn.execute(
                    """
                    UPDATE assets SET status='Available', return_date=?, updated_at=?
                    WHERE asset_name=?
                    """,
                    (return_date, now, asset_name),
                )
                if cur2.rowcount == 0:
                    log.warning("return_asset: '%s' not found", asset_name)
                    return False

            _record_history(conn, asset_name,
                            event_type = "RETURNED",
                            from_user  = assigned_to,
                            event_date = return_date,
                            notes      = return_notes)
            _audit(conn, "assets", "RETURN", asset_name,
                   f"from={assigned_to}, date={return_date}")

        log.info("return_asset: '%s' returned from '%s'", asset_name, assigned_to)
        return True

    except Exception as exc:
        log.error("return_asset error: %s", exc)
        return False


def transfer_asset(
    asset_name:     str,
    from_user:      str  = "",
    to_user:        str  = "",
    to_department:  str  = "",
    to_location:    str  = "",
    transfer_date:  str  = "",
    notes:          str  = "",
) -> bool:
    """
    Transfer an asset from one person/department to another.
    Updates the current assignment record and appends a TRANSFERRED history event.
    Returns True on success.
    """
    if not asset_name:
        return False

    transfer_date = transfer_date or _today()
    now = _now()

    try:
        with _connection() as conn:
            cur = conn.execute(
                """
                UPDATE assets
                SET assigned_to=?, department=?, location=?,
                    assigned_date=?, return_date='', updated_at=?,
                    status='Active'
                WHERE asset_name=? AND assigned_to=?
                """,
                (to_user, to_department, to_location,
                 transfer_date, now, asset_name, from_user),
            )
            if cur.rowcount == 0:
                # Fall back: update by asset_name alone
                conn.execute(
                    """
                    UPDATE assets
                    SET assigned_to=?, department=?, location=?,
                        assigned_date=?, return_date='', updated_at=?, status='Active'
                    WHERE asset_name=?
                    """,
                    (to_user, to_department, to_location, transfer_date, now, asset_name),
                )

            _record_history(conn, asset_name,
                            event_type = "TRANSFERRED",
                            from_user  = from_user,
                            to_user    = to_user,
                            department = to_department,
                            location   = to_location,
                            event_date = transfer_date,
                            notes      = notes)
            _audit(conn, "assets", "TRANSFER", asset_name,
                   f"from={from_user} to={to_user}, dept={to_department}")

        log.info("transfer_asset: '%s' from '%s' to '%s'", asset_name, from_user, to_user)
        return True

    except Exception as exc:
        log.error("transfer_asset error: %s", exc)
        return False


def update_asset_status(
    asset_name:  str,
    assigned_to: str = "",
    status:      str = "Active",
    notes:       str = "",
) -> bool:
    """
    Change the status of an asset (e.g. Active → In Repair → Active).
    Appends a STATUS_CHANGE history event.
    Returns True on success.
    """
    if status not in ASSET_STATUSES:
        log.warning("update_asset_status: unknown status '%s'", status)
        return False

    now = _now()
    try:
        with _connection() as conn:
            if assigned_to:
                cur = conn.execute(
                    "UPDATE assets SET status=?, updated_at=? "
                    "WHERE asset_name=? AND assigned_to=?",
                    (status, now, asset_name, assigned_to),
                )
            else:
                cur = conn.execute(
                    "UPDATE assets SET status=?, updated_at=? WHERE asset_name=?",
                    (status, now, asset_name),
                )
            if cur.rowcount == 0:
                log.warning("update_asset_status: '%s' not found", asset_name)
                return False

            _record_history(conn, asset_name,
                            event_type = "STATUS_CHANGE",
                            from_user  = assigned_to,
                            event_date = _today(),
                            notes      = f"Status → {status}. {notes}".strip())
            _audit(conn, "assets", "STATUS_CHANGE", asset_name,
                   f"status={status}")

        log.info("update_asset_status: '%s' → %s", asset_name, status)
        return True

    except Exception as exc:
        log.error("update_asset_status error: %s", exc)
        return False


def update_asset(
    asset_name:    str,
    assigned_to:   str   = None,
    department:    str   = None,
    location:      str   = None,
    category:      str   = None,
    status:        str   = None,
    notes:         str   = None,
    serial:        str   = None,
    item_id:       str   = None,
    assigned_date: str   = None,
) -> bool:
    """
    Generic field-level update for an asset.
    Only non-None keyword arguments are written.
    Matches on asset_name (and optionally assigned_to if provided in the WHERE).
    Returns True on success.
    """
    fields, values = [], []
    for col, val in [
        ("assigned_to",   assigned_to),
        ("department",    department),
        ("location",      location),
        ("category",      category),
        ("status",        status),
        ("notes",         notes),
        ("serial",        serial),
        ("item_id",       item_id),
        ("assigned_date", assigned_date),
    ]:
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val)

    if not fields:
        return True

    fields.append("updated_at = ?")
    values.append(_now())
    values.append(asset_name)

    try:
        with _connection() as conn:
            cur = conn.execute(
                f"UPDATE assets SET {', '.join(fields)} WHERE asset_name = ?",
                values,
            )
            if cur.rowcount == 0:
                log.warning("update_asset: '%s' not found", asset_name)
                return False
            _audit(conn, "assets", "UPDATE", asset_name)
        return True
    except Exception as exc:
        log.error("update_asset error: %s", exc)
        return False


def remove_asset(asset_name: str, assigned_to: str = "") -> bool:
    """
    Delete an asset record.  If assigned_to is given, only that specific
    assignment is deleted; otherwise all records with that asset_name are removed.
    Returns True on success.
    """
    if not asset_name:
        return False
    try:
        with _connection() as conn:
            if assigned_to:
                cur = conn.execute(
                    "DELETE FROM assets WHERE asset_name=? AND assigned_to=?",
                    (asset_name, assigned_to),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM assets WHERE asset_name=?", (asset_name,)
                )
            if cur.rowcount == 0:
                return False
            _audit(conn, "assets", "DELETE", asset_name,
                   f"assigned_to={assigned_to}")
        log.info("remove_asset: '%s' deleted", asset_name)
        return True
    except Exception as exc:
        log.error("remove_asset error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Query
# ─────────────────────────────────────────────────────────────────────────────

def get_asset(asset_name: str, assigned_to: str = "") -> Optional[dict]:
    """Return a single asset dict or None."""
    try:
        with _connection() as conn:
            if assigned_to:
                row = conn.execute(
                    "SELECT * FROM assets WHERE asset_name=? AND assigned_to=?",
                    (asset_name, assigned_to),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM assets WHERE asset_name=? LIMIT 1",
                    (asset_name,),
                ).fetchone()
        return _row_to_asset(row) if row else None
    except Exception as exc:
        log.error("get_asset error: %s", exc)
        return None


def get_all_assets() -> list:
    """Return all asset records ordered by asset_name."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assets ORDER BY asset_name COLLATE NOCASE, assigned_to"
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("get_all_assets error: %s", exc)
        return []


def get_assets_by_department(department: str) -> list:
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assets WHERE department=? COLLATE NOCASE "
                "ORDER BY asset_name COLLATE NOCASE",
                (department,),
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("get_assets_by_department error: %s", exc)
        return []


def get_assets_by_status(status: str) -> list:
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assets WHERE status=? ORDER BY asset_name COLLATE NOCASE",
                (status,),
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("get_assets_by_status error: %s", exc)
        return []


def get_assets_by_user(assigned_to: str) -> list:
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM assets WHERE assigned_to=? COLLATE NOCASE "
                "ORDER BY asset_name COLLATE NOCASE",
                (assigned_to,),
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("get_assets_by_user error: %s", exc)
        return []


def search_assets(term: str) -> list:
    """Case-insensitive search across asset_name, assigned_to, department,
    location, serial, notes, status."""
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
                    OR department   LIKE ? COLLATE NOCASE
                    OR location     LIKE ? COLLATE NOCASE
                    OR serial       LIKE ? COLLATE NOCASE
                    OR notes        LIKE ? COLLATE NOCASE
                    OR status       LIKE ? COLLATE NOCASE
                ORDER BY asset_name COLLATE NOCASE
                """,
                (pattern,) * 7,
            ).fetchall()
        return [_row_to_asset(r) for r in rows]
    except Exception as exc:
        log.error("search_assets error: %s", exc)
        return []


def asset_exists(asset_name: str, assigned_to: str = "") -> bool:
    try:
        with _connection() as conn:
            if assigned_to:
                row = conn.execute(
                    "SELECT 1 FROM assets WHERE asset_name=? AND assigned_to=? LIMIT 1",
                    (asset_name, assigned_to),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT 1 FROM assets WHERE asset_name=? LIMIT 1",
                    (asset_name,),
                ).fetchone()
        return row is not None
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────────────────

def _record_history(
    conn,
    asset_name: str,
    event_type: str,
    from_user:  str = "",
    to_user:    str = "",
    department: str = "",
    location:   str = "",
    event_date: str = "",
    notes:      str = "",
) -> None:
    """Internal — insert a row into asset_history within an open connection."""
    conn.execute(
        """
        INSERT INTO asset_history
          (asset_name, event_type, from_user, to_user, department,
           location, event_date, notes, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (asset_name, event_type, from_user, to_user, department,
         location, event_date or _today(), notes, _now()),
    )


def get_asset_history(asset_name: str) -> list:
    """Return all history events for a given asset, newest first."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_history WHERE asset_name=? "
                "ORDER BY id DESC",
                (asset_name,),
            ).fetchall()
        return [_row_to_history(r) for r in rows]
    except Exception as exc:
        log.error("get_asset_history error: %s", exc)
        return []


def get_recent_activity(limit: int = 50) -> list:
    """Return the most recent asset events across all assets."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_history(r) for r in rows]
    except Exception as exc:
        log.error("get_recent_activity error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Maintenance
# ─────────────────────────────────────────────────────────────────────────────

MAINTENANCE_TYPES = ["Repair", "Inspection", "Upgrade", "Cleaning", "Calibration", "Other"]


def log_maintenance(
    asset_name:        str,
    maintenance_type:  str   = "Other",
    description:       str   = "",
    performed_by:      str   = "",
    cost:              float = 0.0,
    maintenance_date:  str   = "",
    next_due_date:     str   = "",
) -> bool:
    """
    Record a maintenance or repair event for an asset.

    Parameters
    ----------
    asset_name       : the asset this applies to
    maintenance_type : one of MAINTENANCE_TYPES
    description      : what was done
    performed_by     : technician / vendor name
    cost             : cost of the work
    maintenance_date : ISO date string — defaults to today
    next_due_date    : ISO date string for next scheduled maintenance

    Returns True on success.
    """
    if not asset_name:
        return False

    maintenance_date = maintenance_date or _today()

    try:
        with _connection() as conn:
            conn.execute(
                """
                INSERT INTO asset_maintenance
                  (asset_name, maintenance_type, description, performed_by,
                   cost, maintenance_date, next_due_date, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (asset_name, maintenance_type, description, performed_by,
                 cost, maintenance_date, next_due_date, _now()),
            )
            # If sent to repair, auto-update the asset status
            if maintenance_type == "Repair":
                conn.execute(
                    "UPDATE assets SET status='In Repair', updated_at=? "
                    "WHERE asset_name=?",
                    (_now(), asset_name),
                )
            _audit(conn, "asset_maintenance", "INSERT", asset_name,
                   f"type={maintenance_type}, cost={cost}")

        log.info("log_maintenance: '%s' — %s on %s", asset_name, maintenance_type, maintenance_date)
        return True

    except Exception as exc:
        log.error("log_maintenance error: %s", exc)
        return False


def get_maintenance_log(asset_name: str) -> list:
    """Return all maintenance records for an asset, newest first."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM asset_maintenance WHERE asset_name=? "
                "ORDER BY id DESC",
                (asset_name,),
            ).fetchall()
        return [_row_to_maintenance(r) for r in rows]
    except Exception as exc:
        log.error("get_maintenance_log error: %s", exc)
        return []


def get_upcoming_maintenance(days_ahead: int = 30) -> list:
    """
    Return maintenance records where next_due_date is within the next
    `days_ahead` days (and not blank).
    """
    try:
        cutoff = (date.today() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        today  = _today()
        with _connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM asset_maintenance
                WHERE next_due_date != ''
                  AND next_due_date >= ?
                  AND next_due_date <= ?
                ORDER BY next_due_date ASC
                """,
                (today, cutoff),
            ).fetchall()
        return [_row_to_maintenance(r) for r in rows]
    except Exception as exc:
        log.error("get_upcoming_maintenance error: %s", exc)
        return []


def get_maintenance_cost_summary() -> dict:
    """Return {asset_name: total_cost} for all assets with maintenance records."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT asset_name, SUM(cost) as total FROM asset_maintenance "
                "GROUP BY asset_name ORDER BY total DESC"
            ).fetchall()
        return {r["asset_name"]: float(r["total"] or 0) for r in rows}
    except Exception as exc:
        log.error("get_maintenance_cost_summary error: %s", exc)
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Departments
# ─────────────────────────────────────────────────────────────────────────────

def add_department(name: str, manager: str = "", location: str = "") -> bool:
    """Add a department to the reference table.  Ignores duplicates."""
    if not name:
        return False
    try:
        with _connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, manager, location, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name.strip(), manager, location, _now()),
            )
        return True
    except Exception as exc:
        log.error("add_department error: %s", exc)
        return False


def get_all_departments() -> list:
    """Return all departments as a list of dicts."""
    try:
        with _connection() as conn:
            rows = conn.execute(
                "SELECT * FROM departments ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.error("get_all_departments error: %s", exc)
        return []


def remove_department(name: str) -> bool:
    try:
        with _connection() as conn:
            conn.execute("DELETE FROM departments WHERE name=?", (name,))
        return True
    except Exception as exc:
        log.error("remove_department error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Sync helpers  (bridge to main_window asset_data list)
# ─────────────────────────────────────────────────────────────────────────────

def load_assets_to_memory(asset_list: list) -> int:
    """
    Pull all assets from SQLite into the in-memory asset_data list used by
    main_window.py.  Clears and repopulates the list in-place.

    Usage in MainWindow.__init__:
        from core.asset_manager import init_asset_tables, load_assets_to_memory
        init_asset_tables()
        load_assets_to_memory(asset_data)
    """
    assets = get_all_assets()
    asset_list.clear()
    asset_list.extend(assets)
    return len(assets)


def save_assets_from_memory(asset_list: list) -> int:
    """
    Push the in-memory asset_data list into SQLite using assign_asset (upsert).
    Returns the number of records written.

    Usage before app exit or on explicit save:
        from core.asset_manager import save_assets_from_memory
        save_assets_from_memory(asset_data)
    """
    count = 0
    for entry in asset_list:
        name = entry.get("asset", "")
        if not name:
            continue
        ok = assign_asset(
            asset_name    = name,
            assigned_to   = entry.get("assigned_to",  ""),
            department    = entry.get("department",    ""),
            location      = entry.get("location",     ""),
            assigned_date = entry.get("assigned_date", ""),
            item_id       = entry.get("item_id",      ""),
            category      = entry.get("category",     name),
            status        = entry.get("status",       "Active"),
            notes         = entry.get("notes",        ""),
            serial        = entry.get("serial",       ""),
        )
        if ok:
            count += 1
    log.info("save_assets_from_memory: %d records written", count)
    return count


# ─────────────────────────────────────────────────────────────────────────────
# Reports / Stats
# ─────────────────────────────────────────────────────────────────────────────

def get_asset_stats() -> dict:
    """
    Return a summary dict for dashboard stat cards.
    Keys: total, active, in_repair, retired, lost, available, reserved
    """
    try:
        with _connection() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
            by_status = {
                row["status"]: row["cnt"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) as cnt FROM assets GROUP BY status"
                ).fetchall()
            }
        return {
            "total":     total,
            "active":    by_status.get("Active",    0),
            "in_repair": by_status.get("In Repair", 0),
            "retired":   by_status.get("Retired",   0),
            "lost":      by_status.get("Lost",      0),
            "available": by_status.get("Available", 0),
            "reserved":  by_status.get("Reserved",  0),
        }
    except Exception as exc:
        log.error("get_asset_stats error: %s", exc)
        return {k: 0 for k in ["total","active","in_repair","retired","lost","available","reserved"]}


def get_department_asset_summary() -> list:
    """
    Return [{department, total, active, in_repair}] for the reports tab.
    """
    try:
        with _connection() as conn:
            rows = conn.execute(
                """
                SELECT department,
                       COUNT(*)                                   AS total,
                       SUM(CASE WHEN status='Active'    THEN 1 ELSE 0 END) AS active,
                       SUM(CASE WHEN status='In Repair' THEN 1 ELSE 0 END) AS in_repair
                FROM assets
                GROUP BY department
                ORDER BY department COLLATE NOCASE
                """
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.error("get_department_asset_summary error: %s", exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

def export_assets_to_excel(filepath: str) -> bool:
    """
    Export assets, history, and maintenance log to a three-sheet Excel workbook.
    Requires pandas + openpyxl.  Returns True on success.
    """
    if not _PANDAS_AVAILABLE:
        log.error("export_assets_to_excel: pandas not installed")
        return False
    try:
        assets      = get_all_assets()
        history     = get_recent_activity(limit=10000)
        maintenance = []
        for asset in assets:
            maintenance.extend(get_maintenance_log(asset["asset"]))

        def _df(data, fallback_cols):
            return _pd.DataFrame(data) if data else _pd.DataFrame(columns=fallback_cols)

        df_assets = _df(assets, ["asset","assigned_to","department","location",
                                  "status","serial","assigned_date","notes"])
        df_history = _df(history, ["asset_name","event_type","from_user","to_user",
                                    "department","location","event_date","notes"])
        df_maint   = _df(maintenance, ["asset_name","maintenance_type","description",
                                        "performed_by","cost","maintenance_date","next_due_date"])

        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with _pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df_assets.to_excel(writer,  sheet_name="Assets",      index=False)
            df_history.to_excel(writer, sheet_name="History",     index=False)
            df_maint.to_excel(writer,   sheet_name="Maintenance",  index=False)

        log.info("export_assets_to_excel: written to %s", filepath)
        return True

    except Exception as exc:
        log.error("export_assets_to_excel error: %s", exc)
        return False