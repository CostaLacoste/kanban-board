from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter, BackgroundTasks, FastAPI, File, Header, HTTPException, Query,
    Request, Response, UploadFile, WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse

from .config import Settings
from .database import Database
from .auth import Actor, AuthService
from .integrations import deliver_outbox, process_jobs, send_email
from .middleware import ApiMiddleware
from .models import (
    AttachmentOut,
    AutomationSettings,
    BatchResult,
    BatchTaskUpdate,
    BoardCreate,
    BoardOut,
    BoardUpdate,
    CommentCreate,
    CommentReaction,
    CommentOut,
    CommentUpdate,
    GoalCreate,
    GoalOut,
    HealthOut,
    ApiTokenCreate,
    ApiTokenOut,
    AuthToken,
    LoginRequest,
    InvitationAccept,
    InvitationCreate,
    InvitationOut,
    JobOut,
    MemberUpdate,
    NotificationOut,
    NotificationPreferences,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    RevisionOut,
    SavedFilterCreate,
    SavedFilterOut,
    SessionOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    WorkspaceOut,
    WorkspacePayload,
    UserOut,
    WebhookCreate,
    WebhookOut,
    WatcherUpdate,
)
from .repository import Repository
from .realtime import RealtimeManager
from .storage import LocalObjectStorage
from .platform import PlatformService
from .platform_routes import create_platform_router


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    database = Database(config.database_path, config.database_url)
    repository = Repository(database)
    auth = AuthService(database, config)
    realtime = RealtimeManager(repository)
    object_storage = LocalObjectStorage(config.object_storage_path)
    platform = PlatformService(database, repository, config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        async def job_loop() -> None:
            ticks = 0
            while True:
                await process_jobs(repository, config)
                ticks += 1
                if ticks % 30 == 0:
                    platform.run_scheduled_notifications()
                await asyncio.sleep(2)

        bus_task = asyncio.create_task(realtime.run_bus())
        worker_task = asyncio.create_task(job_loop())
        try:
            yield
        finally:
            realtime.stop()
            bus_task.cancel()
            worker_task.cancel()
            try:
                await asyncio.gather(bus_task, worker_task)
            except asyncio.CancelledError:
                pass

    app = FastAPI(
        title="Flowboard API",
        version="1.0.0",
        description="REST API for Flowboard boards, tasks, workspace settings and attachments.",
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.repository = repository
    app.state.auth = auth
    app.state.realtime = realtime
    app.state.object_storage = object_storage
    app.state.platform = platform
    app.state.metrics = {"requests": 0, "duration": 0.0, "statuses": Counter()}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiMiddleware, auth=auth, settings=config, platform=platform)

    router = APIRouter(prefix="/api/v1")

    def authenticated_actor(request: Request) -> Actor:
        actor: Actor = request.state.actor
        if not actor.authenticated:
            raise HTTPException(status_code=401, detail="Authentication required")
        return actor

    def owner_actor(request: Request) -> Actor:
        actor = authenticated_actor(request)
        if actor.role != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        return actor

    def request_identity(request: Request) -> tuple[str, str]:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        ip_address = forwarded or (request.client.host if request.client else "unknown")
        return request.headers.get("user-agent", "unknown"), ip_address

    @router.get("/health", response_model=HealthOut, tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "flowboard-api", "version": "1.0.0"}

    @router.get("/ready", tags=["system"])
    def ready() -> dict[str, str]:
        with database.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ready", "database": database.provider}

    @router.get("/metrics", response_class=PlainTextResponse, tags=["system"])
    def metrics(request: Request) -> str:
        values = request.app.state.metrics
        lines = [
            "# TYPE flowboard_http_requests_total counter",
            f"flowboard_http_requests_total {values['requests']}",
            "# TYPE flowboard_http_request_duration_seconds_total counter",
            f"flowboard_http_request_duration_seconds_total {values['duration']:.6f}",
        ]
        for code, count in sorted(values["statuses"].items()):
            lines.append(f'flowboard_http_responses_total{{status="{code}"}} {count}')
        lines.extend([
            "# TYPE flowboard_realtime_connections gauge",
            f"flowboard_realtime_connections {len(realtime.sessions)}",
            "# TYPE flowboard_jobs gauge",
        ])
        for job_status, count in sorted(repository.job_counts().items()):
            lines.append(f'flowboard_jobs{{status="{job_status}"}} {count}')
        return "\n".join(lines) + "\n"

    @router.post("/auth/register", response_model=AuthToken, status_code=201, tags=["auth"])
    def register(data: RegisterRequest, request: Request) -> dict:
        result = auth.register(data, *request_identity(request))
        if result is None:
            raise HTTPException(status_code=409, detail="Email already registered")
        user, token = result
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.post("/auth/login", response_model=AuthToken, tags=["auth"])
    def login(data: LoginRequest, request: Request) -> dict:
        result = auth.login(data, *request_identity(request))
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user, token = result
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.post("/auth/invitations/accept", response_model=AuthToken, tags=["auth"])
    def accept_invitation(data: InvitationAccept, request: Request) -> dict:
        result = auth.accept_invitation(data, *request_identity(request))
        if result is None:
            raise HTTPException(status_code=400, detail="Invitation is invalid or expired")
        user, token = result
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.post("/auth/password-reset/request", tags=["auth"])
    async def request_password_reset(
        data: PasswordResetRequest, background_tasks: BackgroundTasks
    ) -> dict[str, object]:
        result = auth.create_password_reset(data.email)
        token = None
        if result:
            recipient, raw = result
            link = f"{config.public_app_url}/?resetToken={quote(raw)}"
            if config.smtp_host:
                background_tasks.add_task(
                    send_email, config, recipient, "Flowboard password reset", f"Reset your password: {link}"
                )
            else:
                token = raw
        return {"accepted": True, "resetToken": token}

    @router.post("/auth/password-reset/confirm", tags=["auth"])
    def confirm_password_reset(data: PasswordResetConfirm) -> dict[str, bool]:
        if not auth.reset_password(data.token, data.password):
            raise HTTPException(status_code=400, detail="Reset token is invalid or expired")
        return {"reset": True}

    @router.get("/auth/me", response_model=UserOut, tags=["auth"])
    def me(request: Request) -> dict:
        actor = authenticated_actor(request)
        return auth.get_user(actor.id)

    @router.get("/auth/sessions", response_model=list[SessionOut], tags=["auth"])
    def sessions(request: Request) -> list[dict]:
        actor = authenticated_actor(request)
        bearer = request.headers.get("authorization", "")
        token = bearer[7:] if bearer.lower().startswith("bearer ") else None
        return auth.list_sessions(actor.id, auth.token_session_id(token))

    @router.delete("/auth/sessions/{session_id}", status_code=204, tags=["auth"])
    def revoke_session(session_id: str, request: Request) -> Response:
        actor = authenticated_actor(request)
        if not auth.revoke_session(actor.id, session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return Response(status_code=204)

    @router.post("/invitations", response_model=InvitationOut, status_code=201, tags=["collaboration"])
    def create_invitation(
        data: InvitationCreate, request: Request, background_tasks: BackgroundTasks
    ) -> dict:
        actor = owner_actor(request)
        invitation = auth.create_invitation(data.email, data.role, actor.id)
        if config.smtp_host:
            link = f"{config.public_app_url}/?invite={quote(invitation['token'])}"
            background_tasks.add_task(
                send_email, config, data.email, "Flowboard invitation", f"Join the workspace: {link}"
            )
        return invitation

    @router.get("/invitations", response_model=list[InvitationOut], tags=["collaboration"])
    def invitations(request: Request) -> list[dict]:
        owner_actor(request)
        return auth.list_invitations()

    @router.get("/members", response_model=list[UserOut], tags=["collaboration"])
    def members(request: Request) -> list[dict]:
        authenticated_actor(request)
        return auth.list_members()

    @router.put("/members", response_model=UserOut, tags=["collaboration"])
    def update_member(data: MemberUpdate, request: Request) -> dict:
        owner_actor(request)
        member = auth.update_member_role(data.email, data.role)
        if member is None:
            raise HTTPException(status_code=404, detail="User not found")
        return member

    @router.post("/auth/api-tokens", response_model=ApiTokenOut, status_code=201, tags=["auth"])
    def create_api_token(data: ApiTokenCreate, request: Request) -> dict:
        actor = authenticated_actor(request)
        return auth.create_api_token(actor.id, data.name)

    @router.get("/auth/api-tokens", response_model=list[ApiTokenOut], tags=["auth"])
    def list_api_tokens(request: Request) -> list[dict]:
        actor = authenticated_actor(request)
        return auth.list_api_tokens(actor.id)

    @router.delete("/auth/api-tokens/{token_id}", status_code=204, tags=["auth"])
    def remove_api_token(token_id: str, request: Request) -> Response:
        actor = authenticated_actor(request)
        if not auth.delete_api_token(actor.id, token_id):
            raise HTTPException(status_code=404, detail="API token not found")
        return Response(status_code=204)

    @router.get("/boards", response_model=list[BoardOut], tags=["boards"])
    def list_boards() -> list[dict]:
        return repository.list_boards()

    @router.post("/boards", response_model=BoardOut, status_code=status.HTTP_201_CREATED, tags=["boards"])
    def create_board(data: BoardCreate) -> dict:
        return repository.create_board(data)

    @router.patch("/boards/{board_id}", response_model=BoardOut, tags=["boards"])
    def update_board(board_id: str, data: BoardUpdate) -> dict:
        board = repository.update_board(board_id, data.name)
        if board is None:
            raise HTTPException(status_code=404, detail="Board not found")
        return board

    @router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["boards"])
    def delete_board(board_id: str) -> Response:
        deleted = repository.delete_board(board_id)
        if deleted is None:
            raise HTTPException(status_code=409, detail="The last board cannot be deleted")
        if not deleted:
            raise HTTPException(status_code=404, detail="Board not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/tasks", response_model=list[TaskOut], tags=["tasks"])
    def list_tasks(
        board_id: Annotated[str | None, Query(alias="boardId")] = None,
        archived: bool | None = None,
    ) -> list[dict]:
        return repository.list_tasks(board_id, archived)

    @router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED, tags=["tasks"])
    def create_task(data: TaskCreate) -> dict:
        task = repository.create_task(data)
        if task is None:
            raise HTTPException(status_code=422, detail="Unknown boardId")
        return task

    @router.get("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
    def get_task(task_id: str) -> dict:
        task = repository.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @router.patch("/tasks/{task_id}", response_model=TaskOut, tags=["tasks"])
    def update_task(task_id: str, data: TaskUpdate) -> dict:
        task = repository.update_task(task_id, data)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if task is False:
            raise HTTPException(status_code=422, detail="Unknown boardId")
        return task

    @router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
    def delete_task(task_id: str) -> Response:
        if not repository.delete_task(task_id):
            raise HTTPException(status_code=404, detail="Task not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/tasks/{task_id}/comments", response_model=list[CommentOut], tags=["comments"])
    def list_task_comments(task_id: str) -> list[dict]:
        comments = repository.list_comments(task_id)
        if comments is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return comments

    @router.post(
        "/tasks/{task_id}/comments",
        response_model=CommentOut,
        status_code=status.HTTP_201_CREATED,
        tags=["comments"],
    )
    async def create_task_comment(task_id: str, data: CommentCreate, request: Request) -> dict:
        actor: Actor = request.state.actor
        try:
            comment = repository.add_comment(
                task_id,
                data,
                actor.id if actor.authenticated else None,
                actor.name,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if comment is None:
            raise HTTPException(status_code=404, detail="Task not found")
        await realtime.publish({"type": "comment.created", "taskId": task_id, "comment": comment})
        return comment

    @router.patch("/comments/{comment_id}", response_model=CommentOut, tags=["comments"])
    async def update_comment(comment_id: str, data: CommentUpdate, request: Request) -> dict:
        actor = authenticated_actor(request)
        comment = repository.update_comment(
            comment_id, actor.id, data.text, data.resolved, actor.role == "owner"
        )
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        await realtime.publish({"type": "comment.updated", "comment": comment})
        return comment

    @router.delete("/comments/{comment_id}", status_code=204, tags=["comments"])
    async def delete_comment(comment_id: str, request: Request) -> Response:
        actor = authenticated_actor(request)
        if not repository.delete_comment(comment_id, actor.id, actor.role == "owner"):
            raise HTTPException(status_code=404, detail="Comment not found")
        await realtime.publish({"type": "comment.deleted", "commentId": comment_id})
        return Response(status_code=204)

    @router.post("/comments/{comment_id}/reactions", response_model=CommentOut, tags=["comments"])
    async def react_to_comment(comment_id: str, data: CommentReaction, request: Request) -> dict:
        actor = authenticated_actor(request)
        comment = repository.toggle_reaction(comment_id, actor.id, data.emoji)
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment not found")
        await realtime.publish({"type": "comment.updated", "comment": comment})
        return comment

    @router.get("/tasks/{task_id}/watchers", tags=["comments"])
    def task_watchers(task_id: str, request: Request) -> list[dict]:
        authenticated_actor(request)
        watchers = repository.list_watchers(task_id)
        if watchers is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return watchers

    @router.put("/tasks/{task_id}/watchers/me", tags=["comments"])
    def watch_task(task_id: str, data: WatcherUpdate, request: Request) -> dict[str, bool]:
        actor = authenticated_actor(request)
        watching = repository.set_watching(task_id, actor.id, data.watching)
        if watching is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"watching": watching}

    @router.post("/tasks/{task_id}/timer/start", response_model=TaskOut, tags=["time tracking"])
    def start_task_timer(task_id: str) -> dict:
        task = repository.start_timer(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @router.post("/tasks/{task_id}/timer/stop", response_model=TaskOut, tags=["time tracking"])
    def stop_task_timer(task_id: str) -> dict:
        task = repository.stop_timer(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @router.patch("/tasks", response_model=BatchResult, tags=["tasks"])
    def batch_update_tasks(data: BatchTaskUpdate) -> dict:
        tasks = repository.batch_update(data)
        return {"updated": len(tasks), "tasks": tasks}

    @router.get("/search/tasks", response_model=list[TaskOut], tags=["search"])
    def search_tasks(
        q: str = "", task_status: Annotated[str | None, Query(alias="status")] = None,
        priority: str | None = None, assignee: str | None = None, tag: str | None = None,
        board_id: Annotated[str | None, Query(alias="boardId")] = None,
        deadline_from: Annotated[str | None, Query(alias="deadlineFrom")] = None,
        deadline_to: Annotated[str | None, Query(alias="deadlineTo")] = None,
        archived: bool | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict]:
        return repository.search_tasks(
            q, task_status, priority, assignee, tag, board_id, deadline_from, deadline_to,
            archived, limit, offset,
        )

    @router.post("/saved-filters", response_model=SavedFilterOut, status_code=201, tags=["search"])
    def save_filter(data: SavedFilterCreate, request: Request) -> dict:
        actor = authenticated_actor(request)
        return repository.create_saved_filter(actor.id, data.name, data.query)

    @router.get("/saved-filters", response_model=list[SavedFilterOut], tags=["search"])
    def saved_filters(request: Request) -> list[dict]:
        actor = authenticated_actor(request)
        return repository.list_saved_filters(actor.id)

    @router.delete("/saved-filters/{filter_id}", status_code=204, tags=["search"])
    def remove_saved_filter(filter_id: str, request: Request) -> Response:
        actor = authenticated_actor(request)
        if not repository.delete_saved_filter(actor.id, filter_id):
            raise HTTPException(status_code=404, detail="Saved filter not found")
        return Response(status_code=204)

    @router.post(
        "/tasks/{task_id}/attachments",
        response_model=AttachmentOut,
        status_code=status.HTTP_201_CREATED,
        tags=["attachments"],
    )
    async def upload_attachment(task_id: str, file: Annotated[UploadFile, File()]) -> dict:
        if repository.get_task(task_id) is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if repository.attachment_count(task_id) >= config.max_attachments_per_task:
            raise HTTPException(status_code=409, detail="Attachment limit reached")
        content = await file.read(config.max_attachment_size + 1)
        await file.close()
        if len(content) > config.max_attachment_size:
            raise HTTPException(status_code=413, detail="Attachment is too large")
        clean_name = Path(file.filename or "file").name[:100]
        media_type = (file.content_type or "application/octet-stream")[:100]
        blocked_types = {"text/html", "image/svg+xml", "application/javascript", "application/x-sh"}
        blocked_extensions = {".exe", ".dll", ".sh", ".bat", ".cmd", ".js", ".html", ".svg"}
        if media_type in blocked_types or Path(clean_name).suffix.lower() in blocked_extensions or content.startswith((b"MZ", b"\x7fELF")):
            raise HTTPException(status_code=415, detail="Attachment type is not allowed")
        attachment = repository.add_attachment(
            task_id,
            clean_name,
            media_type,
            b"" if object_storage.enabled else content,
        )
        if attachment and object_storage.enabled:
            key, checksum = object_storage.put(attachment["id"], content)
            repository.bind_attachment_object(attachment["id"], key, checksum)
            attachment["size"] = len(content)
            with database._lock, database.connect() as connection:
                connection.execute("UPDATE attachments SET size=? WHERE id=?", (len(content), attachment["id"]))
        if attachment:
            repository.add_attachment_version(attachment["id"], clean_name, media_type, content)
        return attachment

    @router.get("/attachments/{attachment_id}/versions", tags=["attachments"])
    def attachment_versions(attachment_id: str) -> list[dict]:
        if repository.get_attachment(attachment_id) is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        return repository.list_attachment_versions(attachment_id)

    @router.post("/attachments/{attachment_id}/versions", status_code=201, tags=["attachments"])
    async def replace_attachment(attachment_id: str, request: Request, file: Annotated[UploadFile, File()]) -> dict:
        if repository.get_attachment(attachment_id) is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        content = await file.read(config.max_attachment_size + 1)
        await file.close()
        if len(content) > config.max_attachment_size:
            raise HTTPException(status_code=413, detail="Attachment is too large")
        name = Path(file.filename or "file").name[:100]
        media_type = (file.content_type or "application/octet-stream")[:100]
        blocked = {"text/html", "image/svg+xml", "application/javascript", "application/x-sh"}
        if media_type in blocked or Path(name).suffix.lower() in {".exe", ".dll", ".sh", ".bat", ".cmd", ".js", ".html", ".svg"}:
            raise HTTPException(status_code=415, detail="Attachment type is not allowed")
        actor: Actor = request.state.actor
        version = repository.add_attachment_version(
            attachment_id, name, media_type, content, actor.id if actor.authenticated else None,
        )
        if object_storage.enabled:
            key, checksum = object_storage.put(attachment_id, content)
            repository.bind_attachment_object(attachment_id, key, checksum)
        return version

    @router.get("/attachments/{attachment_id}/versions/{version_id}", tags=["attachments"])
    def download_attachment_version(attachment_id: str, version_id: str) -> StreamingResponse:
        version = repository.get_attachment_version(attachment_id, version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="Attachment version not found")
        encoded = quote(version["name"], safe="")
        return StreamingResponse(iter([version["content"]]), media_type=version["media_type"], headers={
            "Content-Disposition": f"attachment; filename=download; filename*=UTF-8''{encoded}",
        })

    @router.get("/attachments/{attachment_id}", tags=["attachments"])
    def download_attachment(attachment_id: str) -> StreamingResponse:
        attachment = repository.get_attachment(attachment_id)
        if attachment is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        encoded_filename = quote(attachment["name"], safe="")
        object_ref = repository.get_attachment_object(attachment_id)
        try:
            content = object_storage.get(object_ref["storage_key"]) if object_ref else attachment["content"]
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail="Attachment object is missing") from error
        return StreamingResponse(
            iter([content]),
            media_type=attachment["media_type"],
            headers={
                "Content-Disposition": f"attachment; filename=download; filename*=UTF-8''{encoded_filename}"
            },
        )

    @router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["attachments"])
    def delete_attachment(attachment_id: str) -> Response:
        object_ref = repository.get_attachment_object(attachment_id)
        if not repository.delete_attachment(attachment_id):
            raise HTTPException(status_code=404, detail="Attachment not found")
        if object_ref:
            object_storage.delete(object_ref["storage_key"])
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/automations", response_model=AutomationSettings, tags=["workspace"])
    def get_automations() -> dict:
        return repository.get_automations()

    @router.put("/automations", response_model=AutomationSettings, tags=["workspace"])
    def set_automations(data: AutomationSettings) -> dict:
        return repository.set_automations(data)

    @router.get("/notifications", response_model=list[NotificationOut], tags=["notifications"])
    def notifications(request: Request) -> list[dict]:
        actor: Actor = request.state.actor
        return repository.list_notifications(actor.id if actor.authenticated else None)

    @router.post("/notifications/{notification_id}/read", status_code=204, tags=["notifications"])
    def read_notification(notification_id: str, request: Request) -> Response:
        actor: Actor = request.state.actor
        if not repository.read_notification(notification_id, actor.id if actor.authenticated else None):
            raise HTTPException(status_code=404, detail="Notification not found")
        return Response(status_code=204)

    @router.post("/notifications/read-all", tags=["notifications"])
    def read_all_notifications(request: Request) -> dict[str, int]:
        actor: Actor = request.state.actor
        return {"updated": repository.read_all_notifications(actor.id if actor.authenticated else None)}

    @router.get("/notifications/summary", tags=["notifications"])
    def notification_summary(request: Request) -> dict:
        actor: Actor = request.state.actor
        return repository.notification_summary(actor.id if actor.authenticated else None)

    @router.post("/goals", response_model=GoalOut, status_code=201, tags=["planning"])
    def create_goal(data: GoalCreate) -> dict:
        return repository.create_goal(data.title, data.description, data.target_date, data.color)

    @router.get("/goals", response_model=list[GoalOut], tags=["planning"])
    def goals() -> list[dict]:
        return repository.list_goals()

    @router.delete("/goals/{goal_id}", status_code=204, tags=["planning"])
    def delete_goal(goal_id: str) -> Response:
        if not repository.delete_goal(goal_id):
            raise HTTPException(status_code=404, detail="Goal not found")
        return Response(status_code=204)

    @router.get("/planning/timeline", tags=["planning"])
    def planning_timeline(board_id: Annotated[str | None, Query(alias="boardId")] = None) -> dict:
        tasks = repository.list_tasks(board_id, False)
        return {
            "goals": repository.list_goals(),
            "tasks": [task for task in tasks if task.get("startDate") or task.get("deadline") or task.get("milestone")],
        }

    @router.get("/planning/workload", tags=["planning"])
    def planning_workload() -> list[dict]:
        buckets: dict[str, dict[str, int | str]] = {}
        for task in repository.list_tasks(archived=False):
            assignee = task.get("assignee") or "Unassigned"
            bucket = buckets.setdefault(assignee, {"assignee": assignee, "tasks": 0, "estimatedMinutes": 0, "spentSeconds": 0})
            bucket["tasks"] = int(bucket["tasks"]) + 1
            bucket["estimatedMinutes"] = int(bucket["estimatedMinutes"]) + int(task.get("estimatedMinutes") or 0)
            bucket["spentSeconds"] = int(bucket["spentSeconds"]) + int(task.get("timeSpentSeconds") or 0)
        return list(buckets.values())

    @router.get("/notification-preferences", response_model=NotificationPreferences, tags=["notifications"])
    def notification_preferences(request: Request) -> dict:
        actor = authenticated_actor(request)
        return repository.get_notification_preferences(actor.id)

    @router.put("/notification-preferences", response_model=NotificationPreferences, tags=["notifications"])
    def update_notification_preferences(data: NotificationPreferences, request: Request) -> dict:
        actor = authenticated_actor(request)
        return repository.set_notification_preferences(actor.id, data.model_dump(by_alias=True))

    @router.post("/webhooks", response_model=WebhookOut, status_code=201, tags=["integrations"])
    def create_webhook(data: WebhookCreate, request: Request) -> dict:
        actor = authenticated_actor(request)
        return repository.create_webhook(actor.id, data.url, data.events)

    @router.get("/webhooks", response_model=list[WebhookOut], tags=["integrations"])
    def webhooks(request: Request) -> list[dict]:
        actor = authenticated_actor(request)
        return repository.list_webhooks(actor.id)

    @router.delete("/webhooks/{webhook_id}", status_code=204, tags=["integrations"])
    def remove_webhook(webhook_id: str, request: Request) -> Response:
        actor = authenticated_actor(request)
        if not repository.delete_webhook(actor.id, webhook_id):
            raise HTTPException(status_code=404, detail="Webhook not found")
        return Response(status_code=204)

    @router.post("/outbox/process", tags=["integrations"])
    async def process_outbox(request: Request) -> dict[str, int]:
        owner_actor(request)
        return await deliver_outbox(repository)

    @router.get("/jobs", response_model=list[JobOut], tags=["system"])
    def jobs(request: Request) -> list[dict]:
        owner_actor(request)
        return repository.list_jobs()

    @router.post("/jobs/process", tags=["system"])
    async def run_jobs(request: Request) -> dict[str, int]:
        owner_actor(request)
        return await process_jobs(repository, config)

    @router.get("/workspace", response_model=WorkspaceOut, tags=["workspace"])
    def get_workspace(response: Response) -> dict:
        workspace = repository.get_workspace()
        response.headers["ETag"] = f'"{workspace["revision"]}"'
        return workspace

    @router.put("/workspace", response_model=WorkspaceOut, tags=["workspace"])
    async def replace_workspace(
        data: WorkspacePayload,
        request: Request,
        background_tasks: BackgroundTasks,
        if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    ) -> dict:
        actor: Actor = request.state.actor
        expected = None
        if if_match:
            try:
                expected = int(if_match.strip('"'))
            except ValueError as error:
                raise HTTPException(status_code=400, detail="Invalid If-Match revision") from error
        try:
            workspace = repository.replace_workspace(data, expected, actor.id if actor.authenticated else None)
            await realtime.publish({"type": "workspace.updated", "revision": workspace["revision"]})
            repository.enqueue_job("webhooks.deliver", {"revision": workspace["revision"]})
            background_tasks.add_task(process_jobs, repository, config)
            if actor.authenticated:
                preferences = repository.get_notification_preferences(actor.id)
                if preferences.get("emailEnabled"):
                    repository.enqueue_job("email.send", {
                        "recipient": actor.email, "subject": "Flowboard synchronized",
                        "body": f"Workspace revision {workspace['revision']} was saved.",
                    })
            return workspace
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except RuntimeError as error:
            if str(error).startswith("revision:"):
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Workspace revision conflict", "currentRevision": int(str(error).split(":")[1])},
                ) from error
            raise

    @router.get("/revisions", response_model=list[RevisionOut], tags=["history"])
    def revisions() -> list[dict]:
        return repository.list_revisions()

    @router.post("/revisions/{revision_id}/restore", response_model=WorkspaceOut, tags=["history"])
    async def restore_revision(revision_id: str, request: Request) -> dict:
        actor: Actor = request.state.actor
        workspace = repository.restore_revision(revision_id, actor.id if actor.authenticated else None)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Revision not found")
        await realtime.publish({"type": "workspace.updated", "revision": workspace["revision"]})
        return workspace

    @router.get("/admin/backup", response_model=WorkspaceOut, tags=["system"])
    def backup(request: Request) -> dict:
        if config.auth_required:
            owner_actor(request)
        return repository.get_workspace()

    app.include_router(router)
    app.include_router(create_platform_router(platform, auth, config))

    @app.websocket("/api/v1/realtime")
    async def realtime_socket(
        websocket: WebSocket,
        token: str | None = None,
        client_id: Annotated[str, Query(alias="clientId")] = "browser",
    ) -> None:
        actor = auth.authenticate(token)
        if config.auth_required and actor is None:
            await websocket.close(code=4401)
            return
        actor = actor or Actor.guest()
        session = await realtime.connect(websocket, actor, client_id[:100])
        await websocket.send_json({
            "type": "connected",
            "revision": repository.get_workspace()["revision"],
            "user": {"id": actor.id, "name": actor.name, "role": actor.role},
            "presence": realtime.presence(),
        })
        try:
            while True:
                message = await websocket.receive_json()
                message_type = message.get("type")
                if message_type == "presence":
                    await realtime.update_presence(websocket, str(message.get("taskId") or "")[:100] or None)
                elif message_type == "task.draft" and session.role != "viewer":
                    field = str(message.get("field") or "")
                    allowed_fields = {
                        "title", "description", "status", "priority", "deadline", "assignee", "tags",
                    }
                    if field not in allowed_fields:
                        continue
                    value = message.get("value")
                    if not isinstance(value, (str, list)):
                        continue
                    await realtime.publish({
                        "type": "task.draft",
                        "taskId": str(message.get("taskId") or "")[:100],
                        "field": field,
                        "value": value,
                        "actor": {"id": actor.id, "name": actor.name},
                    }, exclude=websocket)
                elif message_type in {"task.operation", "cursor"} and session.role != "viewer":
                    workspace_id = str(message.get("workspaceId") or "") or None
                    task_id = str(message.get("taskId") or "")[:100]
                    if message_type == "task.operation" and task_id:
                        operation = platform.add_operation(
                            workspace_id,
                            task_id,
                            client_id[:100],
                            actor.id if actor.authenticated else None,
                            str(message.get("field") or "description")[:50],
                            message.get("operation") if isinstance(message.get("operation"), dict) else {},
                            max(0, int(message.get("lamport") or 0)),
                        )
                        await realtime.publish({"type": "task.operation", **operation}, exclude=websocket)
                    elif task_id:
                        await realtime.publish({
                            "type": "cursor", "taskId": task_id,
                            "field": str(message.get("field") or "")[:50],
                            "offset": max(0, int(message.get("offset") or 0)),
                            "actor": {"id": actor.id, "name": actor.name},
                        }, exclude=websocket)
        except WebSocketDisconnect:
            await realtime.disconnect(websocket)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "Flowboard API", "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()

