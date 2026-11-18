from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from app.database import Database


TABLES = (
    ("users", ("id",)),
    ("workspace_members", ("user_id",)),
    ("boards", ("id",)),
    ("settings", ("key",)),
    ("tasks", ("id",)),
    ("attachments", ("id",)),
    ("attachment_objects", ("attachment_id",)),
    ("api_tokens", ("id",)),
    ("saved_filters", ("id",)),
    ("notifications", ("id",)),
    ("webhooks", ("id",)),
    ("outbox", ("id",)),
    ("revisions", ("id",)),
    ("task_comments", ("id",)),
    ("comment_metadata", ("comment_id",)),
    ("comment_reactions", ("comment_id", "user_id", "emoji")),
    ("task_watchers", ("task_id", "user_id")),
    ("invitations", ("id",)),
    ("auth_sessions", ("id",)),
    ("password_resets", ("id",)),
    ("goals", ("id",)),
    ("jobs", ("id",)),
    ("realtime_events", ("id",)),
    ("schema_migrations", ("version",)),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy a Flowboard SQLite database to PostgreSQL")
    parser.add_argument("source", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit("SQLite source file not found")
    if not args.database_url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("Set DATABASE_URL or pass --database-url with a PostgreSQL URL")

    target = Database(Path("unused.db"), args.database_url)
    target.initialize()
    source = sqlite3.connect(args.source)
    source.row_factory = sqlite3.Row
    copied = 0
    try:
        with target.connect() as destination:
            for table, primary_keys in TABLES:
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                rows = source.execute(f'SELECT * FROM "{table}"').fetchall()
                if not rows:
                    continue
                columns = list(rows[0].keys())
                column_sql = ",".join(f'"{column}"' for column in columns)
                placeholders = ",".join("?" for _ in columns)
                updates = ",".join(
                    f'"{column}"=excluded."{column}"'
                    for column in columns
                    if column not in primary_keys
                )
                conflict = f'DO UPDATE SET {updates}' if updates else "DO NOTHING"
                conflict_columns = ",".join(f'"{column}"' for column in primary_keys)
                query = (
                    f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders}) '
                    f'ON CONFLICT({conflict_columns}) {conflict}'
                )
                destination.executemany(query, [tuple(row[column] for column in columns) for row in rows])
                copied += len(rows)
                print(f"{table}: {len(rows)}")
    finally:
        source.close()
    print(f"Copied {copied} rows")


if __name__ == "__main__":
    main()
