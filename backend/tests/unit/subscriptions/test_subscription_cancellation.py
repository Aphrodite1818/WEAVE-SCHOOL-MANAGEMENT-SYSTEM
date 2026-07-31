from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException
from app.modules.subscriptions.service import (
    SubscriptionLifecycleService,
    SubscriptionPaymentService,
)
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    SubscriptionStatus,
)


@pytest.mark.asyncio
async def test_request_cancellation_disables_paystack_renewal_and_marks_non_renewing() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        tenant_id=tenant_id,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        provider=PaymentProvider.PAYSTACK,
        provider_subscription_code="SUB_test",
        provider_email_token="email-token",
    )
    saved = SimpleNamespace(**subscription.__dict__, status=SubscriptionStatus.NON_RENEWING)
    db = AsyncMock()

    with (
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ) as get_current,
        patch(
            "app.modules.subscriptions.service.PaystackClient.disable_subscription",
            new=AsyncMock(return_value={"status": True}),
        ) as disable_subscription,
        patch(
            "app.modules.subscriptions.service.SubscriptionLifecycleService.mark_non_renewing",
            new=AsyncMock(return_value=saved),
        ) as mark_non_renewing,
    ):
        result = await SubscriptionLifecycleService.request_cancellation(
            db,
            tenant_id=tenant_id,
            notes="School requested cancellation",
        )

    assert result is saved
    get_current.assert_awaited_once_with(db=db, tenant_id=tenant_id, for_update=True)
    disable_subscription.assert_awaited_once_with(code="SUB_test", token="email-token")
    mark_non_renewing.assert_awaited_once_with(
        db=db,
        subscription=subscription,
        notes="School requested cancellation",
    )


@pytest.mark.asyncio
async def test_request_cancellation_is_idempotent_when_already_non_renewing() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        tenant_id=tenant_id,
        status=SubscriptionStatus.NON_RENEWING,
        cancel_at_period_end=True,
        provider=PaymentProvider.PAYSTACK,
        provider_subscription_code="SUB_test",
        provider_email_token="email-token",
    )

    with (
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ),
        patch(
            "app.modules.subscriptions.service.PaystackClient.disable_subscription",
            new=AsyncMock(),
        ) as disable_subscription,
        patch(
            "app.modules.subscriptions.service.SubscriptionLifecycleService.mark_non_renewing",
            new=AsyncMock(),
        ) as mark_non_renewing,
    ):
        result = await SubscriptionLifecycleService.request_cancellation(
            AsyncMock(),
            tenant_id=tenant_id,
        )

    assert result is subscription
    disable_subscription.assert_not_awaited()
    mark_non_renewing.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_cancellation_rejects_missing_paystack_credentials() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        tenant_id=tenant_id,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        provider=PaymentProvider.PAYSTACK,
        provider_subscription_code=None,
        provider_email_token=None,
    )

    with patch(
        "app.modules.subscriptions.service.SubscriptionRepository.get_current_subscription",
        new=AsyncMock(return_value=subscription),
    ):
        with pytest.raises(BadRequestException, match="missing the provider cancellation credentials"):
            await SubscriptionLifecycleService.request_cancellation(
                AsyncMock(),
                tenant_id=tenant_id,
            )


@pytest.mark.asyncio
async def test_paystack_disable_webhook_keeps_access_until_period_end() -> None:
    subscription = SimpleNamespace(tenant_id=uuid.uuid4())
    payload = {"data": {"subscription_code": "SUB_test"}}

    with (
        patch(
            "app.modules.subscriptions.service.SubscriptionRepository.find_subscription_by_provider_subscription_code",
            new=AsyncMock(return_value=subscription),
        ),
        patch(
            "app.modules.subscriptions.service.SubscriptionLifecycleService.mark_non_renewing",
            new=AsyncMock(return_value=subscription),
        ) as mark_non_renewing,
        patch(
            "app.modules.subscriptions.service.SubscriptionLifecycleService.cancel_subscription",
            new=AsyncMock(),
        ) as cancel_subscription,
    ):
        await SubscriptionPaymentService.handle_subscription_disable(
            AsyncMock(),
            payload=payload,
        )

    mark_non_renewing.assert_awaited_once_with(
        db=pytest.ANY,
        subscription=subscription,
        notes="Paystack disabled automatic renewal.",
    )
    cancel_subscription.assert_not_awaited()
