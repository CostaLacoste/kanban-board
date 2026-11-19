from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.platform import _totp
from test_api import auth_headers, client, register_user  # noqa: F401


def first_workspace(client: TestClient, token: str) -> dict:
    response = client.get("/api/v1/workspaces", headers=auth_headers(token))
    assert response.status_code == 200
    return response.json()[0]


def test_workspace_isolation_snapshots_and_my_tasks(client: TestClient) -> None:
    owner = register_user(client, "tenant-owner@example.com", "Tenant Owner")
    outsider = register_user(client, "tenant-outsider@example.com", "Outsider")
    headers = auth_headers(owner["accessToken"])
    workspace = first_workspace(client, owner["accessToken"])
    outsider_workspace = first_workspace(client, outsider["accessToken"])
    assert workspace["id"] != outsider_workspace["id"]
    assert client.get(
        f"/api/v1/workspaces/{workspace['id']}/snapshot",
        headers=auth_headers(outsider["accessToken"]),
    ).status_code == 403

    snapshot = client.get(f"/api/v1/workspaces/{workspace['id']}/snapshot", headers=headers).json()
    snapshot["tasks"].append({
        "id": "mine", "title": "My tenant task", "description": "", "status": "todo",
        "priority": "high", "deadline": "2030-01-01", "boardId": "default", "order": 0,
        "archived": False, "recurrence": "none", "tags": [], "checklist": [], "dependsOn": [],
        "assignee": "tenant-owner@example.com", "color": "default", "cover": "", "comments": [],
        "estimatedMinutes": 30, "timeSpentSeconds": 0, "timerStartedAt": "", "startDate": "",
        "goalId": "", "milestone": False, "customValues": {}, "createdAt": "2030-01-01T00:00:00Z",
        "completedAt": "",
    })
    saved = client.put(
        f"/api/v1/workspaces/{workspace['id']}/snapshot",
        headers={**headers, "If-Match": '"0"'}, json=snapshot,
    )
    assert saved.status_code == 200
    mine = client.get("/api/v1/my/tasks", headers=headers).json()
    assert mine[0]["workspaceId"] == workspace["id"]
    assert mine[0]["title"] == "My tenant task"


def test_security_totp_email_and_passkey_options(client: TestClient) -> None:
    account = register_user(client, "secure-platform@example.com", "Secure")
    headers = auth_headers(account["accessToken"])
    setup = client.post("/api/v1/security/totp/setup", headers=headers)
    assert setup.status_code == 200
    code = _totp(setup.json()["secret"])
    assert client.post("/api/v1/security/totp/enable", headers=headers, json={"code": code}).json()["enabled"]
    assert client.post(
        "/api/v1/auth/login", json={"email": "secure-platform@example.com", "password": "strong-password"}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "secure-platform@example.com", "password": "strong-password", "otp": _totp(setup.json()["secret"])},
    ).status_code == 200

    verification = client.post("/api/v1/security/email/send-verification", headers=headers).json()
    assert client.post(
        "/api/v1/auth/email/verify", json={"token": verification["verificationToken"]}
    ).json()["verified"]
    options = client.post("/api/v1/security/passkeys/registration/start", headers=headers)
    assert options.status_code == 200
    assert options.json()["publicKey"]["challenge"]


def test_platform_fields_sharing_operations_assistant_and_audit(client: TestClient) -> None:
    account = register_user(client, "platform-owner@example.com", "Platform Owner")
    headers = auth_headers(account["accessToken"])
    workspace = first_workspace(client, account["accessToken"])
    workspace_id = workspace["id"]
    field = client.post("/api/v1/custom-fields", headers=headers, json={
        "workspaceId": workspace_id, "name": "Cost", "fieldType": "number", "options": [], "required": False,
    })
    assert field.status_code == 201
    assert client.get(f"/api/v1/custom-fields?workspaceId={workspace_id}", headers=headers).json()[0]["name"] == "Cost"

    share = client.post("/api/v1/public-shares", headers=headers, json={
        "workspaceId": workspace_id, "boardId": "default", "mode": "form",
    }).json()
    public = client.get(f"/api/v1/public/{share['token']}")
    assert public.status_code == 200
    submitted = client.post(f"/api/v1/public/{share['token']}/submit", json={
        "title": "Public request", "description": "From form", "values": {field.json()["id"]: 42},
    })
    assert submitted.status_code == 201
    assert submitted.json()["customValues"][field.json()["id"]] == 42

    operation = client.post("/api/v1/collaboration/operations", headers=headers, json={
        "workspaceId": workspace_id, "taskId": submitted.json()["id"], "clientId": "test",
        "field": "description", "operation": {"kind": "set", "value": "Updated"}, "lamport": 1,
    })
    assert operation.status_code == 201
    assert client.get(f"/api/v1/tasks/{submitted.json()['id']}/operations", headers=headers).json()[0]["lamport"] == 1
    assistant = client.post("/api/v1/assistant", headers=headers, json={
        "action": "checklist", "workspaceId": workspace_id, "text": "Plan work. Build feature. Verify release.",
    }).json()
    assert len(assistant["checklist"]) == 3
    audit = client.get(f"/api/v1/workspaces/{workspace_id}/audit", headers=headers).json()
    assert any(item["resource"] == "/api/v1/custom-fields" for item in audit)


def test_github_webhook_creates_a_task(client: TestClient) -> None:
    account = register_user(client, "github-owner@example.com", "GitHub Owner")
    headers = auth_headers(account["accessToken"])
    workspace = first_workspace(client, account["accessToken"])
    integration = client.post("/api/v1/integrations", headers=headers, json={
        "workspaceId": workspace["id"], "kind": "github", "name": "Issues", "config": {},
    }).json()
    payload = json.dumps({
        "action": "opened", "issue": {"id": 7, "title": "Fix sync", "body": "Details", "html_url": "https://github.test/issues/7"},
    }).encode()
    signature = "sha256=" + hmac.new(integration["secret"].encode(), payload, hashlib.sha256).hexdigest()
    response = client.post(
        f"/api/v1/integrations/github/webhook/{integration['id']}", content=payload,
        headers={"Content-Type": "application/json", "X-GitHub-Event": "issues", "X-Hub-Signature-256": signature},
    )
    assert response.status_code == 200
    snapshot = client.get(
        f"/api/v1/workspaces/{workspace['id']}/snapshot", headers=headers,
    ).json()
    assert snapshot["tasks"][0]["title"] == "Fix sync"
