from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Annotated, Any

import httpx

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from .auth import Actor, AuthService
from .config import Settings
from .integrations import process_jobs, send_email
from .platform import PlatformService
from .platform_models import (
    AssistantRequest,
    BoardPermissionUpdate,
    CollaborationOperation,
    CustomFieldCreate,
    EmailVerificationConfirm,
    IntegrationCreate,
    IntegrationMessage,
    PasskeyAuthenticationComplete,
    PasskeyAuthenticationStart,
    PasskeyRegistrationComplete,
    PublicFormSubmission,
    PublicShareCreate,
    PushSubscriptionCreate,
    TotpVerify,
    WorkspaceCreate,
    WorkspaceMemberUpdate,
)


def create_platform_router(
    platform: PlatformService,
    auth: AuthService,
    settings: Settings,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    def actor_for(request: Request) -> Actor:
        actor: Actor = request.state.actor
        if not actor.authenticated:
            raise HTTPException(status_code=401, detail="Authentication required")
        return actor

    def workspace_actor(request: Request, workspace_id: str, write: bool = False) -> tuple[Actor, str]:
        actor = actor_for(request)
        role = platform.workspace_role(workspace_id, actor.id)
        if role is None or (write and role not in {"owner", "editor"}):
            raise HTTPException(status_code=403, detail="Workspace access denied")
        request.state.audit_workspace_id = workspace_id
        return actor, role

    def identity(request: Request) -> tuple[str, str]:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        return request.headers.get("user-agent", "unknown"), forwarded or (request.client.host if request.client else "unknown")

    @router.get("/workspaces", tags=["platform"])
    def list_workspaces(request: Request) -> list[dict[str, Any]]:
        return platform.list_workspaces(actor_for(request).id)

    @router.post("/workspaces", status_code=201, tags=["platform"])
    def create_workspace(data: WorkspaceCreate, request: Request) -> dict[str, Any]:
        return platform.create_workspace(actor_for(request).id, data.name)

    @router.get("/workspaces/{workspace_id}/snapshot", tags=["platform"])
    def workspace_snapshot(workspace_id: str, request: Request, response: Response) -> dict[str, Any]:
        actor, role = workspace_actor(request, workspace_id)
        snapshot = platform.get_snapshot(workspace_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Workspace not found")
        response.headers["ETag"] = f'"{snapshot["revision"]}"'
        return platform.filter_snapshot(workspace_id, actor.id, role, snapshot)

    @router.put("/workspaces/{workspace_id}/snapshot", tags=["platform"])
    async def save_workspace_snapshot(
        workspace_id: str,
        data: dict[str, Any],
        request: Request,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> dict[str, Any]:
        actor, role = workspace_actor(request, workspace_id, write=True)
        expected = None
        if if_match:
            try:
                expected = int(if_match.strip('"'))
            except ValueError as error:
                raise HTTPException(status_code=400, detail="Invalid If-Match revision") from error
        try:
            permitted = platform.permitted_boards(workspace_id, actor.id) if role != "owner" else set()
            if permitted:
                current = platform.get_snapshot(workspace_id) or {}
                data = {
                    **data,
                    "boards": [board for board in current.get("boards", []) if board.get("id") not in permitted]
                    + [board for board in data.get("boards", []) if board.get("id") in permitted],
                    "tasks": [task for task in current.get("tasks", []) if task.get("boardId") not in permitted]
                    + [task for task in data.get("tasks", []) if task.get("boardId") in permitted],
                }
            snapshot = platform.save_snapshot(workspace_id, data, expected)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Workspace not found") from error
        except RuntimeError as error:
            if str(error).startswith("revision:"):
                raise HTTPException(status_code=409, detail={
                    "message": "Workspace revision conflict",
                    "currentRevision": int(str(error).split(":", 1)[1]),
                }) from error
            raise
        await request.app.state.realtime.publish({
            "type": "workspace.updated", "workspaceId": workspace_id, "revision": snapshot["revision"],
        })
        return snapshot

    @router.put("/workspaces/{workspace_id}/members", tags=["platform"])
    def update_workspace_member(workspace_id: str, data: WorkspaceMemberUpdate, request: Request) -> dict[str, Any]:
        _, role = workspace_actor(request, workspace_id)
        if role != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        result = platform.set_member(workspace_id, data.email, data.role)
        if result is None:
            raise HTTPException(status_code=404, detail="Registered user not found")
        return result

    @router.put("/workspaces/{workspace_id}/boards/{board_id}/permissions", tags=["platform"])
    def update_board_permission(
        workspace_id: str, board_id: str, data: BoardPermissionUpdate, request: Request,
    ) -> dict[str, str]:
        _, role = workspace_actor(request, workspace_id)
        if role != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        return platform.set_board_permission(workspace_id, board_id, data.user_id, data.role)

    @router.get("/my/tasks", tags=["platform"])
    def my_tasks(request: Request) -> list[dict[str, Any]]:
        actor = actor_for(request)
        return platform.my_tasks(actor.id, actor.name, actor.email)

    @router.get("/security/status", tags=["security"])
    def security_status(request: Request) -> dict[str, Any]:
        return platform.security_status(actor_for(request).id)

    @router.post("/security/totp/setup", tags=["security"])
    def setup_totp(request: Request) -> dict[str, str]:
        actor = actor_for(request)
        return platform.totp_setup(actor.id, actor.email)

    @router.post("/security/totp/enable", tags=["security"])
    def enable_totp(data: TotpVerify, request: Request) -> dict[str, bool]:
        if not platform.totp_enable(actor_for(request).id, data.code):
            raise HTTPException(status_code=400, detail="Invalid verification code")
        return {"enabled": True}

    @router.post("/security/email/send-verification", tags=["security"])
    def send_verification(request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
        actor = actor_for(request)
        token = platform.create_email_verification(actor.id)
        link = f"{settings.public_app_url}/?verifyEmail={token}"
        if settings.smtp_host:
            background_tasks.add_task(send_email, settings, actor.email, "Verify your Flowboard email", f"Verify email: {link}")
            token = None
        return {"accepted": True, "verificationToken": token}

    @router.post("/auth/email/verify", tags=["security"])
    def verify_email(data: EmailVerificationConfirm) -> dict[str, bool]:
        if not platform.verify_email(data.token):
            raise HTTPException(status_code=400, detail="Verification token is invalid or expired")
        return {"verified": True}

    @router.post("/security/passkeys/registration/start", tags=["security"])
    def passkey_registration_start(request: Request) -> dict[str, Any]:
        actor = actor_for(request)
        try:
            return platform.passkey_registration_start(actor.id, actor.email, actor.name)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.post("/security/passkeys/registration/complete", status_code=201, tags=["security"])
    def passkey_registration_complete(data: PasskeyRegistrationComplete, request: Request) -> dict[str, Any]:
        actor = actor_for(request)
        try:
            return platform.passkey_registration_complete(actor.id, data.challenge_id, data.credential, data.device_name)
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @router.post("/auth/passkeys/start", tags=["security"])
    def passkey_authentication_start(data: PasskeyAuthenticationStart) -> dict[str, Any]:
        try:
            result = platform.passkey_authentication_start(data.email)
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Passkey not found")
        return result

    @router.post("/auth/passkeys/complete", tags=["security"])
    def passkey_authentication_complete(data: PasskeyAuthenticationComplete, request: Request) -> dict[str, Any]:
        try:
            user_id = platform.passkey_authentication_complete(data.challenge_id, data.credential)
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        user = auth.get_user(user_id) if user_id else None
        if user is None:
            raise HTTPException(status_code=401, detail="Passkey authentication failed")
        token = auth.issue_token(user_id, *identity(request))
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.get("/workspaces/{workspace_id}/audit", tags=["security"])
    def audit_log(workspace_id: str, request: Request, limit: int = Query(100, ge=1, le=500)) -> list[dict[str, Any]]:
        _, role = workspace_actor(request, workspace_id)
        if role != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        return platform.list_audit(workspace_id, limit)

    @router.get("/push/public-key", tags=["notifications"])
    def push_public_key(request: Request) -> dict[str, str]:
        actor_for(request)
        return {"publicKey": settings.vapid_public_key}

    @router.post("/push/subscriptions", status_code=201, tags=["notifications"])
    def register_push(data: PushSubscriptionCreate, request: Request) -> dict[str, Any]:
        return platform.register_push(actor_for(request).id, data.endpoint, data.keys)

    @router.post("/push/test", tags=["notifications"])
    def test_push(request: Request, background_tasks: BackgroundTasks) -> dict[str, bool]:
        actor = actor_for(request)
        request.app.state.repository.enqueue_job("push.send", {
            "userId": actor.id, "title": "Flowboard", "body": "Push notifications are working.",
        })
        background_tasks.add_task(process_jobs, request.app.state.repository, settings)
        return {"queued": True}

    @router.get("/integrations", tags=["integrations"])
    def integrations(request: Request, workspace_id: str = Query(alias="workspaceId")) -> list[dict[str, Any]]:
        workspace_actor(request, workspace_id)
        return platform.list_integrations(workspace_id)

    @router.post("/integrations", status_code=201, tags=["integrations"])
    def create_integration(data: IntegrationCreate, request: Request) -> dict[str, Any]:
        workspace_actor(request, data.workspace_id, write=True)
        return platform.create_integration(data.workspace_id, data.kind, data.name, data.config)

    @router.post("/integrations/{integration_id}/test", tags=["integrations"])
    async def test_integration(integration_id: str, data: IntegrationMessage, request: Request) -> dict[str, bool]:
        integration = platform.integration(integration_id)
        if integration is None:
            raise HTTPException(status_code=404, detail="Integration not found")
        workspace_actor(request, integration["workspace_id"], write=True)
        try:
            delivered = await platform.deliver_integration(integration, data.text)
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail="Integration delivery failed") from error
        if not delivered:
            raise HTTPException(status_code=422, detail="Integration configuration is incomplete")
        return {"delivered": True}

    @router.post("/integrations/github/webhook/{integration_id}", tags=["integrations"])
    async def github_webhook(integration_id: str, request: Request) -> dict[str, bool]:
        integration = platform.integration(integration_id)
        if integration is None or integration["kind"] != "github":
            raise HTTPException(status_code=404, detail="Integration not found")
        body = await request.body()
        signature = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(integration["secret"].encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        event = request.headers.get("x-github-event", "")
        payload = json.loads(body or b"{}")
        if event in {"issues", "pull_request"} and payload.get("action") in {"opened", "reopened", "edited"}:
            source = payload.get("issue") or payload.get("pull_request") or {}
            snapshot = platform.get_snapshot(integration["workspace_id"]) or {}
            external_id = f"github:{source.get('html_url') or source.get('id')}"
            tasks = snapshot.setdefault("tasks", [])
            task = next((item for item in tasks if external_id in item.get("tags", [])), None)
            values = {
                "title": source.get("title") or "GitHub item",
                "description": source.get("body") or "",
                "cover": source.get("html_url") or "",
            }
            if task:
                task.update(values)
            else:
                from uuid import uuid4
                task = {
                    "id": str(uuid4()), **values, "status": "todo", "priority": "medium",
                    "deadline": "", "boardId": "default", "order": len(tasks), "archived": False,
                    "recurrence": "none", "tags": ["github", external_id], "checklist": [], "dependsOn": [],
                    "assignee": "", "color": "default", "comments": [], "estimatedMinutes": 0,
                    "timeSpentSeconds": 0, "timerStartedAt": "", "startDate": "", "goalId": "",
                    "milestone": False, "customValues": {}, "createdAt": datetime.now(timezone.utc).isoformat(),
                    "completedAt": "",
                }
                tasks.append(task)
            platform.save_snapshot(integration["workspace_id"], snapshot, snapshot.get("revision"))
        return {"accepted": True}

    @router.get("/workspaces/{workspace_id}/calendar.ics", response_class=PlainTextResponse, tags=["integrations"])
    def calendar_feed(workspace_id: str, request: Request) -> str:
        workspace_actor(request, workspace_id)
        snapshot = platform.get_snapshot(workspace_id) or {}
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Flowboard//Tasks//EN"]
        for task in snapshot.get("tasks", []):
            due = str(task.get("deadline") or "").replace("-", "")
            if not due:
                continue
            title = str(task.get("title") or "Task").replace("\n", " ").replace(",", "\\,")
            lines.extend(["BEGIN:VEVENT", f"UID:{task.get('id')}@flowboard", f"DTSTART;VALUE=DATE:{due}", f"SUMMARY:{title}", "END:VEVENT"])
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    @router.get("/custom-fields", tags=["platform"])
    def custom_fields(request: Request, workspace_id: str = Query(alias="workspaceId")) -> list[dict[str, Any]]:
        workspace_actor(request, workspace_id)
        return platform.list_custom_fields(workspace_id)

    @router.post("/custom-fields", status_code=201, tags=["platform"])
    def create_custom_field(data: CustomFieldCreate, request: Request) -> dict[str, Any]:
        workspace_actor(request, data.workspace_id, write=True)
        return platform.add_custom_field(data.workspace_id, data.name, data.field_type, data.options, data.required)

    @router.post("/public-shares", status_code=201, tags=["sharing"])
    def create_public_share(data: PublicShareCreate, request: Request) -> dict[str, Any]:
        actor, _ = workspace_actor(request, data.workspace_id, write=True)
        return platform.create_share(data.workspace_id, data.board_id, data.mode, data.password, data.expires_at, actor.id)

    @router.get("/public/{token}", tags=["sharing"])
    def public_share(token: str, password: str | None = None) -> dict[str, Any]:
        resolved = platform.resolve_share(token, password)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Share not found or password invalid")
        share, snapshot = resolved
        return {"mode": share["mode"], "boardId": share["board_id"], "workspace": snapshot}

    @router.post("/public/{token}/submit", status_code=201, tags=["sharing"])
    def public_form_submit(token: str, data: PublicFormSubmission, password: str | None = None) -> dict[str, Any]:
        resolved = platform.resolve_share(token, password)
        if resolved is None or resolved[0]["mode"] != "form":
            raise HTTPException(status_code=404, detail="Public form not found")
        return platform.public_form_submit(resolved[0], data.title, data.description, data.values)

    @router.post("/collaboration/operations", status_code=201, tags=["collaboration"])
    async def add_operation(data: CollaborationOperation, request: Request) -> dict[str, Any]:
        actor = actor_for(request)
        if data.workspace_id:
            workspace_actor(request, data.workspace_id, write=True)
        operation = platform.add_operation(
            data.workspace_id, data.task_id, data.client_id, actor.id, data.field, data.operation, data.lamport,
        )
        await request.app.state.realtime.publish({"type": "task.operation", **operation})
        return operation

    @router.get("/tasks/{task_id}/operations", tags=["collaboration"])
    def task_operations(task_id: str, request: Request, after: int = Query(0, ge=0)) -> list[dict[str, Any]]:
        actor_for(request)
        return platform.list_operations(task_id, after)

    @router.post("/assistant", tags=["assistant"])
    def assistant(data: AssistantRequest, request: Request) -> dict[str, Any]:
        actor_for(request)
        if data.workspace_id:
            workspace_actor(request, data.workspace_id)
        return platform.assistant(data.action, data.text, data.task, data.workspace_id)

    return router
