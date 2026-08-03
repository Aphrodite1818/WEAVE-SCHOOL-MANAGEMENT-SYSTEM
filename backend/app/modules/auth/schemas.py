"""Authentication request and response schemas."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginSessionUser(BaseModel):
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
    passport_photo_url: str | None = None
    tenant_logo_url: str | None = None
    legal_compliance_required: bool | None = None
    legal_compliance_policy_version: str | None = None
    legal_compliance_accepted_at: str | None = None


class SessionBootstrapResponse(BaseModel):
    authenticated: bool = True
    actor_type: str
    account_type: str
    role: str | None = None
    tenant_id: str | None = None
    email: str | None = None
    password_reset_required: bool | None = None
    user: LoginSessionUser
    legal_compliance_required: bool = True
    legal_compliance_policy_version: str
    legal_compliance_accepted_at: str | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    identifier: str = Field(
        ...,
        alias="email",
        min_length=1,
        max_length=255,
    )
    password: str
    remember_me: bool = False


class MembershipSelectionRequest(BaseModel):
    """Select one usable tenant membership after global-account login."""

    membership_id: UUID
    remember_me: bool = False


class UpdatePassword(BaseModel):
    email: EmailStr
    new_password: str = Field(min_length=8, max_length=128)
    reset_token: str = Field(min_length=20, max_length=500)


class RequestOTP(BaseModel):
    email: EmailStr
    purpose: Literal["verification", "password_reset"]


class VerifyOTP(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    purpose: Literal["verification", "password_reset"]


class TenantActivationRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    token: str = Field(..., min_length=20, max_length=500)
