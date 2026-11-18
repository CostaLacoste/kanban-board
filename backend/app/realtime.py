from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import WebSocket

from .models import utc_now
from .repository import Repository


@dataclass(slots=True)
class RealtimeSession:
    websocket: WebSocket
    user_id: str
    name: str
    role: str
    client_id: str
    task_id: str | None = None


class RealtimeManager:
    def __init__(self, repository: Repository) -> None:
        self.sessions: dict[WebSocket, RealtimeSession] = {}
        self.repository = repository
        self.instance_id = str(uuid4())
        self.cursor = utc_now()
        self._stopped = False
        self.remote_presence: dict[tuple[str, str], list[dict[str, str]]] = {}

    async def run_bus(self) -> None:
        """Relay durable database events emitted by other API replicas."""
        while not self._stopped:
            await asyncio.sleep(0.5)
            events = await asyncio.to_thread(
                self.repository.realtime_events_after, self.cursor, self.instance_id
            )
            for event in events:
                self.cursor = max(self.cursor, event["createdAt"])
                payload = event["payload"]
                if payload.get("type") == "presence.updated":
                    task_id = str(payload.get("taskId") or "")
                    self.remote_presence[(event["instanceId"], task_id)] = payload.get("users") or []
                    remote_users = [
                        user for (source, task), users in self.remote_presence.items()
                        if task == task_id for user in users
                    ]
                    payload = {**payload, "users": [*self.presence(task_id), *remote_users]}
                await self.broadcast(payload)

    def stop(self) -> None:
        self._stopped = True

    async def connect(self, websocket: WebSocket, actor: Any, client_id: str) -> RealtimeSession:
        await websocket.accept()
        session = RealtimeSession(
            websocket=websocket,
            user_id=actor.id,
            name=actor.name,
            role=actor.role,
            client_id=client_id,
        )
        self.sessions[websocket] = session
        return session

    async def disconnect(self, websocket: WebSocket) -> None:
        session = self.sessions.pop(websocket, None)
        if session and session.task_id:
            await self.broadcast_presence(session.task_id)

    def presence(self, task_id: str | None = None) -> list[dict[str, str]]:
        unique: dict[tuple[str, str], dict[str, str]] = {}
        for session in self.sessions.values():
            if task_id is not None and session.task_id != task_id:
                continue
            unique[(session.user_id, session.client_id)] = {
                "userId": session.user_id,
                "name": session.name,
                "role": session.role,
                "clientId": session.client_id,
                "taskId": session.task_id or "",
            }
        return list(unique.values())

    async def update_presence(self, websocket: WebSocket, task_id: str | None) -> None:
        session = self.sessions.get(websocket)
        if session is None:
            return
        previous_task_id = session.task_id
        session.task_id = task_id or None
        if previous_task_id and previous_task_id != session.task_id:
            await self.broadcast_presence(previous_task_id)
        if session.task_id:
            await self.broadcast_presence(session.task_id)

    async def broadcast_presence(self, task_id: str) -> None:
        await self.publish({
            "type": "presence.updated",
            "taskId": task_id,
            "users": self.presence(task_id),
        })

    async def broadcast(self, message: dict, exclude: WebSocket | None = None) -> None:
        dead: list[WebSocket] = []
        for connection in list(self.sessions):
            if connection is exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.sessions.pop(connection, None)

    async def publish(self, message: dict, exclude: WebSocket | None = None) -> None:
        await asyncio.to_thread(self.repository.publish_realtime_event, self.instance_id, message)
        await self.broadcast(message, exclude=exclude)
