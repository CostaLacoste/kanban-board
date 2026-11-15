from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .database import Database
from .models import (
    AttachmentOut,
    AutomationSettings,
    BatchTaskUpdate,
    BoardCreate,
    BoardOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    WorkspaceOut,
    WorkspacePayload,
    utc_now,
)


WORKSPACE_SETTINGS = (
    "activeBoardId",
    "columns",
    "templates",
    "members",
    "activity",
    "accessibility",
    "theme",
    "language",
    "sort",
    "automations",
)


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_boards(self) -> list[dict[str, Any]]:
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute("SELECT id, name, created_at FROM boards ORDER BY created_at").fetchall()
        return [{"id": row["id"], "name": row["name"], "createdAt": row["created_at"]} for row in rows]

    def board_exists(self, board_id: str, connection: sqlite3.Connection | None = None) -> bool:
        if connection is not None:
            return connection.execute("SELECT 1 FROM boards WHERE id = ?", (board_id,)).fetchone() is not None
        with self.database._lock, self.database.connect() as owned_connection:
            return self.board_exists(board_id, owned_connection)

    def create_board(self, data: BoardCreate) -> dict[str, Any]:
        board = {"id": str(uuid4()), "name": data.name, "createdAt": utc_now()}
        with self.database._lock, self.database.connect() as connection:
            connection.execute(
                "INSERT INTO boards(id, name, created_at) VALUES (?, ?, ?)",
                (board["id"], board["name"], board["createdAt"]),
            )
        return board

    def update_board(self, board_id: str, name: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            cursor = connection.execute("UPDATE boards SET name = ? WHERE id = ?", (name, board_id))
            row = connection.execute(
                "SELECT id, name, created_at FROM boards WHERE id = ?", (board_id,)
            ).fetchone()
        if cursor.rowcount == 0 or row is None:
            return None
        return {"id": row["id"], "name": row["name"], "createdAt": row["created_at"]}

    def delete_board(self, board_id: str) -> bool | None:
        with self.database._lock, self.database.connect() as connection:
            exists = connection.execute("SELECT 1 FROM boards WHERE id = ?", (board_id,)).fetchone()
            if exists is None:
                return False
            count = connection.execute("SELECT COUNT(*) AS count FROM boards").fetchone()["count"]
            if count <= 1:
                return None
            cursor = connection.execute("DELETE FROM boards WHERE id = ?", (board_id,))
        return cursor.rowcount > 0

    def _attachment_metadata(self, connection: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT id, name, media_type, size, created_at FROM attachments WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["media_type"],
                "size": row["size"],
                "url": f"/api/v1/attachments/{row['id']}",
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def _task_from_row(self, connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        task = json.loads(row["payload"])
        task["attachments"] = self._attachment_metadata(connection, row["id"])
        return task

    def list_tasks(self, board_id: str | None = None, archived: bool | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if board_id:
            clauses.append("board_id = ?")
            values.append(board_id)
        if archived is not None:
            clauses.append("archived = ?")
            values.append(int(archived))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.database._lock, self.database.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM tasks {where} ORDER BY board_id, status, sort_order, updated_at",
                values,
            ).fetchall()
            return [self._task_from_row(connection, row) for row in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._task_from_row(connection, row) if row else None

    def _save_task(self, connection: sqlite3.Connection, task: dict[str, Any]) -> None:
        connection.execute(
            """
            INSERT INTO tasks(id, board_id, status, archived, sort_order, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                board_id = excluded.board_id,
                status = excluded.status,
                archived = excluded.archived,
                sort_order = excluded.sort_order,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                task["id"],
                task["boardId"],
                task["status"],
                int(task["archived"]),
                task["order"],
                json.dumps(task, ensure_ascii=False, separators=(",", ":")),
                utc_now(),
            ),
        )

    def _apply_automations(self, connection: sqlite3.Connection, task: dict[str, Any]) -> dict[str, Any]:
        row = connection.execute("SELECT value FROM settings WHERE key = 'automations'").fetchone()
        try:
            rules = json.loads(row["value"]) if row else {}
        except json.JSONDecodeError:
            rules = {}
        today = datetime.now(timezone.utc).date().isoformat()
        next_task = {**task}
        if (
            rules.get("overdueHigh")
            and next_task.get("deadline")
            and next_task["deadline"] < today
            and next_task.get("status") != "done"
        ):
            next_task["priority"] = "high"
        checklist = next_task.get("checklist") or []
        if rules.get("checklistDone") and checklist and all(item.get("done") for item in checklist):
            next_task["status"] = "done"
            next_task["completedAt"] = next_task.get("completedAt") or utc_now()
        tags = list(next_task.get("tags") or [])
        if rules.get("dueTodayTag") and next_task.get("deadline") == today and "today" not in tags:
            next_task["tags"] = [*tags, "today"][:5]
        return next_task

    def create_task(self, data: TaskCreate) -> dict[str, Any] | None:
        task = data.model_dump(by_alias=True, mode="json")
        task["id"] = data.id or str(uuid4())
        task["createdAt"] = data.created_at or utc_now()
        task["completedAt"] = data.completed_at or (utc_now() if data.status == "done" else "")
        task.pop("attachments", None)
        with self.database._lock, self.database.connect() as connection:
            if not self.board_exists(task["boardId"], connection):
                return None
            task = self._apply_automations(connection, task)
            self._save_task(connection, task)
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task["id"],)).fetchone()
            return self._task_from_row(connection, row)

    def update_task(self, task_id: str, data: TaskUpdate) -> dict[str, Any] | None | bool:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            current = json.loads(row["payload"])
            changes = data.model_dump(exclude_unset=True, by_alias=True, mode="json")
            next_task = {**current, **changes}
            if not self.board_exists(next_task["boardId"], connection):
                return False
            if current["status"] != "done" and next_task["status"] == "done":
                next_task["completedAt"] = next_task.get("completedAt") or utc_now()
            elif next_task["status"] != "done":
                next_task["completedAt"] = ""
            next_task = self._apply_automations(connection, next_task)
            self._save_task(connection, next_task)
            saved = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._task_from_row(connection, saved)

    def delete_task(self, task_id: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return cursor.rowcount > 0

    def batch_update(self, data: BatchTaskUpdate) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        with self.database._lock, self.database.connect() as connection:
            for task_id in dict.fromkeys(data.ids):
                row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                if row is None:
                    continue
                task = json.loads(row["payload"])
                if data.status is not None:
                    task["status"] = data.status
                    task["completedAt"] = task.get("completedAt") or utc_now() if data.status == "done" else ""
                if data.priority is not None:
                    task["priority"] = data.priority
                if data.archived is not None:
                    task["archived"] = data.archived
                task = self._apply_automations(connection, task)
                self._save_task(connection, task)
                saved = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                updated.append(self._task_from_row(connection, saved))
        return updated

    def start_timer(self, task_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            task = json.loads(row["payload"])
            if not task.get("timerStartedAt"):
                task["timerStartedAt"] = utc_now()
                self._save_task(connection, task)
            saved = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._task_from_row(connection, saved)

    def stop_timer(self, task_id: str) -> dict[str, Any] | None:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            task = json.loads(row["payload"])
            started_at = task.get("timerStartedAt")
            if started_at:
                try:
                    started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    elapsed = max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
                except (TypeError, ValueError):
                    elapsed = 0
                task["timeSpentSeconds"] = int(task.get("timeSpentSeconds") or 0) + elapsed
                task["timerStartedAt"] = ""
                self._save_task(connection, task)
            saved = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._task_from_row(connection, saved)

    def add_attachment(
        self, task_id: str, name: str, media_type: str, content: bytes
    ) -> dict[str, Any] | None:
        attachment_id = str(uuid4())
        created_at = utc_now()
        with self.database._lock, self.database.connect() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone() is None:
                return None
            connection.execute(
                "INSERT INTO attachments(id, task_id, name, media_type, size, content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (attachment_id, task_id, name, media_type, len(content), content, created_at),
            )
        return {
            "id": attachment_id,
            "name": name,
            "type": media_type,
            "size": len(content),
            "url": f"/api/v1/attachments/{attachment_id}",
            "createdAt": created_at,
        }

    def attachment_count(self, task_id: str) -> int:
        with self.database._lock, self.database.connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM attachments WHERE task_id = ?", (task_id,)
            ).fetchone()
        return row["count"]

    def get_attachment(self, attachment_id: str) -> sqlite3.Row | None:
        with self.database._lock, self.database.connect() as connection:
            return connection.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()

    def delete_attachment(self, attachment_id: str) -> bool:
        with self.database._lock, self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        return cursor.rowcount > 0

    def get_automations(self) -> dict[str, Any]:
        return self.database.get_setting(
            "automations", AutomationSettings().model_dump(by_alias=True, mode="json")
        )

    def set_automations(self, settings: AutomationSettings) -> dict[str, Any]:
        value = settings.model_dump(by_alias=True, mode="json")
        with self.database._lock, self.database.connect() as connection:
            self.database.set_setting("automations", value, connection)
            rows = connection.execute("SELECT * FROM tasks").fetchall()
            for row in rows:
                task = self._apply_automations(connection, json.loads(row["payload"]))
                self._save_task(connection, task)
        return value

    def get_workspace(self) -> dict[str, Any]:
        defaults = {
            "activeBoardId": "default",
            "columns": [],
            "templates": [],
            "members": [],
            "activity": [],
            "accessibility": {},
            "theme": "classic",
            "language": "ru",
            "sort": "manual",
            "automations": AutomationSettings().model_dump(by_alias=True),
        }
        values = {key: self.database.get_setting(key, default) for key, default in defaults.items()}
        return {
            "version": 4,
            **values,
            "boards": self.list_boards(),
            "tasks": self.list_tasks(),
        }

    def replace_workspace(self, payload: WorkspacePayload) -> dict[str, Any]:
        boards = [board.model_dump(by_alias=True, mode="json") for board in payload.boards]
        tasks = [task.model_dump(by_alias=True, mode="json") for task in payload.tasks]
        board_ids = {board["id"] for board in boards}
        task_ids = [task.get("id") for task in tasks if task.get("id")]
        if (
            not boards
            or len(board_ids) != len(boards)
            or len(task_ids) != len(set(task_ids))
            or any(task["boardId"] not in board_ids for task in tasks)
        ):
            raise ValueError("Workspace structure is invalid")
        with self.database._lock, self.database.connect() as connection:
            connection.execute("DELETE FROM attachments")
            connection.execute("DELETE FROM tasks")
            connection.execute("DELETE FROM boards")
            for board in boards:
                connection.execute(
                    "INSERT INTO boards(id, name, created_at) VALUES (?, ?, ?)",
                    (board["id"], board["name"], board["createdAt"]),
                )
            for task in tasks:
                task["id"] = task.get("id") or str(uuid4())
                task["createdAt"] = task.get("createdAt") or utc_now()
                task["completedAt"] = task.get("completedAt") or (utc_now() if task["status"] == "done" else "")
                self._save_task(connection, task)
            settings = payload.model_dump(by_alias=True, mode="json", exclude={"boards", "tasks", "version"})
            for key, value in settings.items():
                self.database.set_setting(key, value, connection)
        return self.get_workspace()

