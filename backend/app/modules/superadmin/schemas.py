import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InputBase(BaseModel):
    """Pydantic schema for the superadmin domain."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class OutputBase(BaseModel):
    """Pydantic schema for the superadmin domain."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SuperadminInviteCreate(InputBase):
    """Pydantic schema for the superadmin domain."""
    email: EmailStr


class SuperadminResponse(OutputBase):
    """Pydantic schema for the superadmin domain."""
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PlatformLockdownRequest(InputBase):
    """Request payload for enabling platform lockdown."""

    reason: str = Field(min_length=3, max_length=255)
    message: str = Field(
        default="LearnlyAI is temporarily in maintenance mode. Please try again later.",
        min_length=10,
        max_length=500,
    )
    confirmation: str = Field(min_length=8, max_length=8)


class PlatformUnlockRequest(InputBase):
    """Request payload for disabling platform lockdown."""

    confirmation: str = Field(min_length=6, max_length=6)


class PlatformControlResponse(OutputBase):
    """Current platform lockdown/control state."""

    id: uuid.UUID | None = None
    lockdown_enabled: bool
    lockdown_reason: str | None = None
    lockdown_message: str
    enabled_by_superadmin_id: uuid.UUID | None = None
    enabled_at: datetime | None = None
    disabled_by_superadmin_id: uuid.UUID | None = None
    disabled_at: datetime | None = None
    updated_at: datetime | None = None
