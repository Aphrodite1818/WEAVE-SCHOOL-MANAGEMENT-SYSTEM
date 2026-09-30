from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.enums import PaymentProvider
from app.modules.payments.models import PaymentWebhookEvent


class PaymentRepository:
    @staticmethod
    async def create_webhook_event(
        db: AsyncSession,
        webhook_event: PaymentWebhookEvent,
    ) -> PaymentWebhookEvent:
        db.add(webhook_event)
        await db.flush()
        return webhook_event

    @staticmethod
    async def get_webhook_event_by_provider(
        db: AsyncSession,
        *,
        provider: PaymentProvider,
        event_type: str,
        event_key: str,
    ) -> PaymentWebhookEvent | None:
        result = await db.execute(
            select(PaymentWebhookEvent).where(
                PaymentWebhookEvent.provider == provider,
                PaymentWebhookEvent.event_type == event_type,
                PaymentWebhookEvent.event_key == event_key,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_webhook_processed(
        db: AsyncSession,
        *,
        webhook_event: PaymentWebhookEvent,
        processed_at: datetime,
    ) -> PaymentWebhookEvent:
        webhook_event.processed_at = processed_at
        webhook_event.error_message = None
        webhook_event.payload = webhook_event.payload or {}
        db.add(webhook_event)
        await db.flush()
        return webhook_event

    @staticmethod
    async def mark_webhook_failed(
        db: AsyncSession,
        *,
        webhook_event: PaymentWebhookEvent,
        error_message: str,
    ) -> PaymentWebhookEvent:
        webhook_event.error_message = error_message
        db.add(webhook_event)
        await db.flush()
        return webhook_event
