from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import AcademicTermStatus
from app.modules.subscriptions.models import PaymentTransaction
from app.modules.subscriptions.plans import get_plan_entitlements
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    TermEntitlementStatus,
)
from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService
from app.tenant_management.models import SubscriptionPlan
from app.tenant_management.schemas import TenantRegisterRequest


@pytest.fixture(autouse=True)
def _isolate_periodic_pending_checkout_cleanup():
    with patch.object(
        TermPlanEntitlementService,
        "expire_stale_pending_checkouts",
        new=AsyncMock(return_value=0),
    ):
        yield


def test_free_is_distinct_from_trial_and_does_not_inherit_paid_features() -> None:
    assert SubscriptionPlan.FREE is not SubscriptionPlan.FREE_TRIAL
    assert (
        get_plan_entitlements(SubscriptionPlan.FREE).features
        != get_plan_entitlements(SubscriptionPlan.PROFESSIONAL).features
    )
    assert TermPlanEntitlementService.amount_kobo(SubscriptionPlan.FREE) == 0


@pytest.mark.asyncio
async def test_missing_entitlement_blocks_term_open_with_frontend_context() -> None:
    tenant_id, term_id = uuid4(), uuid4()
    with (
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(
                return_value=SimpleNamespace(initial_plan_intent=SubscriptionPlan.PROFESSIONAL)
            ),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.ensure_open_eligible(MagicMock(), tenant_id, term_id)
    assert exc_info.value.payload["code"] == "TERM_PLAN_ACTIVATION_REQUIRED"
    assert exc_info.value.payload["suggested_plan"] == "professional"
    assert exc_info.value.payload["payment_required"] is True


@pytest.mark.asyncio
async def test_missing_registration_plan_routes_term_open_to_plan_selection() -> None:
    tenant_id, term_id = uuid4(), uuid4()
    with (
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=SimpleNamespace(initial_plan_intent=None)),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.ensure_open_eligible(MagicMock(), tenant_id, term_id)

    assert exc_info.value.payload["suggested_plan"] is None
    assert exc_info.value.payload["payment_required"] is False


def test_registration_without_plan_preserves_no_plan_intent() -> None:
    payload = TenantRegisterRequest(
        school_name="Example School",
        email="admin@example.com",
        password="valid-password",
    )

    assert payload.initial_plan_intent is None


@pytest.mark.asyncio
async def test_free_activation_never_calls_paystack() -> None:
    tenant_id, term_id, admin_id = uuid4(), uuid4(), uuid4()
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    tenant = SimpleNamespace(
        initial_plan_intent=SubscriptionPlan.PLUS, plan=SubscriptionPlan.FREE_TRIAL
    )
    usage = {resource: 0 for resource in get_plan_entitlements(SubscriptionPlan.FREE).limits}
    with (
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.DRAFT)),
        ),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_all_resource_usage",
            new=AsyncMock(return_value=usage),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.invalidate_tenant_subscription_cache",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.PaystackClient.initialize_transaction",
            new=AsyncMock(),
        ) as paystack,
    ):
        entitlement = await TermPlanEntitlementService.activate_free(
            db, tenant_id, term_id, admin_id
        )
    assert entitlement.plan_code == SubscriptionPlan.FREE
    assert entitlement.amount == 0
    paystack.assert_not_awaited()


@pytest.mark.asyncio
async def test_free_activation_rejects_open_term() -> None:
    with patch.object(
        TermPlanEntitlementService,
        "_term",
        new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.OPEN)),
    ):
        with pytest.raises(ConflictException, match="still a draft"):
            await TermPlanEntitlementService.activate_free(MagicMock(), uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_wrong_amount_cannot_activate_paid_term() -> None:
    transaction = _paid_transaction()
    payload = {
        "data": {
            "status": "success",
            "amount": 1,
            "currency": "NGN",
            "metadata": _payment_metadata(transaction),
        }
    }
    with pytest.raises(ConflictException, match="did not match"):
        await TermPlanEntitlementService.activate_verified_transaction(
            MagicMock(), transaction, payload
        )


@pytest.mark.asyncio
async def test_free_activation_blocks_usage_above_free_limits() -> None:
    tenant_id, term_id, admin_id = uuid4(), uuid4(), uuid4()
    limits = get_plan_entitlements(SubscriptionPlan.FREE).limits
    limited_resource, limit = next(
        (resource, value) for resource, value in limits.items() if value is not None
    )
    usage = {resource: 0 for resource in limits}
    usage[limited_resource] = limit + 1
    with (
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.DRAFT)),
        ),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_all_resource_usage",
            new=AsyncMock(return_value=usage),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.activate_free(
                MagicMock(), tenant_id, term_id, admin_id
            )
    assert exc_info.value.payload["code"] == "FREE_PLAN_LIMITS_EXCEEDED"
    assert exc_info.value.payload["blockers"] == [
        {"resource": limited_resource.value, "used": limit + 1, "limit": limit}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata_key", ["tenant_id", "academic_term_id", "plan_code"])
async def test_payment_metadata_must_match_exact_purchase(metadata_key: str) -> None:
    transaction = _paid_transaction()
    metadata = _payment_metadata(transaction)
    metadata[metadata_key] = str(uuid4())
    payload = _successful_payment_payload(transaction, metadata=metadata)
    with pytest.raises(ConflictException, match="metadata did not match"):
        await TermPlanEntitlementService.activate_verified_transaction(
            MagicMock(), transaction, payload
        )


@pytest.mark.asyncio
async def test_duplicate_payment_activation_is_idempotent_even_after_term_close() -> None:
    transaction = _paid_transaction()
    existing = SimpleNamespace(
        payment_transaction_id=transaction.id,
        status=TermEntitlementStatus.CLOSED,
    )
    db = MagicMock()
    with patch.object(
        TermPlanEntitlementService,
        "_get_entitlement_for_transaction",
        new=AsyncMock(return_value=existing),
    ):
        result = await TermPlanEntitlementService.activate_verified_transaction(
            db, transaction, _successful_payment_payload(transaction)
        )
    assert result is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_paid_activation_rejects_closed_term_at_settlement() -> None:
    transaction = _paid_transaction()
    with (
        patch.object(
            TermPlanEntitlementService,
            "_get_entitlement_for_transaction",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.CLOSED)),
        ),
    ):
        with pytest.raises(ConflictException, match="after the academic term is closed"):
            await TermPlanEntitlementService.activate_verified_transaction(
                MagicMock(), transaction, _successful_payment_payload(transaction)
            )


@pytest.mark.asyncio
async def test_paid_activation_can_finish_checkout_while_term_is_closing() -> None:
    transaction = _paid_transaction()
    tenant = SimpleNamespace(plan=SubscriptionPlan.FREE, initial_plan_intent=None)
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
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.CLOSING)),
        ),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.invalidate_tenant_subscription_cache",
            new=AsyncMock(),
        ),
    ):
        entitlement = await TermPlanEntitlementService.activate_verified_transaction(
            db, transaction, _successful_payment_payload(transaction)
        )
    assert entitlement.status == TermEntitlementStatus.ACTIVE
    assert transaction.status == PaymentStatus.SUCCESS


@pytest.mark.asyncio
async def test_paid_upgrade_closes_free_entitlement_without_opening_term() -> None:
    transaction = _paid_transaction()
    existing = SimpleNamespace(
        payment_transaction_id=None,
        plan_code=SubscriptionPlan.FREE,
        status=TermEntitlementStatus.ACTIVE,
        closed_at=None,
        closed_reason=None,
    )
    tenant = SimpleNamespace(plan=SubscriptionPlan.FREE, initial_plan_intent=None)
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
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.DRAFT)),
        ),
        patch.object(
            TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.invalidate_tenant_subscription_cache",
            new=AsyncMock(),
        ),
    ):
        entitlement = await TermPlanEntitlementService.activate_verified_transaction(
            db, transaction, _successful_payment_payload(transaction)
        )
    assert existing.status == TermEntitlementStatus.CLOSED
    assert existing.closed_reason == "mid_term_upgrade"
    assert entitlement.status == TermEntitlementStatus.ACTIVE
    assert entitlement.plan_code == SubscriptionPlan.PROFESSIONAL
    assert tenant.plan == SubscriptionPlan.PROFESSIONAL
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_mid_term_paid_downgrade_is_rejected() -> None:
    transaction = _paid_transaction(plan=SubscriptionPlan.PLUS)
    active_professional = SimpleNamespace(plan_code=SubscriptionPlan.PROFESSIONAL)
    with (
        patch.object(
            TermPlanEntitlementService,
            "_get_entitlement_for_transaction",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.OPEN)),
        ),
        patch.object(
            TermPlanEntitlementService,
            "get_active",
            new=AsyncMock(return_value=active_professional),
        ),
    ):
        with pytest.raises(ConflictException, match="higher paid plan"):
            await TermPlanEntitlementService.activate_verified_transaction(
                MagicMock(), transaction, _successful_payment_payload(transaction)
            )


@pytest.mark.asyncio
async def test_checkout_reuses_same_pending_paystack_session() -> None:
    tenant_id, term_id = uuid4(), uuid4()
    pending = _paid_transaction(
        plan=SubscriptionPlan.PROFESSIONAL,
        tenant_id=tenant_id,
        term_id=term_id,
    )
    pending.authorization_url = "https://paystack.test/checkout"
    pending.access_code = "access-code"
    pending.created_at = datetime.now(timezone.utc)

    with (
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.DRAFT)),
        ),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch.object(
            TermPlanEntitlementService,
            "_get_pending_checkout",
            new=AsyncMock(return_value=pending),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.PaystackClient.initialize_transaction",
            new=AsyncMock(),
        ) as initialize,
    ):
        response = await TermPlanEntitlementService.initialize_paid_checkout(
            MagicMock(),
            tenant_id,
            term_id,
            SubscriptionPlan.PROFESSIONAL,
            "admin@example.com",
        )

    assert response.reference == pending.reference
    assert response.authorization_url == pending.authorization_url
    initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkout_rejects_switching_plan_while_payment_is_pending() -> None:
    tenant_id, term_id = uuid4(), uuid4()
    pending = _paid_transaction(
        plan=SubscriptionPlan.PLUS,
        tenant_id=tenant_id,
        term_id=term_id,
    )
    pending.authorization_url = "https://paystack.test/checkout"
    pending.access_code = "access-code"
    pending.created_at = datetime.now(timezone.utc)

    with (
        patch.object(
            TermPlanEntitlementService,
            "_term",
            new=AsyncMock(return_value=SimpleNamespace(status=AcademicTermStatus.DRAFT)),
        ),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch.object(
            TermPlanEntitlementService,
            "_get_pending_checkout",
            new=AsyncMock(return_value=pending),
        ),
    ):
        with pytest.raises(ConflictException, match="already in progress"):
            await TermPlanEntitlementService.initialize_paid_checkout(
                MagicMock(),
                tenant_id,
                term_id,
                SubscriptionPlan.PROFESSIONAL,
                "admin@example.com",
            )


@pytest.mark.asyncio
async def test_term_closure_blocks_while_paystack_checkout_is_pending() -> None:
    pending = _paid_transaction()
    with patch.object(
        TermPlanEntitlementService,
        "_get_pending_checkout",
        new=AsyncMock(return_value=pending),
    ):
        with pytest.raises(ConflictException, match="pending Paystack checkout"):
            await TermPlanEntitlementService.close_for_term(
                MagicMock(), pending.tenant_id, pending.academic_term_id
            )


@pytest.mark.asyncio
async def test_reconcile_repairs_closed_term_and_expires_safety_cap() -> None:
    now = datetime.now(timezone.utc)
    closed_term_entitlement = SimpleNamespace(
        tenant_id=uuid4(), status=TermEntitlementStatus.ACTIVE
    )
    safety_expired_entitlement = SimpleNamespace(
        tenant_id=uuid4(), status=TermEntitlementStatus.ACTIVE
    )
    result = MagicMock()
    result.all.return_value = [
        (closed_term_entitlement, AcademicTermStatus.CLOSED),
        (safety_expired_entitlement, AcademicTermStatus.OPEN),
    ]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    with patch(
        "app.modules.subscriptions.term_entitlement_service.invalidate_tenant_subscription_cache",
        new=AsyncMock(),
    ) as invalidate:
        counts = await TermPlanEntitlementService.reconcile(db, as_of=now)
    assert counts == {"closed_term_repaired": 1, "safety_expired": 1}
    assert closed_term_entitlement.status == TermEntitlementStatus.CLOSED
    assert closed_term_entitlement.closed_reason == "reconciled_closed_term"
    assert safety_expired_entitlement.status == TermEntitlementStatus.EXPIRED
    assert safety_expired_entitlement.closed_reason == "safety_cap_reached"
    assert invalidate.await_count == 2


def _paid_transaction(
    *,
    plan: SubscriptionPlan = SubscriptionPlan.PROFESSIONAL,
    tenant_id=None,
    term_id=None,
) -> PaymentTransaction:
    return PaymentTransaction(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        academic_term_id=term_id or uuid4(),
        provider=PaymentProvider.PAYSTACK,
        status=PaymentStatus.PENDING,
        reference=f"term-{uuid4().hex}",
        plan_code=plan,
        billing_interval=BillingInterval.TERM,
        amount=30000,
        amount_kobo=3_000_000,
        currency="NGN",
    )


def _payment_metadata(transaction: PaymentTransaction) -> dict[str, str]:
    return {
        "tenant_id": str(transaction.tenant_id),
        "academic_term_id": str(transaction.academic_term_id),
        "plan_code": transaction.plan_code.value,
    }


def _successful_payment_payload(
    transaction: PaymentTransaction, *, metadata: dict[str, str] | None = None
) -> dict:
    return {
        "data": {
            "status": "success",
            "amount": transaction.amount_kobo,
            "currency": transaction.currency,
            "metadata": metadata or _payment_metadata(transaction),
        }
    }
