from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, File, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .config import Settings
from .database import Database
from .models import (
    AttachmentOut,
    AutomationSettings,
    BatchResult,
    BatchTaskUpdate,
    BoardCreate,
    BoardOut,
    BoardUpdate,
    HealthOut,
    TaskCreate,
    TaskOut,
    TaskUpdate,
    WorkspaceOut,
    WorkspacePayload,
)
from .repository import Repository


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    database = Database(config.database_path)
    repository = Repository(database)

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    router = APIRouter(prefix="/api/v1")

    @router.get("/health", response_model=HealthOut, tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "flowboard-api", "version": "1.0.0"}

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

    @router.get("/workspace", response_model=WorkspaceOut, tags=["workspace"])
    def get_workspace() -> dict:
        return repository.get_workspace()

    @router.put("/workspace", response_model=WorkspaceOut, tags=["workspace"])
    def replace_workspace(data: WorkspacePayload) -> dict:
        try:
            return repository.replace_workspace(data)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "Flowboard API", "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()

