from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.events import flush_cache_invalidation_events
from app.modules.payments.enums import PaymentProvider
from app.modules.payments.models import PaymentWebhookEvent
from app.modules.payments.providers.paystack import PaystackClient
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import WebhookProcessingResponse


PostCommitCallback = Callable[[], Awaitable[None]]


@dataclass(slots=True)
class PaymentWebhookSettlementResult:
    message: str
    post_commit: PostCommitCallback | None = None


ChargeSettlementHandler = Callable[
    [AsyncSession, dict[str, Any]],
    Awaitable[PaymentWebhookSettlementResult],
]


def payment_data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data")
    return value if isinstance(value, dict) else payload


def event_key(event_type: str, payload: dict[str, Any]) -> str:
    data = payment_data(payload)
    stable_id = data.get("id") or data.get("reference")
    if stable_id is not None:
        return f"{event_type}:{stable_id}"
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"{event_type}:{digest}"


def webhook_lock_key(event_type: str, key: str) -> int:
    digest = hashlib.sha256(f"{event_type}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def acquire_webhook_lock(
    db: AsyncSession,
    *,
    event_type: str,
    key: str,
) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": webhook_lock_key(event_type, key)},
    )


async def process_paystack_webhook_secure(
    db: AsyncSession,
    *,
    body: bytes,
    signature: str | None,
    settle_charge: ChargeSettlementHandler,
) -> WebhookProcessingResponse:
    """Verify, deduplicate, lock, and dispatch one Paystack webhook event."""

    provider = PaystackClient()
    if not provider.verify_webhook_signature(body=body, signature=signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paystack webhook signature.",
        )

    payload = provider.parse_webhook_body(body)
    event_type = str(payload.get("event") or "unknown")
    key = event_key(event_type, payload)
    await acquire_webhook_lock(db, event_type=event_type, key=key)

    webhook_event = await PaymentRepository.get_webhook_event_by_provider(
        db,
        provider=PaymentProvider.PAYSTACK,
        event_type=event_type,
        event_key=key,
    )
    if webhook_event is not None and webhook_event.processed_at is not None:
        return WebhookProcessingResponse(
            success=True,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=key,
            duplicate=True,
            message="Webhook event already processed.",
        )

    if webhook_event is None:
        webhook_event = await PaymentRepository.create_webhook_event(
            db,
            PaymentWebhookEvent(
                provider=PaymentProvider.PAYSTACK,
                event_type=event_type,
                event_key=key,
                payload=payload,
            ),
        )
    else:
        webhook_event.payload = payload

    settlement: PaymentWebhookSettlementResult | None = None
    try:
        if event_type == "charge.success":
            settlement = await settle_charge(db, payload)

        await PaymentRepository.mark_webhook_processed(
            db,
            webhook_event=webhook_event,
            processed_at=datetime.now(timezone.utc),
        )
        await db.commit()

        if settlement is not None and settlement.post_commit is not None:
            await settlement.post_commit()
        await flush_cache_invalidation_events(db)

        return WebhookProcessingResponse(
            success=True,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=key,
            duplicate=False,
            message=(
                settlement.message
                if settlement is not None
                else "Webhook event recorded; no payment settlement action was required."
            ),
        )
    except Exception as exc:
        await db.rollback()
        failed_event = await PaymentRepository.get_webhook_event_by_provider(
            db,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=key,
        )
        if failed_event is None:
            failed_event = await PaymentRepository.create_webhook_event(
                db,
                PaymentWebhookEvent(
                    provider=PaymentProvider.PAYSTACK,
                    event_type=event_type,
                    event_key=key,
                    payload=payload,
                ),
            )
        await PaymentRepository.mark_webhook_failed(
            db,
            webhook_event=failed_event,
            error_message=str(exc),
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        raise
