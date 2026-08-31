from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import (
    AcademicSessionStatus,
    AcademicTermName,
    AcademicTermStatus,
)
from app.modules.subscriptions.models import PaymentTransaction
from app.modules.subscriptions.plans import (
    coerce_subscription_plan,
    get_plan_entitlements,
)
from app.modules.subscriptions.schemas import TermPlanBlocker
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    PaymentStatus,
    ResourceLimitCode,
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


def _term(
    *,
    status: AcademicTermStatus = AcademicTermStatus.DRAFT,
    name: AcademicTermName = AcademicTermName.FIRST_TERM,
    is_current: bool = False,
):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        academic_session_id=uuid4(),
        status=status,
        name=name,
        is_current=is_current,
    )


def _active_entitlement(plan: SubscriptionPlan):
    return SimpleNamespace(
        id=uuid4(),
        plan_code=plan,
        status=TermEntitlementStatus.ACTIVE,
        closed_at=None,
        closed_reason=None,
        safety_expires_at=None,
    )


def _price(plan: SubscriptionPlan) -> int:
    return {
        SubscriptionPlan.FREE: 0,
        SubscriptionPlan.PLUS: 4_000_000,
        SubscriptionPlan.PROFESSIONAL: 7_500_000,
        SubscriptionPlan.ENTERPRISE: 11_900_000,
    }[coerce_subscription_plan(plan)]


def _paid_transaction(
    *,
    plan: SubscriptionPlan = SubscriptionPlan.PROFESSIONAL,
    tenant_id=None,
    term_id=None,
    amount_kobo: int | None = None,
) -> PaymentTransaction:
    amount_kobo = amount_kobo if amount_kobo is not None else _price(plan)
    return PaymentTransaction(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        academic_term_id=term_id or uuid4(),
        provider=PaymentProvider.PAYSTACK,
        status=PaymentStatus.PENDING,
        reference=f"term-{uuid4().hex}",
        plan_code=plan,
        billing_interval=BillingInterval.TERM,
        amount=Decimal(amount_kobo) / 100,
        amount_kobo=amount_kobo,
        currency="NGN",
    )


def _payment_metadata(transaction: PaymentTransaction) -> dict[str, str]:
    return {
        "tenant_id": str(transaction.tenant_id),
        "academic_term_id": str(transaction.academic_term_id),
        "plan_code": transaction.plan_code.value,
    }


def _successful_payment_payload(
    transaction: PaymentTransaction,
    *,
    metadata: dict[str, str] | None = None,
) -> dict:
    return {
        "data": {
            "id": 992211,
            "status": "success",
            "amount": transaction.amount_kobo,
            "currency": transaction.currency,
            "metadata": metadata or _payment_metadata(transaction),
        }
    }


def test_legacy_free_trial_normalizes_to_permanent_free() -> None:
    assert coerce_subscription_plan(SubscriptionPlan.FREE_TRIAL) == SubscriptionPlan.FREE
    assert get_plan_entitlements(SubscriptionPlan.FREE_TRIAL) == get_plan_entitlements(
        SubscriptionPlan.FREE
    )
    assert TermPlanEntitlementService.amount_kobo(SubscriptionPlan.FREE) == 0


def test_registration_without_preference_preserves_no_plan_intent() -> None:
    payload = TenantRegisterRequest(
        school_name="Example School",
        email="admin@example.com",
        password="valid-password",
    )
    assert payload.initial_plan_intent is None


@pytest.mark.asyncio
async def test_missing_entitlement_blocks_open_with_plan_selection_context() -> None:
    tenant_id = uuid4()
    term = _term()
    tenant = SimpleNamespace(initial_plan_intent=SubscriptionPlan.PROFESSIONAL)

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.ensure_open_eligible(
                MagicMock(), tenant_id, term.id
            )

    assert exc_info.value.payload["code"] == "TERM_PLAN_SELECTION_REQUIRED"
    assert exc_info.value.payload["suggested_plan"] == "professional"
    assert exc_info.value.payload["payment_required"] is True
    assert exc_info.value.payload["amount_kobo"] == _price(
        SubscriptionPlan.PROFESSIONAL
    )


@pytest.mark.asyncio
async def test_missing_preference_defaults_open_prompt_to_free() -> None:
    tenant_id = uuid4()
    term = _term()

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=SimpleNamespace(initial_plan_intent=None)),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.ensure_open_eligible(
                MagicMock(), tenant_id, term.id
            )

    assert exc_info.value.payload["code"] == "TERM_PLAN_SELECTION_REQUIRED"
    assert exc_info.value.payload["suggested_plan"] == "free"
    assert exc_info.value.payload["payment_required"] is False
    assert exc_info.value.payload["amount_kobo"] == 0


@pytest.mark.asyncio
async def test_draft_plan_selection_is_blocked_for_future_term() -> None:
    tenant_id = uuid4()
    term = _term(name=AcademicTermName.SECOND_TERM)
    session = SimpleNamespace(
        id=term.academic_session_id,
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    earlier_term = _term(
        status=AcademicTermStatus.OPEN,
        name=AcademicTermName.FIRST_TERM,
        is_current=True,
    )
    earlier_term.academic_session_id = term.academic_session_id

    result = MagicMock()
    result.scalars.return_value.all.return_value = [earlier_term, term]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    with patch.object(
        TermPlanEntitlementService,
        "_session",
        new=AsyncMock(return_value=session),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService._ensure_draft_selection_allowed(
                db, tenant_id, term
            )

    assert exc_info.value.payload["code"] == "TERM_PLAN_SELECTION_NOT_READY"


@pytest.mark.asyncio
async def test_plan_options_quote_only_the_upgrade_difference() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PLUS)
    paid_to_date = _price(SubscriptionPlan.PLUS)

    async def usage_and_blockers(*_args, **_kwargs):
        return {}, []

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=paid_to_date)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", side_effect=usage_and_blockers),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
    ):
        options = await TermPlanEntitlementService.get_plan_options(
            MagicMock(), tenant_id, term.id
        )

    by_plan = {option.plan_code: option for option in options.options}
    professional = by_plan[SubscriptionPlan.PROFESSIONAL]
    enterprise = by_plan[SubscriptionPlan.ENTERPRISE]
    free = by_plan[SubscriptionPlan.FREE]

    assert professional.transition == "upgrade"
    assert professional.amount_due_kobo == (
        _price(SubscriptionPlan.PROFESSIONAL) - paid_to_date
    )
    assert professional.requires_payment is True
    assert enterprise.amount_due_kobo == (
        _price(SubscriptionPlan.ENTERPRISE) - paid_to_date
    )
    assert free.transition == "downgrade"
    assert free.amount_due_kobo == 0
    assert free.requires_payment is False


@pytest.mark.asyncio
async def test_plan_options_expose_downgrade_blockers() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PROFESSIONAL)
    blocker = TermPlanBlocker(
        resource=ResourceLimitCode.STUDENTS,
        used=80,
        limit=50,
        over_by=30,
    )

    async def usage_and_blockers(_db, _tenant_id, _term, plan):
        if coerce_subscription_plan(plan) == SubscriptionPlan.FREE:
            return {}, [blocker]
        return {}, []

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=_price(SubscriptionPlan.PROFESSIONAL))),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", side_effect=usage_and_blockers),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
    ):
        options = await TermPlanEntitlementService.get_plan_options(
            MagicMock(), tenant_id, term.id
        )

    free = next(
        option for option in options.options if option.plan_code == SubscriptionPlan.FREE
    )
    assert free.transition == "downgrade"
    assert free.eligible is False
    assert free.amount_due_kobo == 0
    assert free.blockers[0].over_by == 30


@pytest.mark.asyncio
async def test_free_activation_is_draft_only_and_never_calls_paystack() -> None:
    tenant_id, admin_id = uuid4(), uuid4()
    term = _term()
    tenant = SimpleNamespace(
        initial_plan_intent=SubscriptionPlan.PLUS,
        plan=SubscriptionPlan.FREE,
        trial_ends_at=None,
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_ensure_draft_selection_allowed", new=AsyncMock()),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, []))),
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
            db, tenant_id, term.id, admin_id
        )

    assert entitlement.plan_code == SubscriptionPlan.FREE
    assert entitlement.amount == Decimal("0")
    assert tenant.plan == SubscriptionPlan.FREE
    assert tenant.initial_plan_intent is None
    paystack.assert_not_awaited()


@pytest.mark.asyncio
async def test_free_activation_rejects_open_term() -> None:
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    with patch.object(
        TermPlanEntitlementService,
        "_term",
        new=AsyncMock(return_value=term),
    ):
        with pytest.raises(ConflictException, match="still a draft"):
            await TermPlanEntitlementService.activate_free(
                MagicMock(), uuid4(), term.id, uuid4()
            )


@pytest.mark.asyncio
async def test_checkout_initializes_paystack_with_delta_amount() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PLUS)
    paid_to_date = _price(SubscriptionPlan.PLUS)
    expected_due = _price(SubscriptionPlan.PROFESSIONAL) - paid_to_date
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_ensure_draft_selection_allowed", new=AsyncMock()),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, []))),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=paid_to_date)),
        patch.object(TermPlanEntitlementService, "_get_pending_checkout", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
        patch(
            "app.modules.subscriptions.term_entitlement_service.PaystackClient.initialize_transaction",
            new=AsyncMock(
                return_value={
                    "data": {
                        "authorization_url": "https://paystack.test/checkout",
                        "access_code": "access-code",
                    }
                }
            ),
        ) as initialize,
    ):
        response = await TermPlanEntitlementService.initialize_paid_checkout(
            db,
            tenant_id,
            term.id,
            SubscriptionPlan.PROFESSIONAL,
            "admin@example.com",
        )

    assert response.amount_kobo == expected_due
    assert response.amount == Decimal(expected_due) / 100
    initialize.assert_awaited_once()
    assert initialize.await_args.kwargs["amount_kobo"] == expected_due
    assert initialize.await_args.kwargs["metadata"]["paid_to_date_kobo"] == paid_to_date
    assert initialize.await_args.kwargs["metadata"]["transition"] == "upgrade"


@pytest.mark.asyncio
async def test_checkout_reuses_same_pending_paystack_session() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    pending = _paid_transaction(
        plan=SubscriptionPlan.PROFESSIONAL,
        tenant_id=tenant_id,
        term_id=term.id,
        amount_kobo=_price(SubscriptionPlan.PROFESSIONAL),
    )
    pending.authorization_url = "https://paystack.test/checkout"
    pending.access_code = "access-code"
    pending.created_at = datetime.now(timezone.utc)

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_ensure_draft_selection_allowed", new=AsyncMock()),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, []))),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=0)),
        patch.object(TermPlanEntitlementService, "_get_pending_checkout", new=AsyncMock(return_value=pending)),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
        patch(
            "app.modules.subscriptions.term_entitlement_service.PaystackClient.initialize_transaction",
            new=AsyncMock(),
        ) as initialize,
    ):
        response = await TermPlanEntitlementService.initialize_paid_checkout(
            MagicMock(),
            tenant_id,
            term.id,
            SubscriptionPlan.PROFESSIONAL,
            "admin@example.com",
        )

    assert response.reference == pending.reference
    assert response.authorization_url == pending.authorization_url
    initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_paid_checkout_is_not_used_for_downgrade() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PROFESSIONAL)

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_ensure_draft_selection_allowed", new=AsyncMock()),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.initialize_paid_checkout(
                MagicMock(),
                tenant_id,
                term.id,
                SubscriptionPlan.PLUS,
                "admin@example.com",
            )

    assert exc_info.value.payload["code"] == "NO_PAYMENT_REQUIRED"


@pytest.mark.asyncio
async def test_mid_term_downgrade_is_free_when_usage_fits() -> None:
    tenant_id, admin_id = uuid4(), uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PROFESSIONAL)
    tenant = SimpleNamespace(
        plan=SubscriptionPlan.PROFESSIONAL,
        initial_plan_intent=None,
    )
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_get_pending_checkout", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, []))),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=_price(SubscriptionPlan.PROFESSIONAL))),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
        patch(
            "app.modules.subscriptions.term_entitlement_service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.invalidate_tenant_subscription_cache",
            new=AsyncMock(),
        ),
    ):
        entitlement = await TermPlanEntitlementService.change_plan(
            db,
            tenant_id,
            term.id,
            SubscriptionPlan.PLUS,
            admin_id,
        )

    assert existing.status == TermEntitlementStatus.CLOSED
    assert existing.closed_reason == "mid_term_downgrade"
    assert entitlement.plan_code == SubscriptionPlan.PLUS
    assert entitlement.amount == Decimal("0")
    assert entitlement.provider == PaymentProvider.MANUAL
    assert tenant.plan == SubscriptionPlan.PLUS


@pytest.mark.asyncio
async def test_mid_term_downgrade_is_blocked_when_usage_does_not_fit() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PROFESSIONAL)
    blocker = TermPlanBlocker(
        resource=ResourceLimitCode.STUDENTS,
        used=80,
        limit=50,
        over_by=30,
    )

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_get_pending_checkout", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, [blocker]))),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.change_plan(
                MagicMock(),
                tenant_id,
                term.id,
                SubscriptionPlan.FREE,
                uuid4(),
            )

    assert exc_info.value.payload["code"] == "TARGET_PLAN_INELIGIBLE"
    assert exc_info.value.payload["blockers"][0]["over_by"] == 30


@pytest.mark.asyncio
async def test_zero_cost_change_rejects_upgrade_that_requires_payment() -> None:
    tenant_id = uuid4()
    term = _term(status=AcademicTermStatus.OPEN, is_current=True)
    existing = _active_entitlement(SubscriptionPlan.PLUS)

    with (
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
        patch.object(TermPlanEntitlementService, "_get_pending_checkout", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "get_active", new=AsyncMock(return_value=existing)),
        patch.object(TermPlanEntitlementService, "_usage_and_blockers", new=AsyncMock(return_value=({}, []))),
        patch.object(TermPlanEntitlementService, "_paid_to_date", new=AsyncMock(return_value=_price(SubscriptionPlan.PLUS))),
        patch.object(TermPlanEntitlementService, "amount_kobo", side_effect=_price),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await TermPlanEntitlementService.change_plan(
                MagicMock(),
                tenant_id,
                term.id,
                SubscriptionPlan.PROFESSIONAL,
                uuid4(),
            )

    assert exc_info.value.payload["code"] == "PAYMENT_REQUIRED"
    assert exc_info.value.payload["amount_kobo"] == (
        _price(SubscriptionPlan.PROFESSIONAL) - _price(SubscriptionPlan.PLUS)
    )


@pytest.mark.asyncio
async def test_wrong_amount_cannot_activate_paid_term() -> None:
    transaction = _paid_transaction()
    payload = _successful_payment_payload(transaction)
    payload["data"]["amount"] = transaction.amount_kobo - 1

    with pytest.raises(ConflictException, match="did not match"):
        await TermPlanEntitlementService.activate_verified_transaction(
            MagicMock(), transaction, payload
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata_key", ["tenant_id", "academic_term_id", "plan_code"])
async def test_payment_metadata_must_match_exact_purchase(metadata_key: str) -> None:
    transaction = _paid_transaction()
    metadata = _payment_metadata(transaction)
    metadata[metadata_key] = str(uuid4())

    with pytest.raises(ConflictException, match="metadata did not match"):
        await TermPlanEntitlementService.activate_verified_transaction(
            MagicMock(),
            transaction,
            _successful_payment_payload(transaction, metadata=metadata),
        )


@pytest.mark.asyncio
async def test_duplicate_payment_activation_is_idempotent() -> None:
    transaction = _paid_transaction()
    existing = SimpleNamespace(
        payment_transaction_id=transaction.id,
        status=TermEntitlementStatus.ACTIVE,
    )
    db = MagicMock()

    with patch.object(
        TermPlanEntitlementService,
        "_get_entitlement_for_transaction",
        new=AsyncMock(return_value=existing),
    ):
        result = await TermPlanEntitlementService.activate_verified_transaction(
            db,
            transaction,
            _successful_payment_payload(transaction),
        )

    assert result is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_settlement_rejects_closed_term() -> None:
    transaction = _paid_transaction()
    term = _term(status=AcademicTermStatus.CLOSED)

    with (
        patch.object(TermPlanEntitlementService, "_get_entitlement_for_transaction", new=AsyncMock(return_value=None)),
        patch.object(TermPlanEntitlementService, "_term", new=AsyncMock(return_value=term)),
    ):
        with pytest.raises(ConflictException, match="after the academic term is closed"):
            await TermPlanEntitlementService.activate_verified_transaction(
                MagicMock(),
                transaction,
                _successful_payment_payload(transaction),
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
