#======================================#
#            auth/schemas.py           #
#======================================#

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class Token(BaseModel):
    """Represent the Token type."""
    access_token: str
    token_type: str = "bearer"


class LoginSessionUser(BaseModel):
    """Compact authenticated actor payload returned to the frontend."""

    id: str | None = None
    tenant_id: str | None = None
    school_name: str | None = None
    email: str | None = None
    admission_number: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    actor_type: str | None = None
    account_type: str | None = None
    role: str | None = None
    password_reset_required: bool | None = None
    profile_status: str | None = None
    meta: dict[str, Any] | None = None

class LoginRequest(BaseModel):
    """Pydantic schema for the auth domain."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True, extra="forbid")

    identifier: str = Field(..., alias="email", min_length=1, max_length=255)
    password: str


class UpdatePassword(BaseModel):
    """Represent the UpdatePassword type."""
    email: EmailStr
    new_password: str
    reset_token: str

class RequestOTP(BaseModel):
    """Represent the RequestOTP type."""
    email: EmailStr
    purpose: Literal["verification", "password_reset"] # "verification" or "password_reset"

class VerifyOTP(BaseModel):
    """Represent the VerifyOTP type."""
    email: EmailStr
    code: str
    purpose: Literal["verification", "password_reset"]


class TenantActivationRequest(BaseModel):
    """Pydantic schema for the auth domain."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    token: str = Field(..., min_length=20)


class UserInviteAcceptanceRequest(BaseModel):
    """Pydantic schema for the auth domain."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    token: str = Field(..., min_length=20)
