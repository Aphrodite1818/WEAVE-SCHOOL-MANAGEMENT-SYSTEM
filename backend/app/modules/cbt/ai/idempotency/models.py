"""Durable metadata for idempotent CBT AI authoring operations."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


AI_IDEMPOTENCY_KEY_MAX_LENGTH = 128
AI_IDEMPOTENCY_OPERATION_MAX_LENGTH = 32
AI_IDEMPOTENCY_STATUS_MAX_LENGTH = 32

AI_IDEMPOTENCY_IN_PROGRESS = "in_progress"
AI_IDEMPOTENCY_SUCCEEDED = "succeeded"
AI_IDEMPOTENCY_FAILED = "failed"


class AIIdempotencyRecord(BaseModel):
    """Durable once-only identity for one actor's AI authoring operation.

    Large generated responses intentionally do not live in PostgreSQL. Redis
    holds the short-lived replay body while this row protects accounting from
    duplicate execution after the replay body expires or disappears.
    """

    __tablename__ = "cbt_ai_idempotency_records"

    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(
        String(AI_IDEMPOTENCY_OPERATION_MAX_LENGTH), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(AI_IDEMPOTENCY_KEY_MAX_LENGTH), nullable=False
    )
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(AI_IDEMPOTENCY_STATUS_MAX_LENGTH),
        nullable=False,
        default=AI_IDEMPOTENCY_IN_PROGRESS,
        server_default=AI_IDEMPOTENCY_IN_PROGRESS,
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.cbt_ai_credit_reservations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    credits_charged: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    credits_released: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replay_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "actor_type",
            "actor_id",
            "operation",
            "idempotency_key",
            name="uq_cbt_ai_idempotency_actor_operation_key",
        ),
        Index(
            "ix_cbt_ai_idempotency_tenant_status",
            "tenant_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_cbt_ai_idempotency_reservation",
            "reservation_id",
        ),
    )
