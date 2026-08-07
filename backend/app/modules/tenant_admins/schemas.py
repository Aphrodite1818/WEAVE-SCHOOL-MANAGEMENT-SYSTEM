# ====================================== #
#       tenant_admins/schemas.py         #
# ====================================== #

"""Tenant admins request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.tenant_admins.models import TenantAdminStatus


class InputBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class TenantAdminBase(InputBase):
    email: EmailStr


class TenantAdminCreate(TenantAdminBase):
    password: str = Field(..., min_length=8, max_length=64)


class TenantAdminUpdate(InputBase):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=64)
    account_status: TenantAdminStatus | None = None
    is_verified: bool | None = None
    is_active: bool | None = None
    last_login_at: datetime | None = None


class TenantAdminResponse(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    account_status: TenantAdminStatus
    is_verified: bool
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    passport_photo_url: str | None = None


class TenantAdminLoginProfile(OutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    account_status: TenantAdminStatus
    is_verified: bool
    is_active: bool
    passport_photo_url: str | None
