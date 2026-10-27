"""Create a consistent SQLite backup using SQLite's online backup API."""

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "instance" / "ats_analyzer.db"
DESTINATION_DIR = ROOT / "backup"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE,
                        help="SQLite database to back up (default: instance/ats_analyzer.db)")
    parser.add_argument("--output", type=Path,
                        help="optional destination path; otherwise a timestamped file is made in backup/")
    args = parser.parse_args()
    source_path = args.source.expanduser().resolve()
    if not source_path.is_file():
        parser.error(f"database not found: {source_path}")
    DESTINATION_DIR.mkdir(exist_ok=True)
    destination = (args.output.expanduser().resolve() if args.output else
                   DESTINATION_DIR / f"{source_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    if destination == source_path:
        parser.error("source and destination must be different files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    print(f"Backup created: {destination}")


if __name__ == "__main__":
    main()
