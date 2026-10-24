"""Restore a SQLite backup into a separate copy without overwriting the live DB."""

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="Path to a .db backup created by backup_database.py")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "instance" / "ats_analyzer_restored.db",
        help="Restore destination; defaults to a separate instance/ats_analyzer_restored.db copy",
    )
    parser.add_argument("--force", action="store_true", help="Replace the destination file if it already exists")
    args = parser.parse_args()
    source = args.backup.expanduser().resolve()
    destination = args.output.expanduser().resolve()
    if not source.is_file():
        parser.error(f"backup file does not exist: {source}")
    if source == destination:
        parser.error("backup and destination must be different files")
    if destination.exists() and not args.force:
        parser.error(f"destination exists: {destination}; choose another path or pass --force")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as db_source:
        integrity = db_source.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            parser.error(f"backup failed SQLite integrity check: {integrity}")
        with sqlite3.connect(destination) as db_target:
            db_source.backup(db_target)
    print(f"Restored a verified copy to: {destination}")


if __name__ == "__main__":
    main()
