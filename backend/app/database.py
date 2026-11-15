from __future__ import annotations

import json
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


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = RLock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
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
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO boards(id, name, created_at) VALUES (?, ?, ?)",
                (DEFAULT_BOARD["id"], DEFAULT_BOARD["name"], DEFAULT_BOARD["createdAt"]),
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

    def set_setting(self, key: str, value: Any, connection: sqlite3.Connection | None = None) -> None:
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

