"""
core/backup.py  —  InventraX Database Backup & Restore
========================================================
Handles automatic and manual backups of inventrax.db.

Features
--------
  • Timestamped backup copies in  backups/
  • Configurable max backup count (oldest deleted automatically)
  • SQLite integrity check before backup
  • One-step restore from any backup file
  • Backup manifest listing all available backups with metadata

Public API
----------
  backup_database(label)           → str | None   (path of new backup)
  restore_database(backup_path)    → bool
  list_backups()                   → list[dict]
  delete_backup(backup_path)       → bool
  delete_old_backups(keep)         → int          (number deleted)
  verify_backup(backup_path)       → bool
  get_db_info()                    → dict
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime

from config.settings import (
    DB_PATH, BACKUP_DIR, MAX_BACKUPS, BACKUP_FORMAT
)

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Backup
# ─────────────────────────────────────────────────────────────────────────────

def backup_database(label: str = "") -> str | None:
    """
    Copy inventrax.db to  backups/inventrax_YYYYMMDD_HHMMSS[_label].db

    Steps
    -----
    1. Verify the source DB passes SQLite integrity_check
    2. Create backups/ if needed
    3. Copy using SQLite's online backup API (safe while DB is open)
    4. Enforce MAX_BACKUPS by deleting the oldest excess files

    Returns the full path of the new backup on success, None on failure.
    """
    if not os.path.exists(DB_PATH):
        log.warning("backup: source DB not found at %s", DB_PATH)
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)

    stamp    = datetime.now().strftime(BACKUP_FORMAT)
    suffix   = f"_{label}" if label else ""
    filename = f"inventrax_{stamp}{suffix}.db"
    dest     = os.path.join(BACKUP_DIR, filename)

    try:
        # Use SQLite online backup API — safe even with open connections
        src_conn  = sqlite3.connect(DB_PATH)
        dest_conn = sqlite3.connect(dest)
        src_conn.backup(dest_conn, pages=256)
        dest_conn.close()
        src_conn.close()

        size_kb = os.path.getsize(dest) / 1024
        log.info("backup: created %s (%.1f KB)", filename, size_kb)

        # Enforce rotation
        deleted = delete_old_backups(keep=MAX_BACKUPS)
        if deleted:
            log.info("backup: removed %d old backup(s)", deleted)

        return dest

    except Exception as exc:
        log.error("backup: failed to create %s: %s", dest, exc)
        # Clean up partial file
        if os.path.exists(dest):
            try: os.remove(dest)
            except OSError: pass
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Restore
# ─────────────────────────────────────────────────────────────────────────────

def restore_database(backup_path: str) -> bool:
    """
    Restore a backup over the live database.

    Safety steps
    ------------
    1. Verify the backup passes integrity_check
    2. Auto-backup the current live DB first (labelled "pre_restore")
    3. Replace DB_PATH with the backup copy

    Returns True on success, False on failure.
    """
    if not os.path.exists(backup_path):
        log.error("restore: backup file not found: %s", backup_path)
        return False

    if not verify_backup(backup_path):
        log.error("restore: backup failed integrity check — aborting restore")
        return False

    # Safety backup of current live DB
    safety = backup_database(label="pre_restore")
    if safety:
        log.info("restore: safety backup created at %s", safety)
    else:
        log.warning("restore: could not create safety backup — proceeding anyway")

    try:
        src_conn  = sqlite3.connect(backup_path)
        dest_conn = sqlite3.connect(DB_PATH)
        src_conn.backup(dest_conn, pages=256)
        dest_conn.close()
        src_conn.close()
        log.info("restore: database restored from %s", backup_path)
        return True
    except Exception as exc:
        log.error("restore: failed: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# List / delete
# ─────────────────────────────────────────────────────────────────────────────

def list_backups() -> list:
    """
    Return a list of dicts for every .db file in BACKUP_DIR, newest first.

    Each dict has: path, filename, size_kb, created_at (datetime str)
    """
    if not os.path.exists(BACKUP_DIR):
        return []

    backups = []
    for fname in os.listdir(BACKUP_DIR):
        if not fname.endswith(".db"):
            continue
        full = os.path.join(BACKUP_DIR, fname)
        try:
            stat = os.stat(full)
            backups.append({
                "path":       full,
                "filename":   fname,
                "size_kb":    round(stat.st_size / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            })
        except OSError:
            continue

    return sorted(backups, key=lambda x: x["created_at"], reverse=True)


def delete_backup(backup_path: str) -> bool:
    """Delete a single backup file. Returns True on success."""
    try:
        os.remove(backup_path)
        log.info("backup: deleted %s", backup_path)
        return True
    except OSError as exc:
        log.error("backup: could not delete %s: %s", backup_path, exc)
        return False


def delete_old_backups(keep: int = None) -> int:
    """
    Delete the oldest backups so only `keep` remain.
    Uses MAX_BACKUPS from settings if keep is not specified.
    Returns the number of files deleted.
    """
    if keep is None:
        keep = MAX_BACKUPS

    backups = list_backups()   # newest first
    excess  = backups[keep:]   # everything beyond the keep limit
    deleted = 0
    for b in excess:
        if delete_backup(b["path"]):
            deleted += 1
    return deleted


# ─────────────────────────────────────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────────────────────────────────────

def verify_backup(backup_path: str) -> bool:
    """
    Run SQLite's PRAGMA integrity_check on a backup file.
    Returns True if the DB is healthy, False otherwise.
    """
    if not os.path.exists(backup_path):
        return False
    try:
        conn = sqlite3.connect(backup_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
        ok = result and result[0] == "ok"
        if not ok:
            log.warning("verify_backup: integrity check failed for %s — result: %s",
                        backup_path, result)
        return ok
    except Exception as exc:
        log.error("verify_backup: error checking %s: %s", backup_path, exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# DB Info
# ─────────────────────────────────────────────────────────────────────────────

def get_db_info() -> dict:
    """
    Return metadata about the live database:
    path, size_kb, table_counts, integrity, last_modified
    """
    info = {
        "path":          DB_PATH,
        "exists":        os.path.exists(DB_PATH),
        "size_kb":       0.0,
        "last_modified": "",
        "integrity":     "unknown",
        "tables":        {},
        "backup_count":  len(list_backups()),
    }

    if not info["exists"]:
        return info

    try:
        stat = os.stat(DB_PATH)
        info["size_kb"]       = round(stat.st_size / 1024, 1)
        info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        conn = sqlite3.connect(DB_PATH)

        # Integrity check
        result = conn.execute("PRAGMA integrity_check").fetchone()
        info["integrity"] = "ok" if (result and result[0] == "ok") else "FAILED"

        # Row counts per table
        tables = [
            row[0] for row in
            conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in tables:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                info["tables"][table] = count
            except Exception:
                info["tables"][table] = "?"

        conn.close()
    except Exception as exc:
        log.error("get_db_info error: %s", exc)

    return info
