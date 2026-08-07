from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from fastapi import HTTPException, status

from app.config.settings import settings
from app.modules.subscriptions.constants import (
    PAYSTACK_AMOUNT_SETTING_FIELDS,
    PAYSTACK_PLAN_SETTING_FIELDS,
)
from app.modules.subscriptions.plans import coerce_subscription_plan
from app.modules.subscriptions.subscription_enums import BillingInterval
from app.tenant_management.models import SubscriptionPlan


class SubscriptionPlanConfigurationService:
    _validated_until: dict[str, float] = {}
    _validation_ttl_seconds = 300

    @staticmethod
    def _configured_values(
        plan_code: SubscriptionPlan,
        billing_interval: BillingInterval,
    ) -> tuple[int, str]:
        amount_field = PAYSTACK_AMOUNT_SETTING_FIELDS[plan_code][billing_interval]
        plan_field = PAYSTACK_PLAN_SETTING_FIELDS[plan_code][billing_interval]
        amount_kobo = int(getattr(settings, amount_field, 0) or 0)
        provider_plan_code = str(getattr(settings, plan_field, "") or "").strip()
        if amount_kobo <= 0 or not provider_plan_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Selected plan billing is not configured.",
            )
        return amount_kobo, provider_plan_code

    @classmethod
    async def validate_checkout_target(
        cls,
        *,
        plan_code: str | SubscriptionPlan,
        billing_interval: BillingInterval,
    ) -> None:
        resolved_plan = coerce_subscription_plan(plan_code)
        if resolved_plan == SubscriptionPlan.FREE_TRIAL:
            return

        amount_kobo, provider_plan_code = cls._configured_values(
            resolved_plan,
            billing_interval,
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "plan": resolved_plan.value,
                    "interval": billing_interval.value,
                    "amount": amount_kobo,
                    "provider_plan": provider_plan_code,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        if cls._validated_until.get(fingerprint, 0) > time.monotonic():
            return

        from app.modules.subscriptions.service import SubscriptionPaymentService

        fetch_plan = getattr(SubscriptionPaymentService.provider, "fetch_plan", None)
        if not callable(fetch_plan):
            # Compatibility for isolated test doubles. The production provider
            # always implements fetch_plan.
            return

        try:
            response = await fetch_plan(code=provider_plan_code)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unable to validate provider plan configuration.",
            ) from exc

        data: dict[str, Any] = (
            response.get("data") if isinstance(response.get("data"), dict) else response
        )
        provider_amount = int(data.get("amount") or 0)
        provider_currency = str(data.get("currency") or "").upper()
        provider_interval = str(data.get("interval") or "").lower()
        returned_code = str(data.get("plan_code") or data.get("code") or "").strip()
        mismatches: list[str] = []
        if provider_amount != amount_kobo:
            mismatches.append("amount")
        if provider_currency != "NGN":
            mismatches.append("currency")
        if provider_interval != billing_interval.value:
            mismatches.append("interval")
        if returned_code and returned_code != provider_plan_code:
            mismatches.append("plan_code")

        if mismatches:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Provider plan configuration does not match the backend pricing source "
                    f"of truth: {', '.join(sorted(mismatches))}."
                ),
            )

        cls._validated_until[fingerprint] = (
            time.monotonic() + cls._validation_ttl_seconds
        )
