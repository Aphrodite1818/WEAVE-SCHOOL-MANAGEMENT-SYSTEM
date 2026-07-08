"""Schemas for email outbox operations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.email_outbox.models import EmailOutboxStatus


class InputBase(BaseModel):
    """Base input schema."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
    )


class OutputBase(BaseModel):
    """Base output schema."""

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )


def _clean_optional_string(value: str | None) -> str | None:
    """Trim optional text."""

    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


class EmailOutboxCreate(InputBase):
    """Internal schema for queueing an email."""

    recipient_email: EmailStr
    recipient_name: str | None = Field(default=None, max_length=255)
    subject: str = Field(..., min_length=1, max_length=255)
    template_name: str = Field(..., min_length=1, max_length=120)
    template_context: dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = Field(default=4, ge=1, le=10)
    metadata_json: dict[str, Any] | None = None

    @field_validator("recipient_name", "subject", "template_name", mode="before")
    @classmethod
    def clean_text_fields(cls, value: str | None) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_string(value)


class EmailOutboxResponse(OutputBase):
    """Email outbox response schema."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    recipient_email: EmailStr
    recipient_name: str | None = None
    subject: str
    template_name: str
    template_context: dict[str, Any]
    status: EmailOutboxStatus
    attempts: int
    max_attempts: int
    next_retry_at: datetime | None = None
    processing_started_at: datetime | None = None
    sent_at: datetime | None = None
    failure_reason: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class EmailOutboxSummaryResponse(OutputBase):
    """Status counts for a tenant email outbox view."""

    total: int = 0
    pending: int = 0
    processing: int = 0
    sent: int = 0
    failed: int = 0
    cancelled: int = 0


class EmailOutboxRecoveryResponse(OutputBase):
    """Recovery result for stale processing emails."""

    checked: int = 0
    recovered: int = 0
    failed: int = 0


class EmailOutboxRetryResponse(OutputBase):
    """Retry result for failed emails."""

    retried: int = 0
