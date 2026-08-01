"""Pydantic schemas for tenant branding."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class InputBase(BaseModel):
    """Base request schema for tenant branding."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
    )


class OutputBase(BaseModel):
    """Base response schema for tenant branding."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        use_enum_values=True,
    )


class TenantBrandingUpdate(InputBase):
    """Admin selects one backend-controlled palette; arbitrary colours are forbidden."""

    palette_key: (
        Literal[
            "blue",
            "navy",
            "gold",
            "orange",
            "emerald",
            "forest",
            "violet",
            "plum",
            "rose",
            "teal",
            "cyan",
            "slate",
        ]
        | None
    ) = None
    is_enabled: bool | None = None


class TenantBrandingResponse(OutputBase):
    """Tenant branding payload returned to tenant admins."""

    id: uuid.UUID | None = None
    tenant_id: uuid.UUID
    school_name: str
    logo_url: str | None = None
    palette_key: str
    light_tokens: dict[str, str]
    dark_tokens: dict[str, str]
    is_enabled: bool
    theme_version: int
    token_schema_version: int
    updated_by_admin_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TenantBrandingEffectiveResponse(OutputBase):
    """Branding response used by authenticated tenant workspaces."""

    tenant_id: uuid.UUID
    school_name: str
    logo_url: str | None = None
    is_enabled: bool
    theme_version: int
    token_schema_version: int
    is_default_theme: bool
    light_tokens: dict[str, str]
    dark_tokens: dict[str, str]


__all__ = [
    "TenantBrandingEffectiveResponse",
    "TenantBrandingResponse",
    "TenantBrandingUpdate",
]
