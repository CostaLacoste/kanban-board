from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore Flowboard from a SQLite backup")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    if not args.backup.is_file():
        raise SystemExit("Backup file not found")
    target = Settings.from_env().database_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.backup) as backup_db, sqlite3.connect(target) as target_db:
        backup_db.backup(target_db)
    print(target.resolve())


if __name__ == "__main__":
    main()
