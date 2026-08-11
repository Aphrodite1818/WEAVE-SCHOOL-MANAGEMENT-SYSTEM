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
async def test_open_term_entitlement_takes_precedence_over_live_trial() -> None:
    tenant_id = uuid4()
    term_id = uuid4()
    trial = SimpleNamespace(
        plan_code=SubscriptionPlan.FREE_TRIAL,
        status=SubscriptionStatus.TRIALING,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=10),
        billing_interval=BillingInterval.TRIAL,
        provider=PaymentProvider.MANUAL,
    )
    entitlement = SimpleNamespace(
        plan_code=SubscriptionPlan.PROFESSIONAL,
        provider=PaymentProvider.PAYSTACK,
        safety_expires_at=datetime.now(timezone.utc) + timedelta(days=100),
    )

    with (
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_current_term",
            new=AsyncMock(return_value=SimpleNamespace(id=term_id)),
        ),
        patch(
            "app.modules.subscriptions.term_entitlement_service.TermPlanEntitlementService.get_active",
            new=AsyncMock(return_value=entitlement),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=trial),
        ) as get_trial,
    ):
        state = await SubscriptionFeatureService._resolve_subscription_state(
            MagicMock(), tenant_id
        )

    assert state.plan_code == SubscriptionPlan.PROFESSIONAL.value
    assert state.status == SubscriptionStatus.ACTIVE
    assert state.billing_interval == BillingInterval.TERM
    get_trial.assert_not_awaited()


@pytest.mark.asyncio
async def test_trial_remains_effective_until_paid_term_is_open() -> None:
    tenant_id = uuid4()
    trial = SimpleNamespace(
        id=uuid4(),
        plan_code=SubscriptionPlan.FREE_TRIAL,
        status=SubscriptionStatus.TRIALING,
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=10),
        billing_interval=BillingInterval.TRIAL,
        provider=PaymentProvider.MANUAL,
    )

    with (
        patch(
            "app.modules.student_academics.repository.StudentAcademicRepository.get_current_term",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=trial),
        ),
    ):
        state = await SubscriptionFeatureService._resolve_subscription_state(
            MagicMock(), tenant_id
        )

    assert state.plan_code == SubscriptionPlan.FREE_TRIAL.value
    assert state.status == SubscriptionStatus.TRIALING
    assert state.subscription is trial
