import pytest
from fastapi import HTTPException

from app.config.settings import settings
from app.modules.subscriptions.plan_configuration import (
    SubscriptionPlanConfigurationService,
)
from app.modules.subscriptions.service import SubscriptionPaymentService
from app.modules.subscriptions.subscription_enums import BillingInterval
from app.tenant_management.models import SubscriptionPlan


class FakeProvider:
    def __init__(self, amount: int) -> None:
        self.amount = amount

    async def fetch_plan(self, *, code: str):
        return {
            "status": True,
            "data": {
                "plan_code": code,
                "amount": self.amount,
                "currency": "NGN",
                "interval": "monthly",
            },
        }


@pytest.mark.asyncio
async def test_matching_provider_plan_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO", 1_500_000)
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_matching")
    monkeypatch.setattr(SubscriptionPaymentService, "provider", FakeProvider(1_500_000))
    SubscriptionPlanConfigurationService._validated_until.clear()

    await SubscriptionPlanConfigurationService.validate_checkout_target(
        plan_code=SubscriptionPlan.PLUS,
        billing_interval=BillingInterval.MONTHLY,
    )


@pytest.mark.asyncio
async def test_mismatched_provider_amount_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO", 2_000_000)
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_mismatch")
    monkeypatch.setattr(SubscriptionPaymentService, "provider", FakeProvider(1_500_000))
    SubscriptionPlanConfigurationService._validated_until.clear()

    with pytest.raises(HTTPException) as exc_info:
        await SubscriptionPlanConfigurationService.validate_checkout_target(
            plan_code=SubscriptionPlan.PLUS,
            billing_interval=BillingInterval.MONTHLY,
        )

    assert exc_info.value.status_code == 409
    assert "amount" in str(exc_info.value.detail)
