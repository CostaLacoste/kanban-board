from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any

from .models import utc_now


DEFAULT_BOARD = {
    "id": "default",
    "name": "Основная доска",
    "createdAt": utc_now(),
}


def adapt_postgres_query(query: str) -> str:
    """Translate the small SQLite-compatible SQL subset used by the repository."""
    return query.replace("?", "%s")


def adapt_postgres_schema(statement: str) -> str:
    return re.sub(r"\bBLOB\b", "BYTEA", statement, flags=re.IGNORECASE)


class PostgresConnection:
    def __init__(self, raw_connection: Any) -> None:
        self.raw_connection = raw_connection

    def execute(self, query: str, values: Any = ()) -> Any:
        return self.raw_connection.execute(adapt_postgres_query(query), values)

    def executemany(self, query: str, values: Any) -> Any:
        return self.raw_connection.cursor().executemany(adapt_postgres_query(query), values)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.raw_connection.execute(adapt_postgres_schema(statement))

    def commit(self) -> None:
        self.raw_connection.commit()

    def rollback(self) -> None:
        self.raw_connection.rollback()

    def close(self) -> None:
        self.raw_connection.close()


class Database:
    def __init__(self, path: Path, database_url: str = "") -> None:
        self.path = path
        self.database_url = database_url.strip()
        self.provider = "postgresql" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        self._lock = RLock()

    @contextmanager
    def connect(self) -> Iterator[Any]:
        if self.provider == "postgresql":
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as error:
                raise RuntimeError("PostgreSQL requires psycopg; run `uv sync`") from error
            connection: Any = PostgresConnection(
                psycopg.connect(self.database_url, row_factory=dict_row)
            )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._lock, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS boards (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    board_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    sort_order REAL NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS tasks_board_idx
                    ON tasks(board_id, archived, status, sort_order);
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    content BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS attachments_task_idx ON attachments(task_id);
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspace_members (
                    user_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL CHECK(role IN ('owner', 'editor', 'viewer')),
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS api_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS saved_filters (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    query TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    read_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS webhooks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    events TEXT NOT NULL,
                    secret TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    id TEXT PRIMARY KEY,
                    webhook_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    delivered_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (webhook_id) REFERENCES webhooks(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL UNIQUE,
                    actor_id TEXT,
                    snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS notifications_user_idx ON notifications(user_id, read_at, created_at);
                CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(delivered_at, created_at);
                CREATE TABLE IF NOT EXISTS task_comments (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    user_id TEXT,
                    author TEXT NOT NULL,
                    body TEXT NOT NULL,
                    mentions TEXT NOT NULL DEFAULT '[]',
                    parent_id TEXT,
                    created_at TEXT NOT NULL,
                    edited_at TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    FOREIGN KEY (parent_id) REFERENCES task_comments(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS task_comments_task_idx
                    ON task_comments(task_id, created_at);
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO schema_migrations(version,applied_at) VALUES (1,?) ON CONFLICT(version) DO NOTHING", (utc_now(),)
            )
            connection.execute(
                "INSERT INTO schema_migrations(version,applied_at) VALUES (2,?) ON CONFLICT(version) DO NOTHING", (utc_now(),)
            )
            connection.execute(
                "INSERT INTO boards(id, name, created_at) VALUES (?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (DEFAULT_BOARD["id"], DEFAULT_BOARD["name"], DEFAULT_BOARD["createdAt"]),
            )
            connection.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES ('workspaceRevision', '0', ?) ON CONFLICT(key) DO NOTHING",
                (utc_now(),),
            )

    def get_setting(self, key: str, default: Any) -> Any:
        with self._lock, self.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return default

    def set_setting(self, key: str, value: Any, connection: Any | None = None) -> None:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        query = """
            INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """
        if connection is not None:
            connection.execute(query, (key, serialized, utc_now()))
            return
        with self._lock, self.connect() as owned_connection:
            owned_connection.execute(query, (key, serialized, utc_now()))

