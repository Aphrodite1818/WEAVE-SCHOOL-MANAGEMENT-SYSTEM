from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.payments.service import PaymentEngine, PaymentVerificationError
from app.modules.payments.webhook import PaymentWebhookSettlementResult
from app.modules.subscriptions.cache import invalidate_tenant_subscription_cache
from app.modules.subscriptions.models import PaymentTransaction, TermPlanEntitlement
from app.modules.subscriptions.subscription_enums import PaymentStatus
from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService

RECONCILIATION_REQUIRED_KEY = "reconciliation_required"
RECONCILIATION_REASON_KEY = "reconciliation_reason"
LATE_PAYMENT_RECONCILIATION_REASON = (
    "Payment was received after the checkout expired and requires manual reconciliation."
)


def payment_requires_reconciliation(transaction: PaymentTransaction) -> bool:
    return transaction.reconciliation_required


def _validate_verified_payment(
    transaction: PaymentTransaction,
    provider_data: dict,
) -> dict:
    try:
        verified = PaymentEngine.validate_successful_payload(
            provider_data,
            expected_reference=transaction.reference,
            expected_amount_kobo=transaction.amount_kobo,
            expected_currency=transaction.currency,
        )
    except PaymentVerificationError as exc:
        raise ConflictException(
            "Paystack verification did not match the expected term payment."
        ) from exc

    metadata = verified.metadata
    if (
        str(metadata.get("tenant_id")) != str(transaction.tenant_id)
        or str(metadata.get("academic_term_id")) != str(transaction.academic_term_id)
        or str(metadata.get("plan_code")) != transaction.plan_code.value
    ):
        raise ConflictException(
            "Paystack term payment metadata did not match the expected purchase."
        )
    return verified.raw_payload


async def settle_verified_term_payment(
    db: AsyncSession,
    transaction: PaymentTransaction,
    provider_data: dict,
    *,
    commit: bool = True,
) -> TermPlanEntitlement | None:
    """Settle a verified Paystack term payment.

    Normal pending checkouts delegate to the entitlement service. A payment that
    arrives after its checkout was marked abandoned is financial truth but no
    longer safe to apply automatically: the admin may already have created a
    replacement checkout or changed the term plan. Such payments are recorded as
    successful, quarantined from term credit, and surfaced for reconciliation.
    """

    if payment_requires_reconciliation(transaction):
        return None

    validated_data = _validate_verified_payment(transaction, provider_data)

    if transaction.status != PaymentStatus.ABANDONED:
        return await TermPlanEntitlementService.activate_verified_transaction(
            db,
            transaction,
            provider_data,
            commit=commit,
        )

    if transaction.academic_term_id is None:
        raise ConflictException("Payment is not attached to an academic term.")

    already_activated = await TermPlanEntitlementService._get_entitlement_for_transaction(
        db,
        transaction.id,
        lock=True,
    )
    if already_activated is not None:
        return already_activated

    now = datetime.now(timezone.utc)
    quote_snapshot = dict((transaction.raw_payload or {}).get("quote") or {})
    transaction.status = PaymentStatus.SUCCESS
    transaction.paid_at = now
    transaction.provider_transaction_id = (
        str(validated_data.get("id"))
        if validated_data.get("id") is not None
        else transaction.provider_transaction_id
    )
    transaction.failure_reason = LATE_PAYMENT_RECONCILIATION_REASON
    transaction.raw_payload = {
        **validated_data,
        "weave_quote": quote_snapshot,
        RECONCILIATION_REQUIRED_KEY: True,
        RECONCILIATION_REASON_KEY: LATE_PAYMENT_RECONCILIATION_REASON,
        "reconciliation_detected_at": now.isoformat(),
    }

    replacement = await TermPlanEntitlementService._get_pending_checkout(
        db,
        transaction.tenant_id,
        transaction.academic_term_id,
        lock=True,
    )
    if replacement is not None and replacement.id != transaction.id:
        replacement.status = PaymentStatus.ABANDONED
        replacement.failure_reason = (
            "Checkout invalidated because an older expired checkout was paid late "
            "and now requires reconciliation. Do not complete this checkout."
        )
        replacement.raw_payload = {
            **(replacement.raw_payload or {}),
            "superseded_by_reconciliation_reference": transaction.reference,
        }

    await db.flush()
    if commit:
        await db.commit()
        await invalidate_tenant_subscription_cache(transaction.tenant_id)
    return None


async def settle_term_payment_webhook(
    db: AsyncSession,
    payload: dict,
) -> PaymentWebhookSettlementResult:
    """Resolve and settle a term-payment webhook without owning provider mechanics."""

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    reference = str(data.get("reference") or "").strip()
    transaction = (
        await db.execute(
            select(PaymentTransaction)
            .where(PaymentTransaction.reference == reference)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if transaction is None or transaction.academic_term_id is None:
        raise BadRequestException("Unknown term payment reference.")

    entitlement = await settle_verified_term_payment(
        db,
        transaction,
        payload,
        commit=False,
    )

    async def post_commit() -> None:
        await invalidate_tenant_subscription_cache(transaction.tenant_id)

    return PaymentWebhookSettlementResult(
        message=(
            "Late term payment recorded for manual reconciliation."
            if entitlement is None
            else "Term payment webhook processed successfully."
        ),
        post_commit=post_commit,
    )
