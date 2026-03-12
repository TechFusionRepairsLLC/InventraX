"""
core/prefs.py  —  InventraX User Preference Persistence
=========================================================
Saves and restores APP_SETTINGS (theme, font size, low-stock threshold,
window size, etc.) to/from  config/user_prefs.json  between sessions.

Public API
----------
  load_prefs()          → dict   (reads JSON, fills missing keys from defaults)
  save_prefs()          → bool   (writes current APP_SETTINGS to JSON)
  apply_prefs(prefs)    → None   (pushes prefs dict into main_window globals)
  reset_prefs()         → bool   (deletes JSON, reverts to APP_DEFAULTS)
  get_pref(key, default)→ any
  set_pref(key, value)  → bool
"""

import json
import logging
import os
from typing import Any

from config.settings import PREFS_PATH, APP_DEFAULTS

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Load / Save
# ─────────────────────────────────────────────────────────────────────────────

def load_prefs() -> dict:
    """
    Read user_prefs.json.  Any key missing from the file is filled in from
    APP_DEFAULTS so callers always receive a complete settings dict.
    Returns APP_DEFAULTS verbatim if the file doesn't exist yet.
    """
    prefs = dict(APP_DEFAULTS)          # start with a full default copy

    if not os.path.exists(PREFS_PATH):
        log.info("prefs: no saved preferences found — using defaults")
        return prefs

    try:
        with open(PREFS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)

        if not isinstance(saved, dict):
            log.warning("prefs: corrupt preferences file — using defaults")
            return prefs

        # Merge: saved values override defaults; extra unknown keys are ignored
        for key in APP_DEFAULTS:
            if key in saved:
                prefs[key] = saved[key]

        log.info("prefs: loaded from %s", PREFS_PATH)
        return prefs

    except (json.JSONDecodeError, OSError) as exc:
        log.warning("prefs: could not read %s (%s) — using defaults", PREFS_PATH, exc)
        return prefs


def save_prefs() -> bool:
    """
    Write the current APP_SETTINGS dict from main_window to user_prefs.json.
    Safe to call at any time — creates the file if it doesn't exist.
    Returns True on success.
    """
    try:
        from ui.main_window import APP_SETTINGS
        _write_prefs(APP_SETTINGS)
        log.info("prefs: saved to %s", PREFS_PATH)
        return True
    except ImportError:
        log.warning("prefs: could not import APP_SETTINGS from main_window")
        return False
    except Exception as exc:
        log.error("prefs: save failed: %s", exc)
        return False


def _write_prefs(data: dict) -> None:
    """Internal — write a dict to PREFS_PATH as formatted JSON."""
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def apply_prefs(prefs: dict) -> None:
    """
    Push a loaded prefs dict into main_window's APP_SETTINGS and COLORS
    so the theme and all settings take effect before the window is shown.

    Called by Main.py after load_prefs() and before MainWindow() is created.
    Safe to call even if main_window hasn't been imported yet — it imports
    lazily so the module-level dicts exist.
    """
    try:
        import ui.main_window as mw

        # Update APP_SETTINGS in-place (keeps the same dict object)
        for key, value in prefs.items():
            if key in mw.APP_SETTINGS:
                mw.APP_SETTINGS[key] = value

        # Apply theme colours
        theme_name = prefs.get("theme", "Teal Dark")
        if theme_name in mw.THEMES:
            mw.COLORS.clear()
            mw.COLORS.update(mw.THEMES[theme_name])
        else:
            log.warning("prefs: unknown theme '%s' — keeping current", theme_name)

        # Sync LOW_STOCK_THRESHOLD module global
        mw.LOW_STOCK_THRESHOLD = prefs.get(
            "low_stock_threshold", mw.LOW_STOCK_THRESHOLD
        )

        log.info("prefs: applied (theme=%s, font=%spt, low_stock=%s)",
                 theme_name,
                 prefs.get("font_size", 10),
                 prefs.get("low_stock_threshold", 5))

    except Exception as exc:
        log.warning("prefs: could not apply preferences: %s", exc)


def reset_prefs() -> bool:
    """
    Delete user_prefs.json and reset APP_SETTINGS to APP_DEFAULTS.
    Returns True on success.
    """
    try:
        if os.path.exists(PREFS_PATH):
            os.remove(PREFS_PATH)
            log.info("prefs: reset — deleted %s", PREFS_PATH)
        apply_prefs(dict(APP_DEFAULTS))
        return True
    except Exception as exc:
        log.error("prefs: reset failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Single-key helpers (used by Settings dialog for live updates)
# ─────────────────────────────────────────────────────────────────────────────

def get_pref(key: str, default: Any = None) -> Any:
    """Read one preference from the saved file (or return default)."""
    prefs = load_prefs()
    return prefs.get(key, default)


def set_pref(key: str, value: Any) -> bool:
    """
    Update a single preference key and write the file immediately.
    Also updates APP_SETTINGS in main_window if it's already imported.
    Returns True on success.
    """
    try:
        prefs = load_prefs()
        prefs[key] = value
        _write_prefs(prefs)

        # Live update if main_window is already loaded
        try:
            import ui.main_window as mw
            if key in mw.APP_SETTINGS:
                mw.APP_SETTINGS[key] = value
        except ImportError:
            pass

        log.debug("prefs: set %s = %r", key, value)
        return True
    except Exception as exc:
        log.error("prefs: set_pref failed (%s=%r): %s", key, value, exc)
        return False
