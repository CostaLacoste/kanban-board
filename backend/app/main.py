from __future__ import annotations

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
from .integrations import deliver_outbox, send_email
from .middleware import ApiMiddleware
from .models import (
    AttachmentOut,
    AutomationSettings,
    BatchResult,
    BatchTaskUpdate,
    BoardCreate,
    BoardOut,
    BoardUpdate,
    HealthOut,
    ApiTokenCreate,
    ApiTokenOut,
    AuthToken,
    LoginRequest,
    MemberUpdate,
    NotificationOut,
    NotificationPreferences,
    RegisterRequest,
    RevisionOut,
    SavedFilterCreate,
    SavedFilterOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    WorkspaceOut,
    WorkspacePayload,
    UserOut,
    WebhookCreate,
    WebhookOut,
)
from .repository import Repository
from .realtime import RealtimeManager


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    database = Database(config.database_path)
    repository = Repository(database)
    auth = AuthService(database, config)
    realtime = RealtimeManager()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        yield

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
    app.state.metrics = {"requests": 0, "duration": 0.0, "statuses": Counter()}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(ApiMiddleware, auth=auth, settings=config)

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

    @router.get("/health", response_model=HealthOut, tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "flowboard-api", "version": "1.0.0"}

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
        return "\n".join(lines) + "\n"

    @router.post("/auth/register", response_model=AuthToken, status_code=201, tags=["auth"])
    def register(data: RegisterRequest) -> dict:
        result = auth.register(data)
        if result is None:
            raise HTTPException(status_code=409, detail="Email already registered")
        user, token = result
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.post("/auth/login", response_model=AuthToken, tags=["auth"])
    def login(data: LoginRequest) -> dict:
        result = auth.login(data)
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        user, token = result
        return {"accessToken": token, "tokenType": "bearer", "user": user}

    @router.get("/auth/me", response_model=UserOut, tags=["auth"])
    def me(request: Request) -> dict:
        actor = authenticated_actor(request)
        return auth.get_user(actor.id)

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
    ) -> list[dict]:
        return repository.search_tasks(q, task_status, priority, assignee, tag)

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
        return repository.add_attachment(
            task_id,
            clean_name,
            (file.content_type or "application/octet-stream")[:100],
            content,
        )

    @router.get("/attachments/{attachment_id}", tags=["attachments"])
    def download_attachment(attachment_id: str) -> StreamingResponse:
        attachment = repository.get_attachment(attachment_id)
        if attachment is None:
            raise HTTPException(status_code=404, detail="Attachment not found")
        encoded_filename = quote(attachment["name"], safe="")
        return StreamingResponse(
            iter([attachment["content"]]),
            media_type=attachment["media_type"],
            headers={
                "Content-Disposition": f"attachment; filename=download; filename*=UTF-8''{encoded_filename}"
            },
        )

    @router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["attachments"])
    def delete_attachment(attachment_id: str) -> Response:
        if not repository.delete_attachment(attachment_id):
            raise HTTPException(status_code=404, detail="Attachment not found")
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
            await realtime.broadcast({"type": "workspace.updated", "revision": workspace["revision"]})
            background_tasks.add_task(deliver_outbox, repository)
            if actor.authenticated:
                preferences = repository.get_notification_preferences(actor.id)
                if preferences.get("emailEnabled"):
                    background_tasks.add_task(
                        send_email,
                        config,
                        actor.email,
                        "Flowboard synchronized",
                        f"Workspace revision {workspace['revision']} was saved.",
                    )
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
        await realtime.broadcast({"type": "workspace.updated", "revision": workspace["revision"]})
        return workspace

    @router.get("/admin/backup", response_model=WorkspaceOut, tags=["system"])
    def backup(request: Request) -> dict:
        if config.auth_required:
            owner_actor(request)
        return repository.get_workspace()

    app.include_router(router)

    @app.websocket("/api/v1/realtime")
    async def realtime_socket(websocket: WebSocket, token: str | None = None) -> None:
        actor = auth.authenticate(token)
        if config.auth_required and actor is None:
            await websocket.close(code=4401)
            return
        await realtime.connect(websocket)
        await websocket.send_json({"type": "connected", "revision": repository.get_workspace()["revision"]})
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            realtime.disconnect(websocket)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "Flowboard API", "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()

