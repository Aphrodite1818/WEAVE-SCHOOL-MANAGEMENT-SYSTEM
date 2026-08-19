"""Pydantic schemas for communications."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.communications.enums import (
    AnnouncementAudienceType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementStatus,
    CommunicationActorType,
    ConversationType,
    NotificationSourceType,
    NotificationStatus,
)

_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class InputBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=True)


class OutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class ActorIdentity(OutputBase):
    actor_type: CommunicationActorType
    actor_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    label: str
    group_label: str | None = None


class RecipientTarget(InputBase):
    actor_type: CommunicationActorType
    actor_id: uuid.UUID


class AvailableRecipientGroup(OutputBase):
    label: str
    recipients: list[ActorIdentity]


class AvailableRecipientsResponse(OutputBase):
    groups: list[AvailableRecipientGroup]


class MessageCreate(InputBase):
    body: str = Field(..., min_length=1, max_length=5000)


class ConversationCreate(MessageCreate):
    recipient: RecipientTarget
    subject: str | None = Field(default=None, max_length=200)


class MessageResponse(OutputBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    sender_actor_type: CommunicationActorType
    sender_actor_id: uuid.UUID
    body: str
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None = None
    deleted_at: datetime | None = None


class ConversationParticipantResponse(OutputBase):
    id: uuid.UUID
    conversation_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    actor_type: CommunicationActorType
    actor_id: uuid.UUID
    label: str | None = None
    group_label: str | None = None
    joined_at: datetime
    left_at: datetime | None = None
    last_read_message_id: uuid.UUID | None = None


class ConversationResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    conversation_type: ConversationType
    created_by_actor_type: CommunicationActorType
    created_by_actor_id: uuid.UUID
    subject: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    participants: list[ConversationParticipantResponse] = Field(default_factory=list)
    messages: list[MessageResponse] = Field(default_factory=list)
    unread_count: int = 0


class ConversationListResponse(OutputBase):
    items: list[ConversationResponse]
    total: int
    unread_count: int


class AnnouncementAudienceCreate(InputBase):
    audience_type: AnnouncementAudienceType
    tenant_target_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None


class AnnouncementCreate(InputBase):
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=3, max_length=10000)
    category: AnnouncementCategory = AnnouncementCategory.GENERAL
    priority: AnnouncementPriority = AnnouncementPriority.NORMAL
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool = False
    audiences: list[AnnouncementAudienceCreate] = Field(..., min_length=1)


class AnnouncementUpdate(InputBase):
    """Sparse announcement update; schedule timestamps may be cleared explicitly."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=3, max_length=10000)
    category: AnnouncementCategory | None = None
    priority: AnnouncementPriority | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool | None = None
    audiences: list[AnnouncementAudienceCreate] | None = Field(default=None, min_length=1)

    @field_validator(
        "title",
        "body",
        "category",
        "priority",
        "is_pinned",
        "audiences",
        mode="before",
    )
    @classmethod
    def reject_null_non_clearable_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "AnnouncementUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one announcement field must be provided")
        return self


class AnnouncementPublishRequest(InputBase):
    publish_at: datetime | None = None


class AnnouncementAudienceResponse(OutputBase):
    id: uuid.UUID
    announcement_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    audience_type: AnnouncementAudienceType
    tenant_target_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None


class AnnouncementResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    created_by_actor_type: CommunicationActorType
    created_by_actor_id: uuid.UUID
    title: str
    body: str
    category: AnnouncementCategory
    priority: AnnouncementPriority
    status: AnnouncementStatus
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool
    archived_at: datetime | None = None
    audiences: list[AnnouncementAudienceResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnnouncementListResponse(OutputBase):
    items: list[AnnouncementResponse]
    total: int


class RecipientPreviewResponse(OutputBase):
    audience_label: str
    recipient_count: int
    excluded_count: int = 0
    excluded_reasons: list[str] = Field(default_factory=list)
    recipients: list[ActorIdentity] = Field(default_factory=list)


class NotificationResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    recipient_actor_type: CommunicationActorType
    recipient_actor_id: uuid.UUID
    source_type: NotificationSourceType
    source_id: uuid.UUID
    title: str
    preview: str
    action_path: str | None = None
    status: NotificationStatus
    delivered_at: datetime
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None
    dismissed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(OutputBase):
    items: list[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(OutputBase):
    unread_count: int
