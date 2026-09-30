"""Compatibility boundary for subscription payment callers.

Provider verification, webhook signature validation, idempotency, and advisory
locking now live in the shared payments domain. Subscription-specific settlement
remains in the subscription domain.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.dispatcher import settle_paystack_charge
from app.modules.payments.schemas import WebhookProcessingResponse
from app.modules.payments.webhook import (
    process_paystack_webhook_secure as process_shared_paystack_webhook,
)
from app.modules.subscriptions.models import PaymentTransaction


async def _transaction_for_update(
    db: AsyncSession,
    reference: str,
) -> PaymentTransaction | None:
    return (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.reference == reference)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def process_paystack_webhook_secure(
    db: AsyncSession,
    *,
    body: bytes,
    signature: str | None,
) -> WebhookProcessingResponse:
    return await process_shared_paystack_webhook(
        db,
        body=body,
        signature=signature,
        settle_charge=settle_paystack_charge,
    )
