from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent Flowboard SQLite backup")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = Settings.from_env().database_path
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or source.parent / "backups" / f"flowboard-{timestamp}.db"
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_db, sqlite3.connect(output) as backup_db:
        source_db.backup(backup_db)
    print(output.resolve())


if __name__ == "__main__":
    main()
