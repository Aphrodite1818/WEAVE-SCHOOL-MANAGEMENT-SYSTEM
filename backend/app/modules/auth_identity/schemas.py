# ====================================== #
#       auth_identity/schemas.py         #
# ====================================== #

"""Auth identity request and response schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.auth_identity.models import ActorType, IdentifierType


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


class AuthIdentityBase(InputBase):
    identifier: str
    identifier_type: IdentifierType
    actor_type: ActorType
    actor_id: uuid.UUID
    is_active: bool = True


class AuthIdentityCreate(AuthIdentityBase):
    """Used internally when creating a new identity record."""


class AuthIdentityUpdate(InputBase):
    """Used to change identifier or deactivate identity."""

    identifier: str | None = None
    is_active: bool | None = None


class AuthIdentityResponse(OutputBase):
    """Used when returning identity records from service/repository."""

    tenant_id: uuid.UUID | None = None
    id: uuid.UUID
    identifier: str
    identifier_type: IdentifierType
    actor_type: ActorType
    actor_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IdentityResolution(OutputBase):
    """Returned after resolving a login identifier."""

    actor_type: ActorType
    actor_id: uuid.UUID
    tenant_id: uuid.UUID | None = None
    lookup_table: str
