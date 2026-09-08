from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import ConflictException
from app.modules.subscriptions.models import PaymentTransaction
from app.modules.subscriptions.payment_settlement import (
    LATE_PAYMENT_RECONCILIATION_REASON,
    payment_requires_reconciliation,
    settle_verified_term_payment,
)
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.schemas import PaymentTransactionResponse
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
)
from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService
from app.tenant_management.models import SubscriptionPlan
from app.tenant_management.schemas import TenantCreate


def _transaction(
    *,
    status: PaymentStatus = PaymentStatus.ABANDONED,
    tenant_id=None,
    term_id=None,
    reference: str | None = None,
) -> PaymentTransaction:
    return PaymentTransaction(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        academic_term_id=term_id or uuid4(),
        provider=PaymentProvider.PAYSTACK,
        status=status,
        reference=reference or f"term-{uuid4().hex}",
        plan_code=SubscriptionPlan.PROFESSIONAL,
        billing_interval=BillingInterval.TERM,
        amount=Decimal("75000"),
        amount_kobo=7_500_000,
        currency="NGN",
        raw_payload={
            "quote": {
                "target_plan_price_kobo": 7_500_000,
                "paid_to_date_kobo": 0,
                "amount_due_kobo": 7_500_000,
                "transition": "select",
            }
        },
    )


def _verified_payload(transaction: PaymentTransaction) -> dict:
    return {
        "data": {
            "id": 901122,
            "status": "success",
            "amount": transaction.amount_kobo,
            "currency": transaction.currency,
            "metadata": {
                "tenant_id": str(transaction.tenant_id),
                "academic_term_id": str(transaction.academic_term_id),
                "plan_code": transaction.plan_code.value,
            },
        }
    }


@pytest.mark.asyncio
async def test_late_abandoned_payment_is_recorded_but_does_not_create_entitlement() -> None:
    transaction = _transaction()
    replacement = _transaction(
        status=PaymentStatus.PENDING,
        tenant_id=transaction.tenant_id,
        term_id=transaction.academic_term_id,
    )
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch.object(
            TermPlanEntitlementService,
            "_get_entitlement_for_transaction",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            TermPlanEntitlementService,
            "_get_pending_checkout",
            new=AsyncMock(return_value=replacement),
        ),
        patch(
            "app.modules.subscriptions.payment_settlement.invalidate_tenant_subscription_cache",
            new=AsyncMock(),
        ) as invalidate,
    ):
        entitlement = await settle_verified_term_payment(
            db,
            transaction,
            _verified_payload(transaction),
        )

    assert entitlement is None
    assert transaction.status == PaymentStatus.SUCCESS
    assert transaction.paid_at is not None
    assert transaction.provider_transaction_id == "901122"
    assert transaction.failure_reason == LATE_PAYMENT_RECONCILIATION_REASON
    assert payment_requires_reconciliation(transaction) is True
    assert transaction.reconciliation_required is True
    assert transaction.raw_payload["weave_quote"]["amount_due_kobo"] == 7_500_000
    assert replacement.status == PaymentStatus.ABANDONED
    assert (
        transaction.reference == replacement.raw_payload["superseded_by_reconciliation_reference"]
    )
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    invalidate.assert_awaited_once_with(transaction.tenant_id)


@pytest.mark.asyncio
async def test_reconciliation_payment_is_idempotently_kept_out_of_entitlement_path() -> None:
    transaction = _transaction(status=PaymentStatus.SUCCESS)
    transaction.raw_payload = {"reconciliation_required": True}
    db = MagicMock()

    with patch.object(
        TermPlanEntitlementService,
        "activate_verified_transaction",
        new=AsyncMock(),
    ) as activate:
        entitlement = await settle_verified_term_payment(
            db,
            transaction,
            _verified_payload(transaction),
        )

    assert entitlement is None
    activate.assert_not_awaited()


def test_payment_history_response_exposes_reconciliation_flag() -> None:
    transaction = _transaction(status=PaymentStatus.SUCCESS)
    transaction.raw_payload = {"reconciliation_required": True}
    now = datetime.now(timezone.utc)
    transaction.created_at = now
    transaction.updated_at = now

    response = PaymentTransactionResponse.model_validate(transaction)

    assert response.reconciliation_required is True


@pytest.mark.asyncio
async def test_normal_pending_payment_still_uses_standard_entitlement_settlement() -> None:
    transaction = _transaction(status=PaymentStatus.PENDING)
    expected = MagicMock()

    with patch.object(
        TermPlanEntitlementService,
        "activate_verified_transaction",
        new=AsyncMock(return_value=expected),
    ) as activate:
        result = await settle_verified_term_payment(
            MagicMock(),
            transaction,
            _verified_payload(transaction),
            commit=False,
        )

    assert result is expected
    activate.assert_awaited_once()
    assert activate.await_args.kwargs["commit"] is False


@pytest.mark.asyncio
async def test_late_payment_still_requires_exact_paystack_metadata() -> None:
    transaction = _transaction()
    payload = _verified_payload(transaction)
    payload["data"]["metadata"]["academic_term_id"] = str(uuid4())

    with pytest.raises(ConflictException, match="metadata did not match"):
        await settle_verified_term_payment(MagicMock(), transaction, payload)

    assert transaction.status == PaymentStatus.ABANDONED
    assert payment_requires_reconciliation(transaction) is False


@pytest.mark.asyncio
async def test_term_credit_query_excludes_reconciliation_required_successes() -> None:
    result = MagicMock()
    result.scalar_one.return_value = 4_000_000
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    total = await SubscriptionRepository.sum_successful_term_payments(
        db,
        tenant_id=uuid4(),
        academic_term_id=uuid4(),
    )

    statement = db.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert total == 4_000_000
    assert "reconciliation_required" in sql
    assert "IS NOT true" in sql


def test_internal_tenant_creation_defaults_to_permanent_free() -> None:
    payload = TenantCreate(
        school_name="Example School",
        email="admin@example.com",
    )
    assert payload.plan == SubscriptionPlan.FREE
