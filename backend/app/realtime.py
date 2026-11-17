from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class RealtimeSession:
    websocket: WebSocket
    user_id: str
    name: str
    role: str
    client_id: str
    task_id: str | None = None


class RealtimeManager:
    def __init__(self) -> None:
        self.sessions: dict[WebSocket, RealtimeSession] = {}

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
        await self.broadcast({
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
