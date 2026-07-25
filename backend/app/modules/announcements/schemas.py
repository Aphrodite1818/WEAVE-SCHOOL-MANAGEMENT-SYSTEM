#==========================#
#  Announcement schemas.py #
#==========================#

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.announcements.models import (
    AnnouncementActorType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementReadStatus,
    AnnouncementRecipientRole,
    AnnouncementStatus,
    AnnouncementTargetType,
)


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=True,
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


class AnnouncementTargetCreate(InputBase):
    target_type: AnnouncementTargetType
    role: AnnouncementRecipientRole | None = None
    class_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    parent_membership_id: uuid.UUID | None = None
    teacher_membership_id: uuid.UUID | None = None


class AnnouncementTargetResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    announcement_id: uuid.UUID
    target_type: AnnouncementTargetType
    role: AnnouncementRecipientRole | None = None
    class_id: uuid.UUID | None = None
    student_id: uuid.UUID | None = None
    parent_membership_id: uuid.UUID | None = None
    teacher_membership_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class AnnouncementCreate(InputBase):
    title: str = Field(..., min_length=3, max_length=200, description="Title of the announcement.")
    body: str = Field(..., min_length=3, description="Main announcement body/message.")
    category: AnnouncementCategory = AnnouncementCategory.GENERAL
    priority: AnnouncementPriority = AnnouncementPriority.NORMAL
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool = False
    targets: list[AnnouncementTargetCreate] = Field(..., min_length=1)


class AnnouncementUpdate(InputBase):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=3)
    category: AnnouncementCategory | None = None
    priority: AnnouncementPriority | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool | None = None
    targets: list[AnnouncementTargetCreate] | None = None


class AnnouncementPublishRequest(InputBase):
    publish_at: datetime | None = None


class AnnouncementArchiveRequest(InputBase):
    reason: str | None = Field(default=None, max_length=255)


class AnnouncementReadRequest(InputBase):
    status: AnnouncementReadStatus = AnnouncementReadStatus.READ


class AnnouncementReadResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    announcement_id: uuid.UUID
    actor_type: AnnouncementRecipientRole
    actor_id: uuid.UUID
    status: AnnouncementReadStatus
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnnouncementResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    body: str
    category: AnnouncementCategory
    priority: AnnouncementPriority
    status: AnnouncementStatus
    created_by_actor_type: AnnouncementActorType
    created_by_actor_id: uuid.UUID
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool
    targets: list[AnnouncementTargetResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AnnouncementFeedItemResponse(OutputBase):
    id: uuid.UUID
    title: str
    body: str
    category: AnnouncementCategory
    priority: AnnouncementPriority
    status: AnnouncementStatus
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    is_pinned: bool
    is_read: bool = False
    is_acknowledged: bool = False
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AnnouncementListResponse(OutputBase):
    items: list[AnnouncementResponse]
    total: int


class AnnouncementFeedResponse(OutputBase):
    items: list[AnnouncementFeedItemResponse]
    total: int
    unread_count: int
