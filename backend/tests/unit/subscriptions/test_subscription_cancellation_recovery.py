from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.subscriptions.cancellation_service import (
    SubscriptionCancellationService,
)
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    SubscriptionStatus,
)


@pytest.mark.asyncio
async def test_missing_paystack_token_is_recovered_before_disabling_renewal() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        tenant_id=tenant_id,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        provider=PaymentProvider.PAYSTACK,
        provider_subscription_code="SUB_test",
        provider_email_token=None,
    )
    saved = SimpleNamespace(
        **{
            **subscription.__dict__,
            "status": SubscriptionStatus.NON_RENEWING,
            "cancel_at_period_end": True,
        }
    )
    db = SimpleNamespace(commit=AsyncMock())

    with (
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ),
        patch.object(
            SubscriptionCancellationService,
            "_recover_paystack_credentials",
            new=AsyncMock(
                return_value=("SUB_test", "recovered-token", "active")
            ),
        ) as recover,
        patch(
            "app.modules.subscriptions.cancellation_service.PaystackClient.disable_subscription",
            new=AsyncMock(return_value={"status": True}),
        ) as disable,
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionLifecycleService.mark_non_renewing",
            new=AsyncMock(return_value=saved),
        ) as mark_non_renewing,
        patch(
            "app.modules.subscriptions.cancellation_service.flush_cache_invalidation_events",
            new=AsyncMock(),
        ) as flush_events,
    ):
        result = await SubscriptionCancellationService.request_cancellation(
            db,
            tenant_id=tenant_id,
            notes="School no longer needs automatic renewal",
        )

    assert result is saved
    recover.assert_awaited_once()
    disable.assert_awaited_once_with(
        code="SUB_test",
        token="recovered-token",
    )
    mark_non_renewing.assert_awaited_once_with(
        db=db,
        subscription=subscription,
        notes="School no longer needs automatic renewal",
    )
    db.commit.assert_awaited_once()
    flush_events.assert_awaited_once_with(db)


def test_customer_subscription_recovery_prefers_matching_active_plan() -> None:
    subscription = SimpleNamespace(plan_code="professional", billing_interval="monthly")
    candidates = [
        {
            "subscription_code": "SUB_other",
            "status": "active",
            "updatedAt": "2026-07-31T10:00:00Z",
            "plan": {"plan_code": "PLN_OTHER"},
        },
        {
            "subscription_code": "SUB_expected",
            "status": "active",
            "updatedAt": "2026-07-30T10:00:00Z",
            "plan": {"plan_code": "PLN_EXPECTED"},
        },
    ]

    with patch.object(
        SubscriptionCancellationService,
        "_provider_plan_code",
        return_value="PLN_EXPECTED",
    ):
        selected = SubscriptionCancellationService._select_customer_subscription(
            subscription,
            candidates,
        )

    assert selected is candidates[1]
