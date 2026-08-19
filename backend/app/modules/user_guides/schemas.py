"""Schemas for product-guide state persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GuideStatus = Literal["not_started", "in_progress", "dismissed", "completed"]
_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


class UserGuideStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: GuideStatus | None = None
    current_step: str | None = Field(default=None, max_length=100)
    skipped_steps: list[str] | None = Field(default=None, max_length=50)
    remind_after: datetime | None = None

    @field_validator("status", "skipped_steps", mode="before")
    @classmethod
    def reject_null_non_clearable_fields(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "UserGuideStateUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one guide field must be provided")
        return self


class UserGuideStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None
    guide_key: str
    actor_type: str
    actor_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    status: GuideStatus
    current_step: str | None = None
    skipped_steps: list[str] = Field(default_factory=list)
    remind_after: datetime | None = None
    dismissed_at: datetime | None = None
    completed_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
