"""Pydantic schemas for tenant branding."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


_PATCH_NULL_ERROR = "cannot be null; omit the field to leave the current value unchanged"


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
            "royal_gold",
            "navy",
            "navy_gold",
            "indigo_gold",
            "gold",
            "black_gold",
            "orange",
            "emerald",
            "green_gold",
            "forest",
            "teal_gold",
            "violet",
            "purple_gold",
            "plum",
            "burgundy_cream",
            "maroon_gold",
            "rose",
            "crimson_gray",
            "red_navy",
            "teal",
            "cyan",
            "sky_navy",
            "slate",
            "charcoal_red",
        ]
        | None
    ) = None
    is_enabled: bool | None = None

    @field_validator("palette_key", "is_enabled", mode="before")
    @classmethod
    def reject_null_patch_values(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} {_PATCH_NULL_ERROR}")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "TenantBrandingUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one branding field must be provided")
        return self


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
