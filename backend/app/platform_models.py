from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from .models import ApiModel


ShortName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class WorkspaceCreate(ApiModel):
    name: ShortName


class WorkspaceOut(ApiModel):
    id: str
    name: str
    slug: str
    role: Literal["owner", "editor", "viewer", "guest"]
    created_at: str = Field(alias="createdAt")


class WorkspaceMemberUpdate(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]
    role: Literal["owner", "editor", "viewer", "guest"]


class BoardPermissionUpdate(ApiModel):
    user_id: str = Field(alias="userId")
    role: Literal["editor", "viewer"]


class TotpVerify(ApiModel):
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=8)]


class EmailVerificationConfirm(ApiModel):
    token: str


class PasskeyRegistrationComplete(ApiModel):
    challenge_id: str = Field(alias="challengeId")
    credential: dict[str, Any]
    device_name: str = Field(default="Passkey", alias="deviceName")


class PasskeyAuthenticationStart(ApiModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]


class PasskeyAuthenticationComplete(ApiModel):
    challenge_id: str = Field(alias="challengeId")
    credential: dict[str, Any]


class PushSubscriptionCreate(ApiModel):
    endpoint: str
    keys: dict[str, str]


class IntegrationCreate(ApiModel):
    workspace_id: str = Field(alias="workspaceId")
    kind: Literal["github", "slack", "telegram", "calendar"]
    name: ShortName
    config: dict[str, Any] = Field(default_factory=dict)


class IntegrationMessage(ApiModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] = "Flowboard integration connected"


class CustomFieldCreate(ApiModel):
    workspace_id: str = Field(alias="workspaceId")
    name: ShortName
    field_type: Literal["text", "number", "date", "select", "user"] = Field(alias="fieldType")
    options: list[str] = Field(default_factory=list, max_length=50)
    required: bool = False


class PublicShareCreate(ApiModel):
    workspace_id: str = Field(alias="workspaceId")
    board_id: str | None = Field(default=None, alias="boardId")
    mode: Literal["view", "form"] = "view"
    password: str | None = Field(default=None, max_length=128)
    expires_at: str | None = Field(default=None, alias="expiresAt")


class PublicFormSubmission(ApiModel):
    title: ShortName
    description: Annotated[str, StringConstraints(max_length=1000)] = ""
    values: dict[str, Any] = Field(default_factory=dict)


class CollaborationOperation(ApiModel):
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    task_id: str = Field(alias="taskId")
    client_id: str = Field(alias="clientId")
    field: str
    operation: dict[str, Any]
    lamport: int = Field(ge=0)


class AssistantRequest(ApiModel):
    action: Literal["checklist", "summary", "prioritize", "capacity"]
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    text: str = Field(default="", max_length=10_000)
    task: dict[str, Any] | None = None
