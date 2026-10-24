"""Create a consistent SQLite backup using SQLite's online backup API."""

import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "instance" / "ats_analyzer.db"
DESTINATION_DIR = ROOT / "backup"


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Database not found: {SOURCE}. Start the app and create an account first.")
    DESTINATION_DIR.mkdir(exist_ok=True)
    destination = DESTINATION_DIR / f"ats_analyzer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    with sqlite3.connect(SOURCE) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    print(f"Backup created: {destination}")


if __name__ == "__main__":
    main()
