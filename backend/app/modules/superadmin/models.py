import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base
from app.shared.mixins import TimestampMixin, UUIDMixin


class SuperAdmin(UUIDMixin, TimestampMixin, Base):
    """Represent the SuperAdmin type."""
    __tablename__ = "superadmins"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SuperAdminInvite(UUIDMixin, TimestampMixin, Base):
    """Represent the SuperAdminInvite type."""
    __tablename__ = "superadmin_invites"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    invited_by_superadmin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("public.superadmins.id"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PlatformControl(UUIDMixin, TimestampMixin, Base):
    """Singleton platform-control record for emergency lockdown and maintenance mode."""

    __tablename__ = "platform_controls"

    lockdown_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        index=True,
    )
    lockdown_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lockdown_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="LearnlyAI is temporarily in maintenance mode. Please try again later.",
        server_default="LearnlyAI is temporarily in maintenance mode. Please try again later.",
    )
    enabled_by_superadmin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.superadmins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_by_superadmin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("public.superadmins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
