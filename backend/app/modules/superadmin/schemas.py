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
        default="Weave is temporarily in maintenance mode. Please try again later.",
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


class SecurityIPBlockCreate(InputBase):
    """Create a manual IP block rule."""

    ip_address: str = Field(min_length=3, max_length=64)
    reason: str = Field(min_length=3, max_length=255)
    duration_hours: int | None = Field(default=24, gt=0, le=24 * 30)


class SecurityIPBlockUnblock(InputBase):
    """Disable a manual IP block rule."""

    reason: str = Field(default="Manual unblock by superadmin", min_length=3, max_length=255)


class SecurityIPBlockResponse(OutputBase):
    """Safe response for a manual IP block rule."""

    id: uuid.UUID
    ip_address_label: str
    reason: str
    blocked_by_superadmin_id: uuid.UUID | None = None
    blocked_at: datetime
    expires_at: datetime | None = None
    unblocked_by_superadmin_id: uuid.UUID | None = None
    unblocked_at: datetime | None = None
    unblock_reason: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SecurityRevokeIPSessionsRequest(InputBase):
    """Revoke active sessions created from an IP address."""

    ip_address: str = Field(min_length=3, max_length=64)
    reason: str = Field(default="manual_ip_containment", min_length=3, max_length=100)


class SecurityRevokeActorSessionsRequest(InputBase):
    """Revoke active sessions for one actor."""

    actor_type: str = Field(min_length=3, max_length=50)
    actor_id: uuid.UUID
    reason: str = Field(default="manual_actor_containment", min_length=3, max_length=100)


class SecurityActionResponse(OutputBase):
    """Result from a superadmin security response action."""

    detail: str
    affected_count: int = 0
