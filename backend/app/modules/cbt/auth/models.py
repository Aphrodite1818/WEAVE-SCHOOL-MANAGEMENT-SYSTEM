"""Persistent authorization state for human actors using paired CBT servers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, BaseModel, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class CBTActorAuthorization(BaseModel):
    """One cloud authorization family established by a successful CBT staff login.

    The authorization belongs to a tenant actor, not to a specific CBT server.
    A valid machine credential from the same tenant is still required on every
    protected CBT-cloud request.

    Only the current access-token fingerprint is stored. Rotating the short-lived
    access token therefore does not create an ever-growing access-token table.
    """

    __tablename__ = "cbt_actor_authorizations"

    role: Mapped[str] = mapped_column(String(16), nullable=False)

    teacher_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.teacher_accounts.id", ondelete="CASCADE"),
        nullable=True,
    )
    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.teacher_memberships.id", ondelete="CASCADE"),
        nullable=True,
    )
    tenant_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenant_admins.id", ondelete="CASCADE"),
        nullable=True,
    )

    access_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    access_token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            """
            (
                role = 'teacher'
                AND teacher_account_id IS NOT NULL
                AND teacher_membership_id IS NOT NULL
                AND tenant_admin_id IS NULL
            )
            OR
            (
                role = 'admin'
                AND teacher_account_id IS NULL
                AND teacher_membership_id IS NULL
                AND tenant_admin_id IS NOT NULL
            )
            """,
            name="ck_cbt_actor_authorizations_actor_consistency",
        ),
        CheckConstraint(
            "access_token_expires_at <= absolute_expires_at",
            name="ck_cbt_actor_authorizations_access_within_absolute_expiry",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_cbt_actor_authorizations_valid_revocation",
        ),
        Index(
            "ix_cbt_actor_authorizations_tenant_role",
            "tenant_id",
            "role",
        ),
        Index(
            "ix_cbt_actor_authorizations_teacher_membership_revoked",
            "teacher_membership_id",
            "revoked_at",
            postgresql_where=text("teacher_membership_id IS NOT NULL"),
        ),
        Index(
            "ix_cbt_actor_authorizations_teacher_account_revoked",
            "teacher_account_id",
            "revoked_at",
            postgresql_where=text("teacher_account_id IS NOT NULL"),
        ),
        Index(
            "ix_cbt_actor_authorizations_admin_revoked",
            "tenant_admin_id",
            "revoked_at",
            postgresql_where=text("tenant_admin_id IS NOT NULL"),
        ),
        Index(
            "ix_cbt_actor_authorizations_absolute_expiry",
            "absolute_expires_at",
        ),
    )


class CBTActorRefreshToken(UUIDMixin, TimestampMixin, Base):
    """One opaque refresh token belonging to a CBT actor authorization family.

    Raw refresh tokens leave Weave once and are never persisted. Consumed-token
    history is retained so reuse can revoke the whole authorization family.
    """

    __tablename__ = "cbt_actor_refresh_tokens"

    authorization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_actor_authorizations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    reuse_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_actor_refresh_tokens.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_cbt_actor_refresh_tokens_valid_expiry",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_consumed_at",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_revocation",
        ),
        CheckConstraint(
            "reuse_detected_at IS NULL OR reuse_detected_at >= created_at",
            name="ck_cbt_actor_refresh_tokens_valid_reuse",
        ),
        CheckConstraint(
            "replaced_by_token_id IS NULL OR replaced_by_token_id <> id",
            name="ck_cbt_actor_refresh_tokens_not_self_replaced",
        ),
        Index(
            "ix_cbt_actor_refresh_tokens_authorization_expiry",
            "authorization_id",
            "expires_at",
        ),
        Index(
            "ix_cbt_actor_refresh_tokens_authorization_consumed",
            "authorization_id",
            "consumed_at",
        ),
    )
