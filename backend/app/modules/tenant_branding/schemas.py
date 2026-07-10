"""Pydantic schemas for tenant branding."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.tenant_branding.models import TenantBrandingThemeMode


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


def _clean_optional_text(value: object) -> str | None:
    """Trim optional string values and convert blanks to None."""

    if value is None:
        return None

    cleaned_value = str(value).strip()
    return cleaned_value or None


class TenantBrandingUpdate(InputBase):
    """Admin-controlled branding update payload."""

    brand_name: str | None = Field(default=None, max_length=255)
    primary_color: str | None = Field(default=None, min_length=4, max_length=7)
    accent_color: str | None = Field(default=None, min_length=4, max_length=7)
    sidebar_color: str | None = Field(default=None, min_length=4, max_length=7)
    theme_mode: TenantBrandingThemeMode | None = None
    is_enabled: bool | None = None

    @field_validator(
        "brand_name",
        "primary_color",
        "accent_color",
        "sidebar_color",
        mode="before",
    )
    @classmethod
    def clean_optional_strings(cls, value: object) -> str | None:
        """Normalize optional text fields."""

        return _clean_optional_text(value)


class TenantBrandingResponse(OutputBase):
    """Tenant branding payload returned to tenant admins."""

    id: uuid.UUID | None = None
    tenant_id: uuid.UUID
    brand_name: str
    logo_url: str | None = None
    primary_color: str
    accent_color: str
    sidebar_color: str
    theme_mode: TenantBrandingThemeMode
    tokens: dict[str, str]
    is_enabled: bool
    theme_version: int
    updated_by_admin_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TenantBrandingEffectiveResponse(OutputBase):
    """Branding response used by authenticated tenant workspaces."""

    tenant_id: uuid.UUID
    brand_name: str
    logo_url: str | None = None
    primary_color: str
    accent_color: str
    sidebar_color: str
    theme_mode: TenantBrandingThemeMode
    tokens: dict[str, str]
    is_enabled: bool
    theme_version: int
    is_default_theme: bool


class TenantBrandingResetResponse(OutputBase):
    """Response returned after branding is reset to Learnly defaults."""

    branding: TenantBrandingResponse
    message: str = "Tenant branding reset to Learnly defaults."
