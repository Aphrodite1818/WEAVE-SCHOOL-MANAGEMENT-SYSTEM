# =========================== #
#   email_outbox_models.py    #
# =========================== #

"""Email outbox models for safe background email delivery."""

from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum as SQLEnum, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class EmailOutboxStatus(str, PyEnum):
    """Lifecycle state for an email outbox item."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailOutbox(BaseModel):
    """Email queued for safe background delivery."""

    __tablename__ = "email_outbox"

    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    template_name: Mapped[str] = mapped_column(String(120), nullable=False)
    template_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[EmailOutboxStatus] = mapped_column(
        SQLEnum(
            EmailOutboxStatus,
            name="email_outbox_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=EmailOutboxStatus.PENDING,
        server_default=EmailOutboxStatus.PENDING.value,
    )

    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4, server_default="4"
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )

    __table_args__ = (
        Index("ix_email_outbox_tenant_status", "tenant_id", "status"),
        Index("ix_email_outbox_tenant_retry", "tenant_id", "status", "next_retry_at"),
        Index("ix_email_outbox_recipient_status", "recipient_email", "status"),
        Index("ix_email_outbox_template_status", "template_name", "status"),
        Index(
            "ix_email_outbox_pending_claim",
            "next_retry_at",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_email_outbox_processing_recovery",
            "processing_started_at",
            postgresql_where=text("status = 'processing'"),
        ),
    )
