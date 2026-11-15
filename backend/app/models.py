from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Priority = Literal["low", "medium", "high"]
Recurrence = Literal["none", "daily", "weekly", "monthly"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class BoardCreate(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class BoardUpdate(BoardCreate):
    pass


class BoardOut(ApiModel):
    id: str
    name: str
    created_at: str = Field(alias="createdAt")


class ChecklistItem(ApiModel):
    id: str = ""
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    done: bool = False


class Comment(ApiModel):
    id: str = ""
    author: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] = "User"
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    created_at: str = Field(default_factory=utc_now, alias="createdAt")


class AttachmentOut(ApiModel):
    id: str
    name: str
    type: str
    size: int
    url: str
    created_at: str = Field(alias="createdAt")


class TaskFields(ApiModel):
    title: Name
    description: Annotated[str, StringConstraints(max_length=300)] = ""
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] = "todo"
    priority: Priority = "low"
    deadline: str = ""
    board_id: str = Field(default="default", alias="boardId")
    order: float = 0
    archived: bool = False
    recurrence: Recurrence = "none"
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]] = Field(default_factory=list, max_length=5)
    checklist: list[ChecklistItem] = Field(default_factory=list, max_length=8)
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn", max_length=12)
    assignee: Annotated[str, StringConstraints(max_length=50)] = ""
    color: str = "default"
    cover: Annotated[str, StringConstraints(max_length=8)] = ""
    comments: list[Comment] = Field(default_factory=list, max_length=30)
    estimated_minutes: int = Field(default=0, alias="estimatedMinutes", ge=0, le=100_000)
    time_spent_seconds: int = Field(default=0, alias="timeSpentSeconds", ge=0)
    timer_started_at: str = Field(default="", alias="timerStartedAt")

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.lower() for tag in tags))


class TaskCreate(TaskFields):
    id: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    completed_at: str = Field(default="", alias="completedAt")


class TaskUpdate(ApiModel):
    title: Name | None = None
    description: Annotated[str, StringConstraints(max_length=300)] | None = None
    status: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)] | None = None
    priority: Priority | None = None
    deadline: str | None = None
    board_id: str | None = Field(default=None, alias="boardId")
    order: float | None = None
    archived: bool | None = None
    recurrence: Recurrence | None = None
    tags: list[str] | None = Field(default=None, max_length=5)
    checklist: list[ChecklistItem] | None = Field(default=None, max_length=8)
    depends_on: list[str] | None = Field(default=None, alias="dependsOn", max_length=12)
    assignee: str | None = None
    color: str | None = None
    cover: str | None = None
    comments: list[Comment] | None = Field(default=None, max_length=30)
    estimated_minutes: int | None = Field(default=None, alias="estimatedMinutes", ge=0, le=100_000)
    time_spent_seconds: int | None = Field(default=None, alias="timeSpentSeconds", ge=0)
    timer_started_at: str | None = Field(default=None, alias="timerStartedAt")
    completed_at: str | None = Field(default=None, alias="completedAt")

    @field_validator("tags")
    @classmethod
    def unique_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        return list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))[:5]


class TaskOut(TaskFields):
    id: str
    created_at: str = Field(alias="createdAt")
    completed_at: str = Field(default="", alias="completedAt")
    attachments: list[AttachmentOut] = Field(default_factory=list)


class BatchTaskUpdate(ApiModel):
    ids: list[str] = Field(min_length=1, max_length=500)
    status: str | None = None
    priority: Priority | None = None
    archived: bool | None = None


class BatchResult(ApiModel):
    updated: int
    tasks: list[TaskOut]


class AutomationSettings(ApiModel):
    overdue_high: bool = Field(default=False, alias="overdueHigh")
    checklist_done: bool = Field(default=False, alias="checklistDone")
    due_today_tag: bool = Field(default=False, alias="dueTodayTag")


class WorkspacePayload(ApiModel):
    version: int = 4
    active_board_id: str = Field(default="default", alias="activeBoardId")
    boards: list[BoardOut]
    tasks: list[TaskCreate]
    columns: list[dict[str, Any]] = Field(default_factory=list)
    templates: list[dict[str, Any]] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    activity: list[dict[str, Any]] = Field(default_factory=list)
    accessibility: dict[str, Any] = Field(default_factory=dict)
    theme: str = "classic"
    language: str = "ru"
    sort: str = "manual"
    automations: AutomationSettings = Field(default_factory=AutomationSettings)


class WorkspaceOut(ApiModel):
    version: int = 4
    active_board_id: str = Field(alias="activeBoardId")
    boards: list[BoardOut]
    tasks: list[TaskOut]
    columns: list[dict[str, Any]]
    templates: list[dict[str, Any]]
    members: list[str]
    activity: list[dict[str, Any]]
    accessibility: dict[str, Any]
    theme: str
    language: str
    sort: str
    automations: AutomationSettings


class HealthOut(ApiModel):
    status: Literal["ok"]
    service: str
    version: str

