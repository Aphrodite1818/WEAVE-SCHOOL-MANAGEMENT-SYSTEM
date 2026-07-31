"""Schemas for product-guide state persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GuideStatus = Literal["not_started", "in_progress", "dismissed", "completed"]


class UserGuideStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: GuideStatus | None = None
    current_step: str | None = Field(default=None, max_length=100)
    skipped_steps: list[str] | None = Field(default=None, max_length=50)
    remind_after: datetime | None = None


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
