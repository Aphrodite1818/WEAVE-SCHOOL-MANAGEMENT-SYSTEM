from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import (
    BillingInterval,
    PaymentProvider,
    SubscriptionStatus,
)
from app.tenant_management.models import SubscriptionPlan


@pytest.mark.asyncio
@pytest.mark.parametrize("term_status", ["open", "closing"])
async def test_current_term_entitlement_takes_precedence_over_free_fallback(
    term_status: str,
) -> None:
    tenant_id = uuid4()
    term_id = uuid4()
    session_id = uuid4()
    entitlement = SimpleNamespace(
        id=uuid4(),
        plan_code=SubscriptionPlan.PROFESSIONAL,
        provider=PaymentProvider.PAYSTACK,
        safety_expires_at=datetime.now(timezone.utc) + timedelta(days=100),
    )
    current_term = SimpleNamespace(
        id=term_id,
        academic_session_id=session_id,
        status=term_status,
        is_current=True,
    )

    with (
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.list_terms",
            new=AsyncMock(return_value=([current_term], 1)),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.TermPlanEntitlementService.get_active",
            new=AsyncMock(return_value=entitlement),
        ),
    ):
        state = await SubscriptionFeatureService._resolve_subscription_state(
            MagicMock(), tenant_id
        )

    assert state.plan_code == SubscriptionPlan.PROFESSIONAL.value
    assert state.status == SubscriptionStatus.ACTIVE
    assert state.billing_interval == BillingInterval.TERM
    assert state.provider == PaymentProvider.PAYSTACK
    assert state.academic_session_id == session_id


@pytest.mark.asyncio
async def test_no_current_term_resolves_to_permanent_free() -> None:
    tenant_id = uuid4()
    tenant = SimpleNamespace(id=tenant_id, plan=SubscriptionPlan.FREE_TRIAL)

    with (
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.list_terms",
            new=AsyncMock(return_value=([], 0)),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(),
        ) as get_legacy_subscription,
    ):
        state = await SubscriptionFeatureService._resolve_subscription_state(
            MagicMock(), tenant_id
        )

    assert state.plan_code == SubscriptionPlan.FREE.value
    assert state.status == SubscriptionStatus.ACTIVE
    assert state.billing_interval == BillingInterval.TERM
    assert state.provider == PaymentProvider.MANUAL
    assert state.trial_ends_at is None
    assert state.subscription is None
    get_legacy_subscription.assert_not_awaited()


@pytest.mark.asyncio
async def test_open_term_without_entitlement_falls_back_to_free() -> None:
    tenant_id = uuid4()
    term_id = uuid4()
    session_id = uuid4()
    current_term = SimpleNamespace(
        id=term_id,
        academic_session_id=session_id,
        status="open",
        is_current=True,
    )

    with (
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.list_terms",
            new=AsyncMock(return_value=([current_term], 1)),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.TermPlanEntitlementService.get_active",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_tenant",
            new=AsyncMock(return_value=SimpleNamespace(id=tenant_id)),
        ),
    ):
        state = await SubscriptionFeatureService._resolve_subscription_state(
            MagicMock(), tenant_id
        )

    assert state.plan_code == SubscriptionPlan.FREE.value
    assert state.status == SubscriptionStatus.ACTIVE
    assert state.provider == PaymentProvider.MANUAL
    assert state.academic_session_id == session_id
