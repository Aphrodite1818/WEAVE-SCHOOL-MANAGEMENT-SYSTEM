# ==========================#
# cbt/auth/schemas.py
# ==========================#


"""Schema definitions for CBT machine and staff authentication."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.cbt.enums import CBTServerStatus


class AuthenticatedCBTServer(BaseModel):
    """Trusted machine context produced after machine credential authentication.

    ``credential_id`` deliberately travels with the socket/session context so long-lived
    transports can prove that the *same* credential which opened the connection is still
    authorized after server revocation or credential rotation.
    """

    model_config = ConfigDict(frozen=True)

    server_id: UUID
    credential_id: UUID
    tenant_id: UUID
    server_name: str
    status: CBTServerStatus


class CBTStaffLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class CBTStaffAuthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_id: UUID
    membership_id: UUID | None = None
    tenant_id: UUID
    role: Literal["admin", "teacher"]
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
