from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException
from app.modules.subscriptions.cache import invalidate_tenant_subscription_cache
from app.modules.subscriptions.models import PaymentTransaction, PaymentWebhookEvent
from app.modules.subscriptions.payment_settlement import settle_verified_term_payment
from app.modules.subscriptions.providers.paystack import PaystackClient
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import WebhookProcessingResponse
from app.modules.subscriptions.subscription_enums import PaymentProvider


def _data(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("data")
    return value if isinstance(value, dict) else payload


def _event_key(event_type: str, payload: dict[str, Any]) -> str:
    data = _data(payload)
    stable_id = data.get("id") or data.get("reference")
    if stable_id is not None:
        return f"{event_type}:{stable_id}"
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return f"{event_type}:{digest}"


def _webhook_lock_key(event_type: str, event_key: str) -> int:
    digest = hashlib.sha256(f"{event_type}:{event_key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


async def _acquire_webhook_lock(db: AsyncSession, *, event_type: str, event_key: str) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _webhook_lock_key(event_type, event_key)},
    )


async def _transaction_for_update(db: AsyncSession, reference: str) -> PaymentTransaction | None:
    return (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.reference == reference)
            .with_for_update()
        )
    ).scalar_one_or_none()


async def process_paystack_webhook_secure(
    db: AsyncSession, *, body: bytes, signature: str | None
) -> WebhookProcessingResponse:
    provider = PaystackClient()
    if not provider.verify_webhook_signature(body=body, signature=signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paystack webhook signature.",
        )

    payload = provider.parse_webhook_body(body)
    event_type = str(payload.get("event") or "unknown")
    event_key = _event_key(event_type, payload)
    await _acquire_webhook_lock(db, event_type=event_type, event_key=event_key)
    webhook_event = await SubscriptionRepository.get_webhook_event_by_provider(
        db=db,
        provider=PaymentProvider.PAYSTACK,
        event_type=event_type,
        event_key=event_key,
    )
    if webhook_event is not None and webhook_event.processed_at is not None:
        return WebhookProcessingResponse(
            success=True,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=event_key,
            duplicate=True,
            message="Webhook event already processed.",
        )

    if webhook_event is None:
        webhook_event = await SubscriptionRepository.create_webhook_event(
            db=db,
            webhook_event=PaymentWebhookEvent(
                provider=PaymentProvider.PAYSTACK,
                event_type=event_type,
                event_key=event_key,
                payload=payload,
            ),
        )
    else:
        webhook_event.payload = payload

    transaction: PaymentTransaction | None = None
    reconciliation_required = False
    try:
        if event_type == "charge.success":
            payment_data = _data(payload)
            reference = str(payment_data.get("reference") or "")
            transaction = await _transaction_for_update(db, reference) if reference else None
            if transaction is None or transaction.academic_term_id is None:
                raise BadRequestException("Unknown term payment reference.")
            entitlement = await settle_verified_term_payment(
                db,
                transaction,
                payload,
                commit=False,
            )
            reconciliation_required = entitlement is None

        await SubscriptionRepository.mark_webhook_processed(
            db=db,
            webhook_event=webhook_event,
            processed_at=datetime.now(timezone.utc),
        )
        await db.commit()
        if transaction is not None:
            await invalidate_tenant_subscription_cache(transaction.tenant_id)
        await flush_cache_invalidation_events(db)
        return WebhookProcessingResponse(
            success=True,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=event_key,
            duplicate=False,
            message=(
                "Late term payment recorded for manual reconciliation."
                if reconciliation_required
                else "Term payment webhook processed successfully."
                if transaction is not None
                else "Webhook event recorded; no recurring subscription action was required."
            ),
        )
    except Exception as exc:
        await db.rollback()
        failed_event = await SubscriptionRepository.get_webhook_event_by_provider(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=event_key,
        )
        if failed_event is None:
            failed_event = await SubscriptionRepository.create_webhook_event(
                db=db,
                webhook_event=PaymentWebhookEvent(
                    provider=PaymentProvider.PAYSTACK,
                    event_type=event_type,
                    event_key=event_key,
                    payload=payload,
                ),
            )
        await SubscriptionRepository.mark_webhook_failed(
            db=db, webhook_event=failed_event, error_message=str(exc)
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        raise
