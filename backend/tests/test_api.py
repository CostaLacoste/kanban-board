from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(database_path=tmp_path / "test.db", cors_origins=("http://localhost",))
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_default_board(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    boards = client.get("/api/v1/boards").json()
    assert boards == [
        {
            "id": "default",
            "name": "Основная доска",
            "createdAt": boards[0]["createdAt"],
        }
    ]


def test_board_crud_and_last_board_protection(client: TestClient) -> None:
    created = client.post("/api/v1/boards", json={"name": "Работа"})
    assert created.status_code == 201
    board_id = created.json()["id"]

    renamed = client.patch(f"/api/v1/boards/{board_id}", json={"name": "Команда"})
    assert renamed.json()["name"] == "Команда"
    assert client.delete(f"/api/v1/boards/{board_id}").status_code == 204
    assert client.delete("/api/v1/boards/default").status_code == 409


def test_task_crud_filters_and_batch_update(client: TestClient) -> None:
    created = client.post(
        "/api/v1/tasks",
        json={
            "title": "Подготовить релиз",
            "boardId": "default",
            "priority": "medium",
            "tags": ["Релиз", "релиз"],
            "estimatedMinutes": 60,
        },
    )
    assert created.status_code == 201
    task = created.json()
    assert task["tags"] == ["релиз"]
    assert task["estimatedMinutes"] == 60

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"status": "progress", "timeSpentSeconds": 120}
    )
    assert updated.json()["status"] == "progress"
    assert updated.json()["timeSpentSeconds"] == 120

    batch = client.patch(
        "/api/v1/tasks",
        json={"ids": [task["id"]], "status": "done", "priority": "high"},
    )
    assert batch.json()["updated"] == 1
    assert batch.json()["tasks"][0]["completedAt"]
    assert client.get("/api/v1/tasks", params={"boardId": "default", "archived": False}).json()[0]["priority"] == "high"
    assert client.delete(f"/api/v1/tasks/{task['id']}").status_code == 204


def test_rejects_task_for_unknown_board(client: TestClient) -> None:
    response = client.post("/api/v1/tasks", json={"title": "Ошибка", "boardId": "missing"})
    assert response.status_code == 422


def test_timer_start_and_stop(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "Таймер"}).json()
    started = client.post(f"/api/v1/tasks/{task['id']}/timer/start")
    assert started.status_code == 200
    assert started.json()["timerStartedAt"]
    stopped = client.post(f"/api/v1/tasks/{task['id']}/timer/stop")
    assert stopped.status_code == 200
    assert stopped.json()["timerStartedAt"] == ""
    assert stopped.json()["timeSpentSeconds"] >= 0


def test_attachment_upload_download_and_delete(client: TestClient) -> None:
    task = client.post("/api/v1/tasks", json={"title": "Документы"}).json()
    uploaded = client.post(
        f"/api/v1/tasks/{task['id']}/attachments",
        files={"file": ("brief.txt", b"Flowboard brief", "text/plain")},
    )
    assert uploaded.status_code == 201
    attachment = uploaded.json()
    assert attachment["name"] == "brief.txt"

    task_with_file = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task_with_file["attachments"][0]["id"] == attachment["id"]
    downloaded = client.get(attachment["url"])
    assert downloaded.content == b"Flowboard brief"
    assert client.delete(attachment["url"]).status_code == 204


def test_automations_and_workspace_roundtrip(client: TestClient) -> None:
    automations = {"overdueHigh": True, "checklistDone": True, "dueTodayTag": False}
    existing = client.post(
        "/api/v1/tasks",
        json={"title": "Просроченная задача", "deadline": "2000-01-01", "priority": "low"},
    ).json()
    assert client.put("/api/v1/automations", json=automations).json() == automations
    assert client.get(f"/api/v1/tasks/{existing['id']}").json()["priority"] == "high"

    automated = client.post(
        "/api/v1/tasks",
        json={
            "title": "Автоматическая задача",
            "deadline": "2000-01-01",
            "priority": "low",
            "checklist": [{"text": "Готово", "done": True}],
        },
    ).json()
    assert automated["priority"] == "high"
    assert automated["status"] == "done"
    assert automated["completedAt"]

    workspace = client.get("/api/v1/workspace").json()
    workspace["theme"] = "cyberpunk"
    workspace["language"] = "uk"
    workspace["automations"] = automations
    replaced = client.put("/api/v1/workspace", json=workspace)
    assert replaced.status_code == 200
    assert replaced.json()["theme"] == "cyberpunk"
    assert replaced.json()["language"] == "uk"
    assert replaced.json()["automations"] == automations


def register_user(client: TestClient, email: str, name: str = "User") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "name": name, "password": "strong-password"},
    )
    assert response.status_code == 201
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_roles_and_api_tokens(client: TestClient) -> None:
    owner = register_user(client, "owner@example.com", "Owner")
    editor = register_user(client, "editor@example.com", "Editor")
    assert owner["user"]["role"] == "owner"
    assert editor["user"]["role"] == "editor"

    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "strong-password"},
    )
    assert logged_in.status_code == 200
    owner_headers = auth_headers(logged_in.json()["accessToken"])
    assert client.get("/api/v1/auth/me", headers=owner_headers).json()["email"] == "owner@example.com"

    changed = client.put(
        "/api/v1/members",
        headers=owner_headers,
        json={"email": "editor@example.com", "role": "viewer"},
    )
    assert changed.json()["role"] == "viewer"
    viewer_headers = auth_headers(editor["accessToken"])
    assert client.post("/api/v1/boards", headers=viewer_headers, json={"name": "Forbidden"}).status_code == 403

    api_token = client.post(
        "/api/v1/auth/api-tokens", headers=owner_headers, json={"name": "CI"}
    ).json()
    assert api_token["token"].startswith("fb_")
    assert client.get("/api/v1/auth/me", headers=auth_headers(api_token["token"])).status_code == 200
    preferences = client.put(
        "/api/v1/notification-preferences",
        headers=owner_headers,
        json={"inAppEnabled": True, "pushEnabled": True, "emailEnabled": True},
    )
    assert preferences.status_code == 200
    assert preferences.json()["emailEnabled"] is True


def test_revision_conflict_history_search_and_notifications(client: TestClient) -> None:
    owner = register_user(client, "sync@example.com")
    headers = auth_headers(owner["accessToken"])
    client.post(
        "/api/v1/tasks",
        json={"title": "Найти отчёт", "tags": ["поиск"], "priority": "high"},
    )
    search = client.get("/api/v1/search/tasks", params={"q": "отчёт", "tag": "поиск"})
    assert search.status_code == 200
    assert search.json()[0]["title"] == "Найти отчёт"

    saved = client.post(
        "/api/v1/saved-filters",
        headers=headers,
        json={"name": "Важные", "query": {"priority": "high"}},
    )
    assert saved.status_code == 201
    assert len(client.get("/api/v1/saved-filters", headers=headers).json()) == 1

    workspace = client.get("/api/v1/workspace").json()
    first = client.put(
        "/api/v1/workspace", headers={**headers, "If-Match": '"0"'}, json=workspace
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 1
    conflict = client.put(
        "/api/v1/workspace", headers={**headers, "If-Match": '"0"'}, json=workspace
    )
    assert conflict.status_code == 409
    revisions = client.get("/api/v1/revisions").json()
    assert revisions[0]["revision"] == 1
    assert client.get("/api/v1/notifications", headers=headers).json()[0]["kind"] == "sync"


def test_webhooks_and_realtime(client: TestClient) -> None:
    owner = register_user(client, "hooks@example.com")
    headers = auth_headers(owner["accessToken"])
    webhook = client.post(
        "/api/v1/webhooks",
        headers=headers,
        json={"url": "https://example.com/flowboard", "events": ["workspace.updated"]},
    )
    assert webhook.status_code == 201
    assert len(client.get("/api/v1/webhooks", headers=headers).json()) == 1

    with client.websocket_connect(f"/api/v1/realtime?token={owner['accessToken']}") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "connected"
        assert "revision" in message

