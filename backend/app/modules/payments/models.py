from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.payments.enums import PaymentProvider
from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class PaymentWebhookEvent(UUIDMixin, TimestampMixin, Base):
    """Idempotency and audit record for inbound payment-provider webhooks."""

    __tablename__ = "payment_webhook_events"

    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(
            PaymentProvider,
            name="payment_provider",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_type",
            "event_key",
            name="uq_payment_webhook_events_provider_type_key",
        ),
        Index(
            "ix_payment_webhook_events_provider_type",
            "provider",
            "event_type",
        ),
    )
