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
    author_id: str | None = Field(default=None, alias="authorId")
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    mentions: list[str] = Field(default_factory=list, max_length=20)
    parent_id: str | None = Field(default=None, alias="parentId")
    created_at: str = Field(default_factory=utc_now, alias="createdAt")
    edited_at: str | None = Field(default=None, alias="editedAt")
    resolved_at: str | None = Field(default=None, alias="resolvedAt")
    reactions: dict[str, list[str]] = Field(default_factory=dict)


class CommentCreate(ApiModel):
    id: str | None = None
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    parent_id: str | None = Field(default=None, alias="parentId")


class CommentUpdate(ApiModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)] | None = None
    resolved: bool | None = None


class CommentReaction(ApiModel):
    emoji: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16)]


class CommentOut(Comment):
    task_id: str = Field(alias="taskId")


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
    start_date: str = Field(default="", alias="startDate")
    goal_id: str = Field(default="", alias="goalId")
    milestone: bool = False

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
    start_date: str | None = Field(default=None, alias="startDate")
    goal_id: str | None = Field(default=None, alias="goalId")
    milestone: bool | None = None

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
    revision: int = Field(default=0, ge=0)
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
    revision: int
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


class RegisterRequest(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class LoginRequest(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
    password: str


class InvitationCreate(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
    role: Literal["editor", "viewer"] = "editor"


class InvitationOut(ApiModel):
    id: str
    email: str
    role: Literal["editor", "viewer"]
    token: str | None = None
    expires_at: str = Field(alias="expiresAt")
    accepted_at: str | None = Field(default=None, alias="acceptedAt")
    created_at: str = Field(alias="createdAt")


class InvitationAccept(ApiModel):
    token: str
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class PasswordResetRequest(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]


class PasswordResetConfirm(ApiModel):
    token: str
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class SessionOut(ApiModel):
    id: str
    user_agent: str = Field(alias="userAgent")
    ip_address: str = Field(alias="ipAddress")
    created_at: str = Field(alias="createdAt")
    last_seen_at: str = Field(alias="lastSeenAt")
    current: bool = False


class UserOut(ApiModel):
    id: str
    email: str
    name: str
    role: Literal["owner", "editor", "viewer"]
    created_at: str = Field(alias="createdAt")


class AuthToken(ApiModel):
    access_token: str = Field(alias="accessToken")
    token_type: Literal["bearer"] = Field(default="bearer", alias="tokenType")
    user: UserOut


class MemberUpdate(ApiModel):
    email: str
    role: Literal["owner", "editor", "viewer"]


class ApiTokenCreate(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


class ApiTokenOut(ApiModel):
    id: str
    name: str
    token: str | None = None
    created_at: str = Field(alias="createdAt")
    last_used_at: str | None = Field(default=None, alias="lastUsedAt")


class SavedFilterCreate(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    query: dict[str, Any]


class SavedFilterOut(SavedFilterCreate):
    id: str
    created_at: str = Field(alias="createdAt")


class NotificationOut(ApiModel):
    id: str
    kind: str
    title: str
    body: str
    read_at: str | None = Field(default=None, alias="readAt")
    created_at: str = Field(alias="createdAt")


class NotificationPreferences(ApiModel):
    in_app_enabled: bool = Field(default=True, alias="inAppEnabled")
    push_enabled: bool = Field(default=True, alias="pushEnabled")
    email_enabled: bool = Field(default=False, alias="emailEnabled")


class GoalCreate(ApiModel):
    title: Name
    description: Annotated[str, StringConstraints(max_length=500)] = ""
    target_date: str = Field(default="", alias="targetDate")
    color: str = "lime"


class GoalOut(GoalCreate):
    id: str
    progress: int = Field(default=0, ge=0, le=100)
    task_count: int = Field(default=0, alias="taskCount")
    completed_count: int = Field(default=0, alias="completedCount")
    created_at: str = Field(alias="createdAt")


class WatcherUpdate(ApiModel):
    watching: bool = True


class JobOut(ApiModel):
    id: str
    kind: str
    status: Literal["pending", "running", "done", "failed"]
    attempts: int
    last_error: str | None = Field(default=None, alias="lastError")
    created_at: str = Field(alias="createdAt")


class WebhookCreate(ApiModel):
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500)]
    events: list[str] = Field(default_factory=lambda: ["workspace.updated"], max_length=20)


class WebhookOut(ApiModel):
    id: str
    url: str
    events: list[str]
    active: bool
    created_at: str = Field(alias="createdAt")


class RevisionOut(ApiModel):
    id: str
    revision: int
    actor_id: str | None = Field(default=None, alias="actorId")
    created_at: str = Field(alias="createdAt")

