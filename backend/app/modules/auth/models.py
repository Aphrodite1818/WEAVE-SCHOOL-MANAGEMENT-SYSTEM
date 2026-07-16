# ====================================== #
#             auth/models.py             #
# ====================================== #

"""Database models for auth records and persistent login sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class AuthPurpose(str, PyEnum):
    """Supported one-time authentication record purposes."""

    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"
    TENANT_ACTIVATION = "tenant_activation"
    USER_INVITE = "user_invite"


class AuthRecord(UUIDMixin, TimestampMixin, Base):
    """Stores OTP, password-reset, activation, and invite secrets."""

    __tablename__ = "auth"

    __table_args__ = (
        Index(
            "ix_auth_active_email_purpose",
            "tenant_id",
            "email",
            "purpose",
            "expires_at",
            postgresql_where=text("is_used = false"),
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenants.id"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    hashed_value: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[AuthPurpose] = mapped_column(
        SQLEnum(
            AuthPurpose,
            name="otppurpose",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )


class AuthSessionActorType(str, PyEnum):
    """Actors that can own a login session."""

    SUPERADMIN = "superadmin"
    TENANT_ADMIN = "tenant_admin"
    TEACHER_ACCOUNT = "teacher_account"
    TEACHER = "teacher"
    STAFF = "staff"
    PARENT_ACCOUNT = "parent_account"
    PARENT = "parent"
    STUDENT = "student"


class AuthSession(UUIDMixin, TimestampMixin, Base):
    """Represents one persistent browser/device login session."""

    __tablename__ = "auth_sessions"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="NULL for superadmin sessions; required for tenant actor sessions.",
    )

    actor_type: Mapped[AuthSessionActorType] = mapped_column(
        SQLEnum(
            AuthSessionActorType,
            name="auth_session_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        index=True,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="ID of the actor in its own table. Polymorphic, so no FK here.",
    )

    session_jti: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        doc="Stable unique ID for this session/token family.",
    )

    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    remember_me: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    compromised_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            """
            (
                actor_type = 'superadmin'
                AND tenant_id IS NULL
            )
            OR
            (
                actor_type IN ('teacher_account', 'parent_account')
                AND tenant_id IS NULL
            )
            OR
            (
                actor_type NOT IN ('superadmin', 'teacher_account', 'parent_account')
                AND tenant_id IS NOT NULL
            )
            """,
            name="ck_auth_sessions_tenant_scope",
        ),
        Index("ix_auth_sessions_actor", "actor_type", "actor_id"),
        Index(
            "ix_auth_sessions_tenant_actor",
            "tenant_id",
            "actor_type",
            "actor_id",
        ),
        Index(
            "ix_auth_sessions_active_lookup",
            "actor_type",
            "actor_id",
            "revoked_at",
            "expires_at",
        ),
    )

    @staticmethod
    def _ensure_timezone_aware(value: datetime) -> datetime:
        """Return a timezone-aware datetime."""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def is_revoked(self) -> bool:
        """Return whether the session has been explicitly revoked."""

        return self.revoked_at is not None

    @property
    def is_compromised(self) -> bool:
        """Return whether refresh-token reuse has marked the session unsafe."""

        return self.compromised_at is not None

    @property
    def is_expired(self) -> bool:
        """Return whether the session has passed its expiry time."""

        return datetime.now(timezone.utc) >= self._ensure_timezone_aware(self.expires_at)

    @property
    def is_active(self) -> bool:
        """Return whether the session can still be used."""

        return not self.is_revoked and not self.is_compromised and not self.is_expired


class AuthRefreshToken(UUIDMixin, TimestampMixin, Base):
    """Stores hashed refresh tokens for refresh-token rotation."""

    __tablename__ = "auth_refresh_tokens"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        doc="Hash/HMAC digest of the raw refresh token.",
    )
    token_jti: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique ID for this specific refresh token.",
    )

    issued_ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    issued_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    reuse_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_auth_refresh_tokens_session_active",
            "session_id",
            "revoked_at",
            "expires_at",
        ),
        Index(
            "ix_auth_refresh_tokens_rotation_state",
            "session_id",
            "used_at",
            "revoked_at",
        ),
    )

    @staticmethod
    def _ensure_timezone_aware(value: datetime) -> datetime:
        """Return a timezone-aware datetime."""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @property
    def is_used(self) -> bool:
        """Return whether this refresh token has already been rotated."""

        return self.used_at is not None

    @property
    def is_revoked(self) -> bool:
        """Return whether this refresh token has been explicitly revoked."""

        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Return whether this refresh token has passed its expiry time."""

        return datetime.now(timezone.utc) >= self._ensure_timezone_aware(self.expires_at)

    @property
    def is_reuse_detected(self) -> bool:
        """Return whether this token has already triggered reuse detection."""

        return self.reuse_detected_at is not None

    @property
    def is_active(self) -> bool:
        """Return whether this refresh token can still be exchanged."""

        return not self.is_used and not self.is_revoked and not self.is_expired


class AuthRefreshTokenReuseEvent(UUIDMixin, Base):
    """Append-only audit record for one rejected refresh-token reuse attempt."""

    __tablename__ = "auth_refresh_token_reuse_events"

    refresh_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_auth_refresh_token_reuse_events_window", "detected_at", "id"),
    )
