"""Schemas for the Weave -> CBT tenant-branding projection."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CBTBrandingProjectionResponse(BaseModel):
    """Effective school branding consumed by a paired CBT server."""

    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    school_name: str
    logo_url: str | None = None
    logo_revision: UUID | None = None
    is_enabled: bool
    is_default_theme: bool
    theme_version: int
    token_schema_version: int
    light_tokens: dict[str, str]
    dark_tokens: dict[str, str]
