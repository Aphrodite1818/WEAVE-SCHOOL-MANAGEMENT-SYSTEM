"""Database model for persistent per-actor product-guide progress."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class UserGuideState(UUIDMixin, TimestampMixin, Base):
    """Stores presentation state while completion remains domain-data driven."""

    __tablename__ = "user_guide_states"

    __table_args__ = (
        CheckConstraint(
            "status IN ('not_started', 'in_progress', 'dismissed', 'completed')",
            name="ck_user_guide_states_status",
        ),
        UniqueConstraint(
            "actor_type",
            "actor_id",
            "scope_key",
            "guide_key",
            name="uq_user_guide_states_actor_scope_guide",
        ),
        Index(
            "ix_user_guide_states_actor_scope",
            "actor_type",
            "actor_id",
            "scope_key",
        ),
    )

    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{PUBLIC_SCHEMA}.tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scope_key: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="global",
        server_default="global",
    )
    guide_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="not_started",
        server_default="not_started",
    )
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    skipped_steps: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    remind_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
