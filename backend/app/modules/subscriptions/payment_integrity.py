from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache.events import flush_cache_invalidation_events
from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.subscriptions.models import (
    PaymentTransaction,
    PaymentWebhookEvent,
    TenantSubscription,
)
from app.modules.subscriptions.plans import (
    coerce_subscription_plan,
    normalize_plan_code,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import (
    SubscriptionStatusResponse,
    WebhookProcessingResponse,
)
from app.modules.subscriptions.service import (
    SubscriptionFeatureService,
    SubscriptionPaymentService,
    _utc_now,
)
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
)

logger = logging.getLogger(__name__)


def _extract_provider_plan_code(data: dict[str, Any]) -> str | None:
    candidates = (
        data.get("plan"),
        data.get("subscription"),
        data.get("authorization"),
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if not isinstance(candidate, dict):
            continue
        for key in ("plan_code", "code"):
            value = candidate.get(key)
            if value:
                return str(value)
        nested_plan = candidate.get("plan")
        if isinstance(nested_plan, dict):
            value = nested_plan.get("plan_code") or nested_plan.get("code")
            if value:
                return str(value)
        if isinstance(nested_plan, str) and nested_plan.strip():
            return nested_plan.strip()
    return None


def _metadata_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return "" if value is None else str(value)


def _transaction_integrity_failures(
    transaction: PaymentTransaction,
    data: dict[str, Any],
) -> list[str]:
    metadata = SubscriptionPaymentService._extract_metadata(data)
    expected_plan = normalize_plan_code(transaction.plan_code)
    expected_interval = BillingInterval(transaction.billing_interval).value
    expected_provider_plan = SubscriptionPaymentService._get_paystack_plan_code(
        coerce_subscription_plan(transaction.plan_code),
        BillingInterval(transaction.billing_interval),
    )

    failures: list[str] = []
    if str(data.get("reference") or "") != transaction.reference:
        failures.append("reference")

    try:
        provider_amount = int(data.get("amount"))
    except (TypeError, ValueError):
        provider_amount = -1
    if provider_amount != int(transaction.amount_kobo):
        failures.append("amount")

    if str(data.get("currency") or "").upper() != str(transaction.currency).upper():
        failures.append("currency")

    if _metadata_value(metadata, "tenant_id") != str(transaction.tenant_id):
        failures.append("tenant_id")
    if _metadata_value(metadata, "plan_code").lower() != expected_plan:
        failures.append("plan_code")
    if _metadata_value(metadata, "billing_interval").lower() != expected_interval:
        failures.append("billing_interval")
    if _metadata_value(metadata, "transaction_id") != str(transaction.id):
        failures.append("transaction_id")

    provider_plan = _extract_provider_plan_code(data)
    if provider_plan != expected_provider_plan:
        failures.append("provider_plan")

    return failures


def _recurring_integrity_failures(
    subscription: TenantSubscription,
    data: dict[str, Any],
) -> list[str]:
    plan = coerce_subscription_plan(subscription.plan_code)
    interval = BillingInterval(subscription.billing_interval)
    expected_amount = SubscriptionPaymentService._get_amount_kobo(plan, interval)
    expected_provider_plan = SubscriptionPaymentService._get_paystack_plan_code(
        plan, interval
    )
    metadata = SubscriptionPaymentService._extract_metadata(data)

    failures: list[str] = []
    try:
        provider_amount = int(data.get("amount"))
    except (TypeError, ValueError):
        provider_amount = -1
    if provider_amount != expected_amount:
        failures.append("amount")
    if str(data.get("currency") or "").upper() != "NGN":
        failures.append("currency")
    if _extract_provider_plan_code(data) != expected_provider_plan:
        failures.append("provider_plan")

    optional_metadata = {
        "tenant_id": str(subscription.tenant_id),
        "plan_code": normalize_plan_code(subscription.plan_code),
        "billing_interval": interval.value,
    }
    for key, expected in optional_metadata.items():
        if (
            key in metadata
            and _metadata_value(metadata, key).lower() != expected.lower()
        ):
            failures.append(key)
    return failures


async def _get_transaction_for_update(
    db: AsyncSession,
    reference: str,
) -> PaymentTransaction | None:
    result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.reference == reference)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def _record_transaction_integrity_failure(
    db: AsyncSession,
    transaction: PaymentTransaction,
    payload: dict[str, Any],
    failures: list[str],
) -> None:
    reason = "Payment integrity mismatch: " + ", ".join(sorted(set(failures)))
    logger.warning(
        "Rejected Paystack payment integrity mismatch",
        extra={
            "transaction_id": str(transaction.id),
            "tenant_id": str(transaction.tenant_id),
            "reference": transaction.reference,
            "mismatches": sorted(set(failures)),
        },
    )
    data = SubscriptionPaymentService._extract_data(payload)
    await SubscriptionRepository.mark_transaction_failed(
        db=db,
        transaction=transaction,
        status=PaymentStatus.FAILED,
        failure_reason=reason,
        raw_payload={
            "integrity_mismatches": sorted(set(failures)),
            "provider_transaction_id": data.get("id"),
        },
        provider_transaction_id=(
            str(data.get("id")) if data.get("id") is not None else None
        ),
    )


async def verify_subscription_checkout_secure(
    db: AsyncSession,
    *,
    reference: str,
) -> SubscriptionStatusResponse:
    transaction = await _get_transaction_for_update(db, reference)
    if transaction is None:
        raise NotFoundException("Payment transaction not found.")

    if transaction.status == PaymentStatus.SUCCESS:
        return await SubscriptionFeatureService.get_subscription_status(
            db=db,
            tenant_id=transaction.tenant_id,
            use_cache=False,
        )

    provider_response = await SubscriptionPaymentService.provider.verify_transaction(
        reference=reference,
    )
    data = SubscriptionPaymentService._extract_data(provider_response)
    payment_status = str(data.get("status") or "").lower()

    if payment_status != "success":
        mapped_status = (
            PaymentStatus.ABANDONED
            if payment_status in {"abandoned", "cancelled"}
            else PaymentStatus.FAILED
        )
        await SubscriptionRepository.mark_transaction_failed(
            db=db,
            transaction=transaction,
            status=mapped_status,
            failure_reason=str(
                data.get("gateway_response") or "Payment not successful"
            ),
            raw_payload=provider_response,
            provider_transaction_id=(
                str(data.get("id")) if data.get("id") is not None else None
            ),
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        raise BadRequestException("Payment has not been completed successfully.")

    failures = _transaction_integrity_failures(transaction, data)
    if failures:
        await _record_transaction_integrity_failure(
            db,
            transaction,
            provider_response,
            failures,
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        raise BadRequestException(
            "Payment verification failed because the paid amount or checkout details did not match."
        )

    await SubscriptionPaymentService.handle_charge_success(
        db=db,
        payload=provider_response,
        transaction=transaction,
    )
    await db.commit()
    await flush_cache_invalidation_events(db)
    return await SubscriptionFeatureService.get_subscription_status(
        db=db,
        tenant_id=transaction.tenant_id,
        use_cache=False,
    )


async def _resolve_recurring_subscription(
    db: AsyncSession,
    data: dict[str, Any],
) -> TenantSubscription | None:
    subscription_code = SubscriptionPaymentService._extract_subscription_code(data)
    customer_code = SubscriptionPaymentService._extract_customer_code(data)
    subscription = None
    if subscription_code:
        subscription = await SubscriptionRepository.find_subscription_by_provider_subscription_code(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            provider_subscription_code=subscription_code,
        )
    if subscription is None and customer_code:
        subscription = await SubscriptionRepository.find_current_subscription_by_provider_customer_code(
            db=db,
            provider=PaymentProvider.PAYSTACK,
            provider_customer_code=customer_code,
        )
    return subscription


async def _validate_charge_success(
    db: AsyncSession,
    payload: dict[str, Any],
) -> None:
    data = SubscriptionPaymentService._extract_data(payload)
    reference = str(data.get("reference") or "")
    transaction = (
        await _get_transaction_for_update(db, reference) if reference else None
    )

    if transaction is not None:
        failures = _transaction_integrity_failures(transaction, data)
        if failures:
            await _record_transaction_integrity_failure(
                db,
                transaction,
                payload,
                failures,
            )
            raise BadRequestException(
                "Paystack webhook payment details did not match checkout."
            )
        return

    subscription = await _resolve_recurring_subscription(db, data)
    if subscription is None:
        raise BadRequestException("Unknown Paystack charge.success payment reference.")

    failures = _recurring_integrity_failures(subscription, data)
    if failures:
        logger.warning(
            "Rejected recurring Paystack payment integrity mismatch",
            extra={
                "tenant_id": str(subscription.tenant_id),
                "subscription_id": str(subscription.id),
                "mismatches": sorted(set(failures)),
            },
        )
        raise BadRequestException(
            "Recurring Paystack payment details did not match the plan."
        )


async def process_paystack_webhook_secure(
    db: AsyncSession,
    *,
    body: bytes,
    signature: str | None,
) -> WebhookProcessingResponse:
    provider = SubscriptionPaymentService.provider
    if not provider.verify_webhook_signature(body=body, signature=signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paystack webhook signature.",
        )

    payload = provider.parse_webhook_body(body)
    event_type = str(payload.get("event") or "unknown")
    event_key = SubscriptionPaymentService._extract_event_key(event_type, payload)
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

    try:
        if event_type == "charge.success":
            await _validate_charge_success(db, payload)
        await SubscriptionPaymentService.dispatch_paystack_event(db=db, payload=payload)
        await SubscriptionRepository.mark_webhook_processed(
            db=db,
            webhook_event=webhook_event,
            processed_at=_utc_now(),
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        return WebhookProcessingResponse(
            success=True,
            provider=PaymentProvider.PAYSTACK,
            event_type=event_type,
            event_key=event_key,
            duplicate=False,
            message="Webhook event processed successfully.",
        )
    except Exception as exc:
        await SubscriptionRepository.mark_webhook_failed(
            db=db,
            webhook_event=webhook_event,
            error_message=str(exc),
        )
        await db.commit()
        await flush_cache_invalidation_events(db)
        raise
