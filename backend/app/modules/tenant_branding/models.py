"""Database models for tenant branding."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class TenantBrandingThemeMode(str, Enum):
    """Supported tenant branding theme modes."""

    LIGHT = "light"
    DARK = "dark"


class TenantBranding(BaseModel):
    """Tenant-scoped branding configuration used inside school workspaces."""

    __tablename__ = "tenant_branding"

    logo_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    primary_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    accent_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    sidebar_color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
    )

    header_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#FFFFFF")
    surface_color: Mapped[str] = mapped_column(String(7), nullable=False, server_default="#FFFFFF")
    palette_key: Mapped[str] = mapped_column(
        String(32), nullable=False, default="blue", server_default="blue"
    )

    theme_mode: Mapped[TenantBrandingThemeMode] = mapped_column(
        SQLEnum(
            TenantBrandingThemeMode,
            name="tenant_branding_theme_mode",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TenantBrandingThemeMode.LIGHT,
        server_default=TenantBrandingThemeMode.LIGHT.value,
    )

    tokens: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    theme_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    token_schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4,
        server_default="4",
    )

    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_branding_tenant_id"),
        CheckConstraint(
            "palette_key IN ('blue', 'navy', 'gold', 'orange', 'emerald', 'forest', "
            "'violet', 'plum', 'rose', 'teal', 'cyan', 'slate')",
            name="ck_tenant_branding_palette_key",
        ),
        Index("ix_tenant_branding_tenant_enabled", "tenant_id", "is_enabled"),
    )
