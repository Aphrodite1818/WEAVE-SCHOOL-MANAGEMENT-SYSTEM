from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.core.exceptions import ConflictException
from app.modules.subscriptions.cancellation_service import (
    SubscriptionCancellationService,
)
from app.modules.subscriptions.service import SubscriptionPaymentService
from app.modules.subscriptions.subscription_enums import (
    PaymentProvider,
    SubscriptionStatus,
)


@pytest.mark.asyncio
async def test_request_cancellation_disables_paystack_renewal_and_marks_non_renewing() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        provider=PaymentProvider.PAYSTACK,
    )
    saved = SimpleNamespace(**{**subscription.__dict__, "status": SubscriptionStatus.NON_RENEWING})
    db = SimpleNamespace(commit=AsyncMock())

    with (
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ) as get_current,
        patch.object(
            SubscriptionCancellationService,
            "_disable_paystack_renewal",
            new=AsyncMock(),
        ) as disable_subscription,
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionLifecycleService.mark_non_renewing",
            new=AsyncMock(return_value=saved),
        ) as mark_non_renewing,
        patch(
            "app.modules.subscriptions.cancellation_service.flush_cache_invalidation_events",
            new=AsyncMock(),
        ),
    ):
        result = await SubscriptionCancellationService.request_cancellation(
            db,
            tenant_id=tenant_id,
            notes="School requested cancellation",
        )

    assert result is saved
    get_current.assert_awaited_once_with(
        db=db,
        tenant_id=tenant_id,
        for_update=True,
    )
    disable_subscription.assert_awaited_once()
    mark_non_renewing.assert_awaited_once_with(
        db=db,
        subscription=subscription,
        notes="School requested cancellation",
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_request_cancellation_is_idempotent_when_already_non_renewing() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=SubscriptionStatus.NON_RENEWING,
        cancel_at_period_end=True,
        provider=PaymentProvider.PAYSTACK,
    )

    with (
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ),
        patch.object(
            SubscriptionCancellationService,
            "_disable_paystack_renewal",
            new=AsyncMock(),
        ) as disable_subscription,
    ):
        result = await SubscriptionCancellationService.request_cancellation(
            AsyncMock(),
            tenant_id=tenant_id,
        )

    assert result is subscription
    disable_subscription.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_sync_failure_returns_safe_reference() -> None:
    tenant_id = uuid.uuid4()
    subscription = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        status=SubscriptionStatus.ACTIVE,
        cancel_at_period_end=False,
        provider=PaymentProvider.PAYSTACK,
    )

    with (
        patch(
            "app.modules.subscriptions.cancellation_service.SubscriptionRepository.get_current_subscription",
            new=AsyncMock(return_value=subscription),
        ),
        patch.object(
            SubscriptionCancellationService,
            "_disable_paystack_renewal",
            new=AsyncMock(side_effect=ConflictException("provider mismatch")),
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await SubscriptionCancellationService.request_cancellation(
                AsyncMock(),
                tenant_id=tenant_id,
            )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["reason"] == "provider_cancellation_failed"
    assert exc_info.value.detail["reference"].startswith("billing_")


@pytest.mark.asyncio
async def test_paystack_disable_webhook_keeps_access_until_period_end() -> None:
    subscription = SimpleNamespace(tenant_id=uuid.uuid4())
    payload = {"data": {"subscription_code": "SUB_test"}}
    db = AsyncMock()

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
            db,
            payload=payload,
        )

    mark_non_renewing.assert_awaited_once_with(
        db=db,
        subscription=subscription,
        notes="Paystack disabled automatic renewal.",
    )
    cancel_subscription.assert_not_awaited()
