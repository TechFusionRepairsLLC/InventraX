"""
config/settings.py  —  InventraX Global Configuration
=======================================================
Single source of truth for every path, constant, and default value
used across the application.  Import what you need:

    from config.settings import DB_PATH, APP_TITLE, LOW_STOCK_THRESHOLD
    from config.settings import PATHS, APP_DEFAULTS, APP_INFO

Nothing in this file has side-effects — it is safe to import anywhere.
"""

import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# App Identity
# ─────────────────────────────────────────────────────────────────────────────

APP_TITLE       = "InventraX"
APP_SUBTITLE    = "Inventory & Asset Management Platform"
APP_VERSION     = "2.0.0"
APP_AUTHOR      = "Alejandro X. Solis"
APP_COMPANY     = "TechFusion Repairs LLC"
APP_EMAIL       = "TechFusionRepairs@gmail.com"
APP_WEBSITE     = "https://alejandroxsolis93.wixsite.com/techfusionrepairsllc"
APP_GITHUB      = "https://github.com/TechFusionRepairsLLC"
APP_DONATE_URL  = "https://www.paypal.com/donate/?hosted_button_id=CESA5GQALY386"

# ─────────────────────────────────────────────────────────────────────────────
# Base Directories
# ─────────────────────────────────────────────────────────────────────────────
# All paths are relative to the project root (the folder containing Main.py).
# Using __file__ would anchor to the config/ package — so we walk up one level.

_HERE        = os.path.dirname(os.path.abspath(__file__))   # .../config/
BASE_DIR     = os.path.dirname(_HERE)                        # project root

# ─────────────────────────────────────────────────────────────────────────────
# File & Folder Paths
# ─────────────────────────────────────────────────────────────────────────────

# Data
DATA_DIR     = os.path.join(BASE_DIR, "data")
DB_PATH      = os.path.join(DATA_DIR, "inventrax.db")

# Logs
LOG_DIR      = os.path.join(BASE_DIR, "logs")
LOG_PATH     = os.path.join(LOG_DIR,  "inventrax.log")

# Reports output
REPORTS_DIR  = os.path.join(BASE_DIR, "reports")

# Automatic backups
BACKUP_DIR   = os.path.join(BASE_DIR, "backups")

# Barcode / QR images
BARCODES_DIR = os.path.join(BASE_DIR, "barcodes")

# UI assets
ASSETS_DIR        = os.path.join(BASE_DIR, "assets")
ICONS_DIR         = os.path.join(ASSETS_DIR, "icons")
APP_LOGO_PATH     = os.path.join(ICONS_DIR, "inventrax_logo.png")
COMPANY_LOGO_PATH = os.path.join(ICONS_DIR, "TechFusion.png")

# User preferences (theme, font size, etc.)
PREFS_DIR    = os.path.join(BASE_DIR, "config")
PREFS_PATH   = os.path.join(PREFS_DIR, "user_prefs.json")

# Convenience dict — pass to any function that needs to create directories
PATHS = {
    "base":     BASE_DIR,
    "data":     DATA_DIR,
    "db":       DB_PATH,
    "logs":     LOG_DIR,
    "log_file": LOG_PATH,
    "reports":  REPORTS_DIR,
    "backups":  BACKUP_DIR,
    "barcodes": BARCODES_DIR,
    "assets":   ASSETS_DIR,
    "icons":    ICONS_DIR,
    "prefs":    PREFS_PATH,
}

# ─────────────────────────────────────────────────────────────────────────────
# Inventory Defaults
# ─────────────────────────────────────────────────────────────────────────────

LOW_STOCK_THRESHOLD  = 5       # items at or below this qty trigger a warning
MAX_QUANTITY         = 99_999  # SpinBox upper bound
DEFAULT_CURRENCY     = "USD"
CURRENCY_SYMBOL      = "$"

# ─────────────────────────────────────────────────────────────────────────────
# Asset Defaults
# ─────────────────────────────────────────────────────────────────────────────

ASSET_STATUSES = [
    "Active",
    "In Repair",
    "Available",
    "Reserved",
    "Retired",
    "Lost",
    "Disposed",
]

MAINTENANCE_TYPES = [
    "Repair",
    "Inspection",
    "Upgrade",
    "Cleaning",
    "Calibration",
    "Other",
]

# ─────────────────────────────────────────────────────────────────────────────
# UI / Display Defaults
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_THEME      = "Teal Dark"
DEFAULT_FONT_SIZE  = 10         # points
MIN_FONT_SIZE      = 8
MAX_FONT_SIZE      = 16
WINDOW_MIN_WIDTH   = 1000
WINDOW_MIN_HEIGHT  = 700
WINDOW_DEFAULT_WIDTH  = 1160
WINDOW_DEFAULT_HEIGHT = 800

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOG_LEVEL          = "INFO"     # DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_MAX_BYTES      = 5_242_880  # 5 MB before rotation
LOG_BACKUP_COUNT   = 3          # keep 3 rotated log files

# ─────────────────────────────────────────────────────────────────────────────
# Backup
# ─────────────────────────────────────────────────────────────────────────────

BACKUP_ON_CLOSE    = True       # auto-backup DB when app closes
MAX_BACKUPS        = 10         # oldest backup deleted when limit is exceeded
BACKUP_FORMAT      = "%Y%m%d_%H%M%S"   # timestamp format in backup filenames

# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_REPORT_FMT = "excel"    # "csv" | "excel" | "pdf" | "all"
AUTO_REPORT_ON_CLOSE = False    # generate a report bundle on every close

# ─────────────────────────────────────────────────────────────────────────────
# App Defaults dict  (mirrors APP_SETTINGS in main_window — source of truth)
# ─────────────────────────────────────────────────────────────────────────────

APP_DEFAULTS = {
    "theme":               DEFAULT_THEME,
    "low_stock_threshold": LOW_STOCK_THRESHOLD,
    "font_size":           DEFAULT_FONT_SIZE,
    "confirm_deletes":     True,
    "startup_warning":     True,
    "backup_on_close":     BACKUP_ON_CLOSE,
    "auto_report_on_close":AUTO_REPORT_ON_CLOSE,
    "default_report_fmt":  DEFAULT_REPORT_FMT,
    "currency_symbol":     CURRENCY_SYMBOL,
    "window_width":        WINDOW_DEFAULT_WIDTH,
    "window_height":       WINDOW_DEFAULT_HEIGHT,
}

# ─────────────────────────────────────────────────────────────────────────────
# App Info dict  (used by Settings dialog About section and Main.py)
# ─────────────────────────────────────────────────────────────────────────────

APP_INFO = {
    "title":    APP_TITLE,
    "subtitle": APP_SUBTITLE,
    "version":  APP_VERSION,
    "author":   APP_AUTHOR,
    "company":  APP_COMPANY,
    "email":    APP_EMAIL,
    "website":  APP_WEBSITE,
    "github":   APP_GITHUB,
    "donate":   APP_DONATE_URL,
}