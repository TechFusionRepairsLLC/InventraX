"""
Main.py  —  InventraX Application Entry Point
==============================================
Handles in order:
  1. Logging configuration (file + console, rotating)
  2. Required directory creation
  3. Database initialisation (inventory + asset tables)
  4. User preferences load (theme, font, settings)
  5. Splash screen
  6. Main window launch
  7. Auto-save & backup on clean exit
  8. Top-level exception handler so crashes are logged, not silent
"""

import sys
import os
import logging
import traceback
from logging.handlers import RotatingFileHandler

# ── Ensure project root is on sys.path so all imports resolve ────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Settings (no side-effects — safe to import first) ────────────────────────
from config.settings import (
    APP_TITLE, APP_VERSION, APP_COMPANY,
    LOG_PATH, LOG_DIR, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT,
    DATA_DIR, REPORTS_DIR, BACKUP_DIR, BARCODES_DIR, PREFS_PATH,
    BACKUP_ON_CLOSE, AUTO_REPORT_ON_CLOSE, DEFAULT_REPORT_FMT,
    PATHS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Logging
# ─────────────────────────────────────────────────────────────────────────────

def _setup_logging() -> logging.Logger:
    """
    Configure the root logger with:
      • RotatingFileHandler → logs/inventrax.log  (5 MB × 3 files)
      • StreamHandler       → console (INFO and above)
    Returns the application-level logger.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.INFO)

    root_log = logging.getLogger()
    root_log.setLevel(level)
    root_log.addHandler(file_handler)
    root_log.addHandler(console_handler)

    return logging.getLogger("inventrax.main")


log = _setup_logging()
log.info("─" * 60)
log.info("InventraX %s  starting up", APP_VERSION)
log.info("Python %s  |  %s", sys.version.split()[0], sys.platform)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Required directories
# ─────────────────────────────────────────────────────────────────────────────

def _create_directories() -> None:
    dirs = [DATA_DIR, LOG_DIR, REPORTS_DIR, BACKUP_DIR, BARCODES_DIR,
            os.path.dirname(PREFS_PATH)]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    log.info("Directories verified")


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Database initialisation
# ─────────────────────────────────────────────────────────────────────────────

def _init_database() -> None:
    try:
        from core.inventory     import init_db
        from core.asset_manager import init_asset_tables
        init_db()
        init_asset_tables()
        log.info("Database initialised")
    except Exception:
        log.critical("Database initialisation failed:\n%s", traceback.format_exc())
        # Non-fatal — app can still run with in-memory data only


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — User preferences
# ─────────────────────────────────────────────────────────────────────────────

def _load_preferences() -> None:
    """
    Load saved user preferences from config/user_prefs.json and apply
    them to main_window.APP_SETTINGS and COLORS before the window opens.
    Completely safe on first run — falls back to defaults silently.
    """
    import os
    # Skip entirely if prefs module or prefs file doesn't exist yet
    prefs_module = os.path.join(_ROOT, "core", "prefs.py")
    if not os.path.exists(prefs_module):
        log.info("startup: core/prefs.py not found — using defaults (first run?)")
        return
    try:
        from core.prefs import load_prefs, apply_prefs
        prefs = load_prefs()
        apply_prefs(prefs)
        log.info("User preferences loaded (theme: %s)", prefs.get("theme", "default"))
    except Exception:
        log.warning("Could not load user preferences — using defaults\n%s",
                    traceback.format_exc())


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Splash screen
# ─────────────────────────────────────────────────────────────────────────────

def _build_splash(app):
    """
    Show a minimal splash screen while the DB and UI initialise.
    Returns the QSplashScreen instance (caller must call .finish(window)).
    """
    try:
        from PyQt5.QtWidgets import QSplashScreen, QLabel
        from PyQt5.QtGui     import QPixmap, QPainter, QColor, QFont
        from PyQt5.QtCore    import Qt
        from config.settings import APP_LOGO_PATH, WINDOW_DEFAULT_WIDTH

        # Build a 480×220 dark splash programmatically
        # (falls back gracefully if the logo file doesn't exist)
        W, H = 480, 220
        pix = QPixmap(W, H)
        pix.fill(QColor("#0F1117"))

        painter = QPainter(pix)

        # Teal accent bar at top
        painter.fillRect(0, 0, W, 4, QColor("#00D4AA"))

        # Logo (if it exists)
        logo_pix = QPixmap(APP_LOGO_PATH)
        if not logo_pix.isNull():
            logo_scaled = logo_pix.scaled(64, 64, Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation)
            painter.drawPixmap(W // 2 - 32, 28, logo_scaled)
            title_y = 112
        else:
            title_y = 60

        # App title
        font_title = QFont("Segoe UI", 22, QFont.Bold)
        painter.setFont(font_title)
        painter.setPen(QColor("#E8EAF6"))
        painter.drawText(0, title_y, W, 40, Qt.AlignHCenter, APP_TITLE)

        # Subtitle
        font_sub = QFont("Segoe UI", 10)
        painter.setFont(font_sub)
        painter.setPen(QColor("#8892B0"))
        painter.drawText(0, title_y + 44, W, 28, Qt.AlignHCenter,
                         "Inventory & Asset Management Platform")

        # Version
        font_ver = QFont("Segoe UI", 8)
        painter.setFont(font_ver)
        painter.setPen(QColor("#4D5A8A"))
        painter.drawText(0, H - 28, W, 20, Qt.AlignHCenter,
                         f"v{APP_VERSION}  ·  {APP_COMPANY}")

        # Loading bar background
        painter.fillRect(40, H - 12, W - 80, 4, QColor("#1E2333"))
        painter.fillRect(40, H - 12, (W - 80) // 2, 4, QColor("#00D4AA"))

        painter.end()

        splash = QSplashScreen(pix, Qt.WindowStaysOnTopHint)
        splash.setMask(pix.mask())
        splash.show()
        app.processEvents()
        return splash

    except Exception:
        log.warning("Splash screen could not be created: %s", traceback.format_exc())
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Auto-save & backup on exit
# ─────────────────────────────────────────────────────────────────────────────

def _on_clean_exit() -> None:
    """Called after the Qt event loop exits normally."""
    try:
        from core.prefs import save_prefs
        save_prefs()
        log.info("Preferences saved on exit")
    except Exception:
        log.warning("Could not save preferences: %s", traceback.format_exc())

    try:
        if BACKUP_ON_CLOSE:
            from core.backup import backup_database
            path = backup_database()
            if path:
                log.info("Auto-backup written: %s", path)
    except Exception:
        log.warning("Auto-backup failed: %s", traceback.format_exc())

    if AUTO_REPORT_ON_CLOSE:
        try:
            from ui.main_window   import inventory_data, asset_data
            from core.reporting   import generate_auto_report
            paths = generate_auto_report(
                inventory_data, asset_data,
                output_folder=REPORTS_DIR,
                fmt=DEFAULT_REPORT_FMT,
            )
            log.info("Auto-report written: %s", paths)
        except Exception:
            log.warning("Auto-report failed: %s", traceback.format_exc())

    log.info("InventraX shut down cleanly")
    log.info("─" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Top-level exception handler
# ─────────────────────────────────────────────────────────────────────────────

def _handle_uncaught_exception(exc_type, exc_value, exc_tb):
    """
    Catches any unhandled exception, logs it to file, and shows a user-
    friendly error dialog instead of a silent crash.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log.critical("Unhandled exception:\n%s", tb_str)

    # Show error dialog if Qt is running
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app:
            msg = QMessageBox()
            msg.setWindowTitle(f"{APP_TITLE} — Unexpected Error")
            msg.setIcon(QMessageBox.Critical)
            msg.setText(
                "<b>An unexpected error occurred.</b><br><br>"
                "The error has been logged to:<br>"
                f"<code>{LOG_PATH}</code><br><br>"
                "The application will now close."
            )
            msg.setDetailedText(tb_str)
            msg.exec_()
    except Exception:
        pass  # Qt itself may be broken — nothing more we can do


sys.excepthook = _handle_uncaught_exception


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore    import Qt

    # HiDPI support
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_TITLE)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_COMPANY)

    # ── Show splash immediately before ANY blocking work ─────────────────────
    splash = _build_splash(app)
    app.processEvents()   # paint the splash right away

    # ── Step 2: directories ───────────────────────────────────────────────────
    log.info("startup: creating directories")
    _create_directories()
    if splash: app.processEvents()

    # ── Step 3: database ──────────────────────────────────────────────────────
    log.info("startup: initialising database")
    _init_database()
    if splash: app.processEvents()

    # ── Step 4: preferences ───────────────────────────────────────────────────
    log.info("startup: loading preferences")
    _load_preferences()
    if splash: app.processEvents()

    # ── Step 6: main window ───────────────────────────────────────────────────
    log.info("startup: building main window")
    from ui.main_window import MainWindow
    window = MainWindow()

    if splash:
        splash.finish(window)

    window.show()
    log.info("startup: complete — main window displayed")

    exit_code = app.exec_()

    # ── Step 7: clean exit ────────────────────────────────────────────────────
    _on_clean_exit()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())