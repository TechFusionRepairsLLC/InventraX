"""
reporting.py  —  InventraX Reporting & Export Layer
=====================================================
Centralises every report, export, and data-summary function for the app.
Pulls data from inventory.py and asset_manager.py so main_window.py never
touches the database directly for reporting purposes.

Dependencies
------------
  Required : pandas, sqlite3  (already in requirements)
  Optional : openpyxl          (Excel export — pip install openpyxl)
             matplotlib        (chart PNG export — already used by main_window)
             reportlab         (PDF export    — pip install reportlab)

Public API
----------
  # ── Inventory reports ──
  inventory_summary(inventory_dict)            → dict
  low_stock_report(inventory_dict, threshold)  → list[dict]
  out_of_stock_report(inventory_dict)          → list[dict]
  top_selling_report(inventory_dict, limit)    → list[dict]
  popular_items_report(inventory_dict, limit)  → list[dict]
  revenue_by_category(inventory_dict)          → dict[str, float]
  quantity_by_category(inventory_dict)         → dict[str, int]
  full_inventory_report(inventory_dict)        → list[dict]

  # ── Asset reports ──
  asset_summary(asset_list)                    → dict
  assets_by_status_report(asset_list)          → dict[str, list]
  assets_by_department_report(asset_list)      → dict[str, list]
  assets_by_user_report(asset_list)            → dict[str, list]

  # ── Combined ──
  full_report(inventory_dict, asset_list)      → dict

  # ── CSV export ──
  export_inventory_to_csv(inventory_dict, output_file)   → bool
  export_assets_to_csv(asset_list, output_file)          → bool
  export_full_to_csv(inventory_dict, asset_list, folder) → dict[str,str]

  # ── Excel export ──
  export_inventory_to_excel(inventory_dict, output_file) → bool
  export_assets_to_excel(asset_list, output_file)        → bool
  export_full_workbook(inventory_dict, asset_list, output_file) → bool

  # ── Chart PNG export ──
  export_chart_png(inventory_dict, chart_type, output_file,
                   title, figsize) → bool

  # ── PDF export (requires reportlab) ──
  export_report_pdf(inventory_dict, asset_list, output_file) → bool

  # ── DB-backed exports (reads directly from SQLite) ──
  export_inventory_from_db(output_file, fmt)  → bool   fmt: 'csv'|'excel'
  export_assets_from_db(output_file, fmt)     → bool
  export_audit_log_from_db(output_file, fmt)  → bool

  # ── Scheduled / auto-report helper ──
  generate_auto_report(inventory_dict, asset_list,
                       output_folder, fmt)    → list[str]   (paths written)
"""

import os
import csv
import logging
import sqlite3
from datetime import datetime, date
from typing import Optional

log = logging.getLogger(__name__)

# ── Optional dependencies ─────────────────────────────────────────────────────
try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False
    log.warning("pandas not installed — CSV/Excel export will use stdlib csv module")

try:
    import matplotlib
    matplotlib.use("Agg")          # non-interactive backend for file export
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    _MPL = True
except ImportError:
    _MPL = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as _rl_colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    _REPORTLAB = True
except ImportError:
    _REPORTLAB = False

from config.settings import DB_PATH

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _today_str() -> str:
    return date.today().strftime("%Y-%m-%d")

def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def _safe_int(val, default=0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default

def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def _db_connection():
    """Return a plain sqlite3 connection (no context manager — caller closes it)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────────────────────
# Inventory report builders  (work on the in-memory inventory_data dict)
# ─────────────────────────────────────────────────────────────────────────────

def inventory_summary(inventory_dict: dict, low_stock_threshold: int = 5) -> dict:
    """
    Return a high-level summary dict suitable for the dashboard stat cards
    and the text report pane.

    Keys
    ----
    total_items, total_quantity, out_of_stock_count, low_stock_count,
    total_revenue, total_sold_units, category_count,
    most_valuable_item, highest_revenue_item, generated_at
    """
    if not inventory_dict:
        return {
            "total_items": 0, "total_quantity": 0,
            "out_of_stock_count": 0, "low_stock_count": 0,
            "total_revenue": 0.0, "total_sold_units": 0,
            "category_count": 0, "most_valuable_item": "N/A",
            "highest_revenue_item": "N/A", "generated_at": _now_str(),
        }

    total_qty    = sum(_safe_int(d.get("quantity"))         for d in inventory_dict.values())
    total_rev    = sum(_safe_float(d.get("sold_revenue"))   for d in inventory_dict.values())
    total_sold   = sum(_safe_int(d.get("sold_count"))       for d in inventory_dict.values())
    oos          = sum(1 for d in inventory_dict.values() if _safe_int(d.get("quantity")) == 0)
    low          = sum(1 for d in inventory_dict.values()
                       if 0 < _safe_int(d.get("quantity")) <= low_stock_threshold)
    categories   = {d.get("category", "") for d in inventory_dict.values()}

    most_valuable = max(
        inventory_dict.items(),
        key=lambda x: _safe_float(x[1].get("price")),
        default=(("N/A", {}))
    )[0]
    highest_rev = max(
        inventory_dict.items(),
        key=lambda x: _safe_float(x[1].get("sold_revenue")),
        default=(("N/A", {}))
    )[0]

    return {
        "total_items":          len(inventory_dict),
        "total_quantity":       total_qty,
        "out_of_stock_count":   oos,
        "low_stock_count":      low,
        "total_revenue":        round(total_rev, 2),
        "total_sold_units":     total_sold,
        "category_count":       len(categories),
        "most_valuable_item":   most_valuable,
        "highest_revenue_item": highest_rev,
        "generated_at":         _now_str(),
    }


def low_stock_report(inventory_dict: dict, threshold: int = 5) -> list:
    """
    Return items with 0 < quantity <= threshold, sorted by quantity ascending.
    Each row is a dict with name + all inventory fields.
    """
    results = []
    for name, d in inventory_dict.items():
        qty = _safe_int(d.get("quantity"))
        if 0 < qty <= threshold:
            results.append({"name": name, **d})
    return sorted(results, key=lambda x: _safe_int(x.get("quantity")))


def out_of_stock_report(inventory_dict: dict) -> list:
    """Return items with quantity == 0, sorted by name."""
    return sorted(
        [{"name": n, **d} for n, d in inventory_dict.items()
         if _safe_int(d.get("quantity")) == 0],
        key=lambda x: x["name"].lower()
    )


def top_selling_report(inventory_dict: dict, limit: int = 10) -> list:
    """Return top N items by sold_count, descending."""
    rows = [{"name": n, **d} for n, d in inventory_dict.items()]
    return sorted(rows, key=lambda x: _safe_int(x.get("sold_count")), reverse=True)[:limit]


def popular_items_report(inventory_dict: dict, limit: int = 10) -> list:
    """Return top N items by usage_count, descending."""
    rows = [{"name": n, **d} for n, d in inventory_dict.items()]
    return sorted(rows, key=lambda x: _safe_int(x.get("usage_count")), reverse=True)[:limit]


def revenue_by_category(inventory_dict: dict) -> dict:
    """Return {category: total_sold_revenue} sorted by revenue descending."""
    totals: dict = {}
    for d in inventory_dict.values():
        cat = d.get("category") or "Uncategorised"
        totals[cat] = totals.get(cat, 0.0) + _safe_float(d.get("sold_revenue"))
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


def quantity_by_category(inventory_dict: dict) -> dict:
    """Return {category: total_quantity} sorted by quantity descending."""
    totals: dict = {}
    for d in inventory_dict.values():
        cat = d.get("category") or "Uncategorised"
        totals[cat] = totals.get(cat, 0) + _safe_int(d.get("quantity"))
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


def full_inventory_report(inventory_dict: dict) -> list:
    """
    Return all inventory items as a flat list of dicts with a 'name' key
    prepended, sorted by name.  Ready for DataFrame or CSV export.
    """
    return sorted(
        [{"name": n, **d} for n, d in inventory_dict.items()],
        key=lambda x: x["name"].lower()
    )


# ─────────────────────────────────────────────────────────────────────────────
# Asset report builders  (work on the in-memory asset_data list)
# ─────────────────────────────────────────────────────────────────────────────

def asset_summary(asset_list: list) -> dict:
    """
    Return a high-level summary of all assets.

    Keys
    ----
    total, by_status (dict), by_department (dict),
    most_common_status, generated_at
    """
    if not asset_list:
        return {
            "total": 0, "by_status": {}, "by_department": {},
            "most_common_status": "N/A", "generated_at": _now_str(),
        }

    by_status: dict = {}
    by_dept: dict   = {}
    for entry in asset_list:
        s = entry.get("status", "Active")
        d = entry.get("department", "") or "Unassigned"
        by_status[s]  = by_status.get(s, 0) + 1
        by_dept[d]    = by_dept.get(d, 0) + 1

    most_common = max(by_status.items(), key=lambda x: x[1], default=("N/A", 0))[0]

    return {
        "total":              len(asset_list),
        "by_status":          by_status,
        "by_department":      by_dept,
        "most_common_status": most_common,
        "generated_at":       _now_str(),
    }


def assets_by_status_report(asset_list: list) -> dict:
    """Return {status: [asset_entries]} grouping."""
    groups: dict = {}
    for entry in asset_list:
        s = entry.get("status", "Active")
        groups.setdefault(s, []).append(entry)
    return dict(sorted(groups.items()))


def assets_by_department_report(asset_list: list) -> dict:
    """Return {department: [asset_entries]} grouping."""
    groups: dict = {}
    for entry in asset_list:
        dept = entry.get("department", "") or "Unassigned"
        groups.setdefault(dept, []).append(entry)
    return dict(sorted(groups.items()))


def assets_by_user_report(asset_list: list) -> dict:
    """Return {assigned_to: [asset_entries]} grouping."""
    groups: dict = {}
    for entry in asset_list:
        user = entry.get("assigned_to", "") or "Unassigned"
        groups.setdefault(user, []).append(entry)
    return dict(sorted(groups.items()))


# ─────────────────────────────────────────────────────────────────────────────
# Combined full report
# ─────────────────────────────────────────────────────────────────────────────

def full_report(inventory_dict: dict, asset_list: list,
                low_stock_threshold: int = 5) -> dict:
    """
    Build a complete report dict combining all inventory and asset summaries.
    Returned structure is used by main_window.py's report_display pane and
    by the PDF/Excel exporters.

    Keys
    ----
    inventory_summary, low_stock, out_of_stock, top_selling,
    popular_items, revenue_by_category, quantity_by_category,
    asset_summary, assets_by_status, assets_by_department,
    generated_at
    """
    return {
        "inventory_summary":    inventory_summary(inventory_dict, low_stock_threshold),
        "low_stock":            low_stock_report(inventory_dict, low_stock_threshold),
        "out_of_stock":         out_of_stock_report(inventory_dict),
        "top_selling":          top_selling_report(inventory_dict),
        "popular_items":        popular_items_report(inventory_dict),
        "revenue_by_category":  revenue_by_category(inventory_dict),
        "quantity_by_category": quantity_by_category(inventory_dict),
        "asset_summary":        asset_summary(asset_list),
        "assets_by_status":     assets_by_status_report(asset_list),
        "assets_by_department": assets_by_department_report(asset_list),
        "generated_at":         _now_str(),
    }


def format_report_text(report: dict) -> str:
    """
    Convert a full_report() dict into a human-readable plain-text string
    suitable for display in main_window's QTextEdit report pane.
    """
    lines = []
    sep   = "─" * 52

    def h(title):
        lines.append(f"\n{title}")
        lines.append(sep)

    inv = report.get("inventory_summary", {})
    h("INVENTORY SUMMARY")
    lines.append(f"  Total Items       : {inv.get('total_items', 0)}")
    lines.append(f"  Total Quantity    : {inv.get('total_quantity', 0)}")
    lines.append(f"  Out of Stock      : {inv.get('out_of_stock_count', 0)}")
    lines.append(f"  Low Stock         : {inv.get('low_stock_count', 0)}")
    lines.append(f"  Categories        : {inv.get('category_count', 0)}")
    lines.append(f"  Total Units Sold  : {inv.get('total_sold_units', 0)}")
    lines.append(f"  Total Revenue     : ${inv.get('total_revenue', 0):,.2f}")
    lines.append(f"  Most Valuable     : {inv.get('most_valuable_item', 'N/A')}")
    lines.append(f"  Highest Revenue   : {inv.get('highest_revenue_item', 'N/A')}")

    h("LOW STOCK ITEMS")
    low = report.get("low_stock", [])
    if low:
        for item in low:
            lines.append(f"  {item['name']:<28} Qty: {item.get('quantity', 0)}"
                         f"   SKU: {item.get('sku', '')}")
    else:
        lines.append("  None")

    h("OUT OF STOCK ITEMS")
    oos = report.get("out_of_stock", [])
    if oos:
        for item in oos:
            lines.append(f"  {item['name']:<28} SKU: {item.get('sku', '')}")
    else:
        lines.append("  None")

    h("TOP 10 SELLING ITEMS")
    for item in report.get("top_selling", []):
        lines.append(f"  {item['name']:<28} Sold: {item.get('sold_count', 0):>5}"
                     f"   Rev: ${_safe_float(item.get('sold_revenue')):>9,.2f}")

    h("TOP 10 POPULAR ITEMS  (by usage count)")
    for item in report.get("popular_items", []):
        lines.append(f"  {item['name']:<28} Uses: {item.get('usage_count', 0):>5}")

    h("REVENUE BY CATEGORY")
    for cat, rev in report.get("revenue_by_category", {}).items():
        lines.append(f"  {cat:<28} ${rev:>10,.2f}")

    h("QUANTITY BY CATEGORY")
    for cat, qty in report.get("quantity_by_category", {}).items():
        lines.append(f"  {cat:<28} {qty:>6}")

    # ── Assets ────────────────────────────────────────────────────────────────
    asst = report.get("asset_summary", {})
    h("ASSET SUMMARY")
    lines.append(f"  Total Assets      : {asst.get('total', 0)}")
    for status, count in asst.get("by_status", {}).items():
        lines.append(f"    {status:<22} : {count}")

    h("ASSETS BY DEPARTMENT")
    for dept, entries in report.get("assets_by_department", {}).items():
        lines.append(f"  {dept:<28} {len(entries)} asset(s)")
        for e in entries:
            lines.append(f"    · {e.get('asset', ''):<24} → {e.get('assigned_to', '')}  [{e.get('status', '')}]")

    lines.append(f"\n{'─'*52}")
    lines.append(f"  Report generated: {report.get('generated_at', _now_str())}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CSV export
# ─────────────────────────────────────────────────────────────────────────────

def export_inventory_to_csv(
    inventory_dict: dict,
    output_file: str,
) -> bool:
    """
    Export the in-memory inventory to a CSV file.
    Works with or without pandas.
    Returns True on success.
    """
    _ensure_dir(output_file)
    rows = full_inventory_report(inventory_dict)
    if not rows:
        log.warning("export_inventory_to_csv: no data to export")

    if _PANDAS:
        try:
            pd.DataFrame(rows).to_csv(output_file, index=False)
            log.info("export_inventory_to_csv → %s (%d rows)", output_file, len(rows))
            return True
        except Exception as exc:
            log.error("export_inventory_to_csv (pandas) error: %s", exc)
            return False

    # stdlib fallback
    try:
        fieldnames = [
            "name", "category", "quantity", "location", "price", "sku",
            "sold_count", "sold_revenue", "usage_count", "serial",
            "warranty_date", "notes",
        ]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        log.info("export_inventory_to_csv (stdlib) → %s (%d rows)", output_file, len(rows))
        return True
    except Exception as exc:
        log.error("export_inventory_to_csv (stdlib) error: %s", exc)
        return False


def export_assets_to_csv(asset_list: list, output_file: str) -> bool:
    """Export the in-memory asset list to a CSV file."""
    _ensure_dir(output_file)
    if not asset_list:
        log.warning("export_assets_to_csv: no data to export")

    if _PANDAS:
        try:
            pd.DataFrame(asset_list).to_csv(output_file, index=False)
            log.info("export_assets_to_csv → %s (%d rows)", output_file, len(asset_list))
            return True
        except Exception as exc:
            log.error("export_assets_to_csv error: %s", exc)
            return False

    try:
        fieldnames = ["asset", "assigned_to", "department", "location",
                      "status", "serial", "notes", "assigned_date"]
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(asset_list)
        return True
    except Exception as exc:
        log.error("export_assets_to_csv (stdlib) error: %s", exc)
        return False


def export_full_to_csv(
    inventory_dict: dict,
    asset_list: list,
    output_folder: str,
) -> dict:
    """
    Export both inventory and assets as separate CSVs into output_folder.
    Returns {'inventory': path, 'assets': path} for success, or empty string on failure.
    """
    os.makedirs(output_folder, exist_ok=True)
    stamp  = date.today().strftime("%Y%m%d")
    inv_path   = os.path.join(output_folder, f"inventory_{stamp}.csv")
    asset_path = os.path.join(output_folder, f"assets_{stamp}.csv")
    return {
        "inventory": inv_path   if export_inventory_to_csv(inventory_dict, inv_path)   else "",
        "assets":    asset_path if export_assets_to_csv(asset_list,        asset_path) else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Excel export
# ─────────────────────────────────────────────────────────────────────────────

def export_inventory_to_excel(
    inventory_dict: dict,
    output_file: str,
) -> bool:
    """Export inventory to a single-sheet .xlsx file."""
    if not _PANDAS:
        log.error("export_inventory_to_excel: pandas not installed")
        return False
    _ensure_dir(output_file)
    rows = full_inventory_report(inventory_dict)
    try:
        df = pd.DataFrame(rows) if rows else pd.DataFrame()
        df.rename(columns={
            "name": "Item Name", "category": "Category", "quantity": "Quantity",
            "location": "Location", "price": "Price ($)", "sku": "SKU",
            "sold_count": "Sold Count", "sold_revenue": "Sold Revenue ($)",
            "usage_count": "Usage Count", "serial": "Serial No.",
            "warranty_date": "Warranty Date", "notes": "Notes",
        }, inplace=True)
        df.to_excel(output_file, sheet_name="Inventory", index=False)
        log.info("export_inventory_to_excel → %s", output_file)
        return True
    except Exception as exc:
        log.error("export_inventory_to_excel error: %s", exc)
        return False


def export_assets_to_excel(asset_list: list, output_file: str) -> bool:
    """Export asset list to a single-sheet .xlsx file."""
    if not _PANDAS:
        log.error("export_assets_to_excel: pandas not installed")
        return False
    _ensure_dir(output_file)
    try:
        df = pd.DataFrame(asset_list) if asset_list else pd.DataFrame()
        df.rename(columns={
            "asset": "Asset Name", "assigned_to": "Assigned To",
            "department": "Department", "location": "Location",
            "status": "Status", "serial": "Serial No.",
            "notes": "Notes", "assigned_date": "Assigned Date",
        }, inplace=True)
        df.to_excel(output_file, sheet_name="Assets", index=False)
        log.info("export_assets_to_excel → %s", output_file)
        return True
    except Exception as exc:
        log.error("export_assets_to_excel error: %s", exc)
        return False


def export_full_workbook(
    inventory_dict: dict,
    asset_list: list,
    output_file: str,
    low_stock_threshold: int = 5,
) -> bool:
    """
    Export a multi-sheet Excel workbook:
      Sheet 1 — Inventory         (all items)
      Sheet 2 — Low Stock         (qty > 0 and <= threshold)
      Sheet 3 — Out of Stock      (qty == 0)
      Sheet 4 — Top Selling       (by sold_count)
      Sheet 5 — Revenue Summary   (by category)
      Sheet 6 — Assets            (all asset records)
      Sheet 7 — Assets by Dept    (grouped summary)

    Returns True on success.
    """
    if not _PANDAS:
        log.error("export_full_workbook: pandas not installed")
        return False
    _ensure_dir(output_file)
    try:
        report = full_report(inventory_dict, asset_list, low_stock_threshold)

        def _df(data):
            return pd.DataFrame(data) if data else pd.DataFrame()

        df_inv      = _df(full_inventory_report(inventory_dict))
        df_low      = _df(report["low_stock"])
        df_oos      = _df(report["out_of_stock"])
        df_selling  = _df(report["top_selling"])
        df_rev_cat  = pd.DataFrame(
            [{"Category": k, "Total Revenue ($)": v}
             for k, v in report["revenue_by_category"].items()]
        )
        df_qty_cat  = pd.DataFrame(
            [{"Category": k, "Total Quantity": v}
             for k, v in report["quantity_by_category"].items()]
        )
        df_assets   = _df(asset_list)
        dept_rows   = [
            {"Department": dept, "Asset Count": len(entries),
             "Active": sum(1 for e in entries if e.get("status") == "Active"),
             "In Repair": sum(1 for e in entries if e.get("status") == "In Repair")}
            for dept, entries in report["assets_by_department"].items()
        ]
        df_dept     = pd.DataFrame(dept_rows) if dept_rows else pd.DataFrame()

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            df_inv.to_excel(    writer, sheet_name="Inventory",       index=False)
            df_low.to_excel(    writer, sheet_name="Low Stock",        index=False)
            df_oos.to_excel(    writer, sheet_name="Out of Stock",     index=False)
            df_selling.to_excel(writer, sheet_name="Top Selling",      index=False)
            df_rev_cat.to_excel(writer, sheet_name="Revenue by Cat",   index=False)
            df_qty_cat.to_excel(writer, sheet_name="Qty by Category",  index=False)
            df_assets.to_excel( writer, sheet_name="Assets",           index=False)
            df_dept.to_excel(   writer, sheet_name="Assets by Dept",   index=False)

        log.info("export_full_workbook → %s (8 sheets)", output_file)
        return True
    except Exception as exc:
        log.error("export_full_workbook error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Chart PNG export
# ─────────────────────────────────────────────────────────────────────────────

# Chart colour palette that matches InventraX themes
_CHART_COLORS = [
    "#00D4AA", "#FFB800", "#FF4757", "#4D9FFF",
    "#A855F7", "#22C55E", "#F59E0B", "#EF4444",
]


def export_chart_png(
    inventory_dict: dict,
    chart_type:  str   = "bar",          # "bar" | "pie" | "line" | "revenue_bar" | "horizontal_bar"
    output_file: str   = "chart.png",
    title:       str   = "",
    figsize:     tuple = (9, 5),
    dpi:         int   = 150,
) -> bool:
    """
    Render a chart from inventory data and save it as a PNG.

    chart_type options
    ------------------
    "bar"          — quantity per category (vertical bar)
    "horizontal_bar" — quantity per category (horizontal, easier to read long names)
    "pie"          — inventory distribution by category
    "line"         — quantity trend across categories (alphabetical)
    "revenue_bar"  — revenue per category (vertical bar)
    "top_selling"  — top 10 selling items horizontal bar

    Returns True on success, False if matplotlib is not installed or an error occurs.
    """
    if not _MPL:
        log.error("export_chart_png: matplotlib not installed")
        return False
    _ensure_dir(output_file)

    qty_by_cat = quantity_by_category(inventory_dict)
    rev_by_cat = revenue_by_category(inventory_dict)

    try:
        fig, ax = plt.subplots(figsize=figsize, facecolor="#1E2333")
        ax.set_facecolor("#252A3D")
        for spine in ax.spines.values():
            spine.set_color("#3D4470")
        ax.tick_params(colors="#8892B0", labelsize=9)
        ax.xaxis.label.set_color("#8892B0")
        ax.yaxis.label.set_color("#8892B0")

        chart_title = title or {
            "bar":           "Inventory Quantity by Category",
            "horizontal_bar":"Inventory Quantity by Category",
            "pie":           "Inventory Distribution by Category",
            "line":          "Quantity Trend by Category",
            "revenue_bar":   "Revenue by Category",
            "top_selling":   "Top 10 Selling Items",
        }.get(chart_type, "Inventory Report")
        ax.set_title(chart_title, color="#E8EAF6", fontsize=13, fontweight="bold", pad=12)

        if chart_type == "bar":
            if qty_by_cat:
                bars = ax.bar(qty_by_cat.keys(), qty_by_cat.values(),
                              color=_CHART_COLORS[:len(qty_by_cat)], width=0.55)
                ax.set_ylabel("Quantity", color="#8892B0")
                ax.tick_params(axis="x", rotation=30)
                for bar in bars:
                    ax.text(bar.get_x() + bar.get_width()/2,
                            bar.get_height() + 0.1,
                            str(int(bar.get_height())),
                            ha="center", va="bottom", color="#E8EAF6", fontsize=8)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        elif chart_type == "horizontal_bar":
            if qty_by_cat:
                cats  = list(qty_by_cat.keys())[::-1]
                qtys  = [qty_by_cat[c] for c in cats]
                bars  = ax.barh(cats, qtys,
                                color=_CHART_COLORS[:len(cats)], height=0.55)
                ax.set_xlabel("Quantity", color="#8892B0")
                for bar in bars:
                    ax.text(bar.get_width() + 0.1,
                            bar.get_y() + bar.get_height()/2,
                            str(int(bar.get_width())),
                            va="center", color="#E8EAF6", fontsize=8)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        elif chart_type == "pie":
            if qty_by_cat:
                wedges, texts, autotexts = ax.pie(
                    qty_by_cat.values(),
                    labels=qty_by_cat.keys(),
                    autopct="%1.1f%%",
                    startangle=140,
                    colors=_CHART_COLORS[:len(qty_by_cat)],
                    wedgeprops={"linewidth": 1, "edgecolor": "#1E2333"},
                )
                for t in texts:     t.set_color("#E8EAF6")
                for t in autotexts: t.set_color("#1E2333"); t.set_fontsize(8)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        elif chart_type == "line":
            sc = sorted(qty_by_cat.items())
            if sc:
                cats, qtys = zip(*sc)
                ax.plot(cats, qtys, marker="o", linestyle="-",
                        color="#00D4AA", linewidth=2, markersize=7,
                        markerfacecolor="#1E2333", markeredgecolor="#00D4AA",
                        markeredgewidth=2)
                ax.fill_between(range(len(cats)), qtys, alpha=0.12, color="#00D4AA")
                ax.set_xticks(range(len(cats)))
                ax.set_xticklabels(cats, rotation=30, ha="right")
                ax.set_ylabel("Quantity", color="#8892B0")
                ax.grid(axis="y", color="#2D3454", linestyle="--", alpha=0.5)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        elif chart_type == "revenue_bar":
            if rev_by_cat:
                bars = ax.bar(rev_by_cat.keys(), rev_by_cat.values(),
                              color=_CHART_COLORS[:len(rev_by_cat)], width=0.55)
                ax.set_ylabel("Revenue ($)", color="#8892B0")
                ax.tick_params(axis="x", rotation=30)
                ax.yaxis.set_major_formatter(
                    mticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
                )
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        elif chart_type == "top_selling":
            selling = top_selling_report(inventory_dict, limit=10)
            if selling:
                names  = [s["name"][:20] for s in selling][::-1]
                counts = [_safe_int(s.get("sold_count")) for s in selling][::-1]
                bars   = ax.barh(names, counts,
                                 color=_CHART_COLORS[:len(names)], height=0.55)
                ax.set_xlabel("Units Sold", color="#8892B0")
                for bar in bars:
                    ax.text(bar.get_width() + 0.1,
                            bar.get_y() + bar.get_height()/2,
                            str(int(bar.get_width())),
                            va="center", color="#E8EAF6", fontsize=8)
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center",
                        color="#8892B0", transform=ax.transAxes)

        else:
            log.warning("export_chart_png: unknown chart_type '%s'", chart_type)
            plt.close(fig)
            return False

        fig.tight_layout()
        fig.savefig(output_file, dpi=dpi, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        log.info("export_chart_png: saved %s (%s)", output_file, chart_type)
        return True

    except Exception as exc:
        log.error("export_chart_png error: %s", exc)
        try: plt.close(fig)
        except Exception: pass
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PDF export  (requires reportlab)
# ─────────────────────────────────────────────────────────────────────────────

def export_report_pdf(
    inventory_dict: dict,
    asset_list: list,
    output_file: str,
    low_stock_threshold: int = 5,
    company_name: str = "TechFusion Repairs LLC",
) -> bool:
    """
    Generate a professional multi-section PDF report.

    Sections
    --------
    1. Cover / summary stats
    2. Low stock & out-of-stock alert tables
    3. Top selling & popular items tables
    4. Revenue & quantity by category tables
    5. Asset summary & assignment list

    Requires: pip install reportlab
    Returns True on success.
    """
    if not _REPORTLAB:
        log.error("export_report_pdf: reportlab not installed  (pip install reportlab)")
        return False
    _ensure_dir(output_file)

    report = full_report(inventory_dict, asset_list, low_stock_threshold)
    inv    = report["inventory_summary"]
    styles = getSampleStyleSheet()

    # ── Colour helpers ────────────────────────────────────────────────────────
    TEAL   = _rl_colors.HexColor("#00D4AA")
    DARK   = _rl_colors.HexColor("#0F1117")
    PANEL  = _rl_colors.HexColor("#1E2333")
    TEXT   = _rl_colors.HexColor("#E8EAF6")
    SUB    = _rl_colors.HexColor("#8892B0")
    WARN   = _rl_colors.HexColor("#FFB800")
    DANGER = _rl_colors.HexColor("#FF4757")
    WHITE  = _rl_colors.white

    def _h1(text):
        return Paragraph(
            f'<font color="#00D4AA"><b>{text}</b></font>',
            styles["Heading1"]
        )

    def _h2(text):
        return Paragraph(
            f'<font color="#E8EAF6"><b>{text}</b></font>',
            styles["Heading2"]
        )

    def _p(text, color="#8892B0"):
        return Paragraph(
            f'<font color="{color}">{text}</font>',
            styles["Normal"]
        )

    def _table(headers, rows, col_widths=None):
        data   = [headers] + (rows if rows else [["—"] * len(headers)])
        tbl    = Table(data, colWidths=col_widths)
        style  = TableStyle([
            ("BACKGROUND",  (0, 0), (-1, 0),  PANEL),
            ("TEXTCOLOR",   (0, 0), (-1, 0),  TEAL),
            ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, 0),  9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [DARK, PANEL]),
            ("TEXTCOLOR",   (0, 1), (-1, -1), TEXT),
            ("FONTSIZE",    (0, 1), (-1, -1), 8),
            ("GRID",        (0, 0), (-1, -1), 0.4, _rl_colors.HexColor("#2D3454")),
            ("ROWHEIGHT",   (0, 0), (-1, -1), 16),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",  (0, 0), (-1, 0),  8),
        ])
        tbl.setStyle(style)
        return tbl

    story = []

    # ── Cover ─────────────────────────────────────────────────────────────────
    story.append(_h1("InventraX  —  Inventory & Asset Report"))
    story.append(_p(f"Generated: {report['generated_at']}  ·  {company_name}"))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=TEAL))
    story.append(Spacer(1, 0.3 * cm))

    # ── Inventory summary stats ───────────────────────────────────────────────
    story.append(_h2("Inventory Summary"))
    stat_rows = [
        ["Total Items",         str(inv.get("total_items", 0))],
        ["Total Quantity",      str(inv.get("total_quantity", 0))],
        ["Out of Stock",        str(inv.get("out_of_stock_count", 0))],
        ["Low Stock",           str(inv.get("low_stock_count", 0))],
        ["Categories",          str(inv.get("category_count", 0))],
        ["Total Units Sold",    str(inv.get("total_sold_units", 0))],
        ["Total Sales Revenue", f"${inv.get('total_revenue', 0):,.2f}"],
        ["Most Valuable Item",  inv.get("most_valuable_item", "N/A")],
        ["Highest Revenue Item",inv.get("highest_revenue_item", "N/A")],
    ]
    story.append(_table(["Metric", "Value"], stat_rows, col_widths=[9*cm, 8*cm]))
    story.append(Spacer(1, 0.4 * cm))

    # ── Low stock ─────────────────────────────────────────────────────────────
    story.append(_h2("Low Stock Alerts"))
    low_rows = [
        [i["name"][:30], str(i.get("quantity", 0)),
         i.get("category", ""), i.get("sku", ""), i.get("location", "")]
        for i in report["low_stock"]
    ] or [["No low-stock items", "", "", "", ""]]
    story.append(_table(
        ["Item Name", "Qty", "Category", "SKU", "Location"],
        low_rows, col_widths=[6*cm, 2*cm, 4*cm, 3*cm, 4*cm]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Out of stock ──────────────────────────────────────────────────────────
    story.append(_h2("Out of Stock Items"))
    oos_rows = [
        [i["name"][:30], i.get("category", ""), i.get("sku", ""), i.get("location", "")]
        for i in report["out_of_stock"]
    ] or [["No out-of-stock items", "", "", ""]]
    story.append(_table(
        ["Item Name", "Category", "SKU", "Location"],
        oos_rows, col_widths=[7*cm, 4*cm, 3.5*cm, 4.5*cm]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Top selling ───────────────────────────────────────────────────────────
    story.append(_h2("Top 10 Selling Items"))
    sell_rows = [
        [i["name"][:28], str(i.get("sold_count", 0)),
         f"${_safe_float(i.get('sold_revenue')):,.2f}",
         i.get("category", "")]
        for i in report["top_selling"]
    ] or [["No sales data", "", "", ""]]
    story.append(_table(
        ["Item Name", "Units Sold", "Revenue", "Category"],
        sell_rows, col_widths=[7*cm, 3*cm, 4*cm, 5*cm]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Revenue by category ───────────────────────────────────────────────────
    story.append(_h2("Revenue by Category"))
    rev_rows = [
        [cat, f"${rev:,.2f}"]
        for cat, rev in report["revenue_by_category"].items()
    ] or [["No revenue data", ""]]
    story.append(_table(
        ["Category", "Total Revenue ($)"],
        rev_rows, col_widths=[10*cm, 9*cm]
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Asset summary ─────────────────────────────────────────────────────────
    asst = report["asset_summary"]
    story.append(_h2("Asset Summary"))
    asset_stat_rows = [["Total Assets", str(asst.get("total", 0))]]
    for status, count in asst.get("by_status", {}).items():
        asset_stat_rows.append([f"  Status: {status}", str(count)])
    story.append(_table(["Metric", "Value"], asset_stat_rows,
                         col_widths=[9*cm, 8*cm]))
    story.append(Spacer(1, 0.4 * cm))

    # ── Asset list ────────────────────────────────────────────────────────────
    story.append(_h2("Asset Assignments"))
    asset_rows = [
        [e.get("asset", "")[:25], e.get("assigned_to", ""),
         e.get("department", ""), e.get("location", ""), e.get("status", "")]
        for e in asset_list
    ] or [["No assets assigned", "", "", "", ""]]
    story.append(_table(
        ["Asset", "Assigned To", "Department", "Location", "Status"],
        asset_rows, col_widths=[5*cm, 4*cm, 4*cm, 4*cm, 3*cm]
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    try:
        doc = SimpleDocTemplate(
            output_file,
            pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm,   bottomMargin=1.5*cm,
        )
        doc.build(story)
        log.info("export_report_pdf → %s", output_file)
        return True
    except Exception as exc:
        log.error("export_report_pdf build error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# DB-backed exports  (read directly from SQLite — no in-memory dict needed)
# ─────────────────────────────────────────────────────────────────────────────

def export_inventory_from_db(
    output_file: str,
    fmt: str = "csv",           # "csv" | "excel"
) -> bool:
    """
    Export the items table directly from SQLite without touching in-memory data.
    Useful for background / scheduled exports.
    """
    if not _PANDAS:
        log.error("export_inventory_from_db: pandas required")
        return False
    _ensure_dir(output_file)
    try:
        conn = _db_connection()
        df   = pd.read_sql_query("SELECT * FROM items ORDER BY name COLLATE NOCASE", conn)
        conn.close()
        if fmt == "excel":
            df.to_excel(output_file, sheet_name="Inventory", index=False)
        else:
            df.to_csv(output_file, index=False)
        log.info("export_inventory_from_db (%s) → %s", fmt, output_file)
        return True
    except Exception as exc:
        log.error("export_inventory_from_db error: %s", exc)
        return False


def export_assets_from_db(output_file: str, fmt: str = "csv") -> bool:
    """Export the assets table directly from SQLite."""
    if not _PANDAS:
        log.error("export_assets_from_db: pandas required")
        return False
    _ensure_dir(output_file)
    try:
        conn = _db_connection()
        df   = pd.read_sql_query(
            "SELECT * FROM assets ORDER BY asset_name COLLATE NOCASE", conn
        )
        conn.close()
        if fmt == "excel":
            df.to_excel(output_file, sheet_name="Assets", index=False)
        else:
            df.to_csv(output_file, index=False)
        log.info("export_assets_from_db (%s) → %s", fmt, output_file)
        return True
    except Exception as exc:
        log.error("export_assets_from_db error: %s", exc)
        return False


def export_audit_log_from_db(output_file: str, fmt: str = "csv") -> bool:
    """Export the audit_log table directly from SQLite."""
    if not _PANDAS:
        log.error("export_audit_log_from_db: pandas required")
        return False
    _ensure_dir(output_file)
    try:
        conn = _db_connection()
        df   = pd.read_sql_query(
            "SELECT * FROM audit_log ORDER BY id DESC", conn
        )
        conn.close()
        if fmt == "excel":
            df.to_excel(output_file, sheet_name="Audit Log", index=False)
        else:
            df.to_csv(output_file, index=False)
        log.info("export_audit_log_from_db (%s) → %s", fmt, output_file)
        return True
    except Exception as exc:
        log.error("export_audit_log_from_db error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Scheduled / auto-report helper
# ─────────────────────────────────────────────────────────────────────────────

def generate_auto_report(
    inventory_dict: dict,
    asset_list:     list,
    output_folder:  str  = "reports",
    fmt:            str  = "excel",       # "csv" | "excel" | "pdf" | "all"
    low_stock_threshold: int = 5,
) -> list:
    """
    Generate a dated report bundle in output_folder.
    Returns a list of file paths that were successfully written.

    fmt = "all"   → writes Excel workbook + CSV pair + PDF (if reportlab available)
    fmt = "excel" → writes the full multi-sheet workbook only
    fmt = "csv"   → writes inventory.csv + assets.csv
    fmt = "pdf"   → writes the PDF only (requires reportlab)

    Typical usage (e.g. on app close or a scheduled timer):
        from core.reporting import generate_auto_report
        paths = generate_auto_report(inventory_data, asset_data,
                                     output_folder="reports", fmt="all")
        print("Saved:", paths)
    """
    os.makedirs(output_folder, exist_ok=True)
    stamp   = datetime.now().strftime("%Y%m%d_%H%M")
    written = []

    if fmt in ("excel", "all"):
        path = os.path.join(output_folder, f"inventrax_report_{stamp}.xlsx")
        if export_full_workbook(inventory_dict, asset_list, path, low_stock_threshold):
            written.append(path)

    if fmt in ("csv", "all"):
        paths = export_full_to_csv(inventory_dict, asset_list, output_folder)
        written.extend(p for p in paths.values() if p)

    if fmt in ("pdf", "all"):
        path = os.path.join(output_folder, f"inventrax_report_{stamp}.pdf")
        if export_report_pdf(inventory_dict, asset_list, path, low_stock_threshold):
            written.append(path)

    log.info("generate_auto_report: %d file(s) written to '%s'", len(written), output_folder)
    return written