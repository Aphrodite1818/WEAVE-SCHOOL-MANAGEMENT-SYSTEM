from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.config.settings import settings
from app.core.cache.base import build_cache_key
from app.core.cache.manager import CacheManager
from app.modules.subscriptions.constants import (
    DEFAULT_CURRENCY,
    DEFAULT_TRIAL_DAYS,
    PAYSTACK_AMOUNT_SETTING_FIELDS,
    PAYSTACK_PLAN_SETTING_FIELDS,
)
from app.modules.subscriptions.plans import get_plan_entitlements
from app.modules.subscriptions.subscription_enums import BillingInterval
from app.tenant_management.models import SubscriptionPlan

PLAN_DISPLAY_NAMES = {
    SubscriptionPlan.FREE_TRIAL: "Free Trial",
    SubscriptionPlan.PLUS: "Plus",
    SubscriptionPlan.PROFESSIONAL: "Professional",
    SubscriptionPlan.ENTERPRISE: "Enterprise",
}
PLAN_ORDER = (
    SubscriptionPlan.FREE_TRIAL,
    SubscriptionPlan.PLUS,
    SubscriptionPlan.PROFESSIONAL,
    SubscriptionPlan.ENTERPRISE,
)


class PublicSubscriptionPlan(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    plan_code: str
    name: str
    amount: int
    amount_kobo: int
    currency: str
    billing_interval: BillingInterval
    trial_days: int | None = None
    checkout_enabled: bool
    features: dict[str, bool]
    limits: dict[str, int | None]


class PublicSubscriptionCatalogue(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    currency: str
    billing_intervals: list[BillingInterval]
    cache_version: str
    plans: list[PublicSubscriptionPlan]


class PublicSubscriptionCatalogueService:
    @staticmethod
    def _amount_kobo(plan: SubscriptionPlan) -> int:
        if plan == SubscriptionPlan.FREE_TRIAL:
            return 0
        field_name = PAYSTACK_AMOUNT_SETTING_FIELDS[plan][BillingInterval.MONTHLY]
        value = getattr(settings, field_name, None)
        return int(value or 0)

    @staticmethod
    def _checkout_enabled(plan: SubscriptionPlan, amount_kobo: int) -> bool:
        if plan == SubscriptionPlan.FREE_TRIAL:
            return True
        field_name = PAYSTACK_PLAN_SETTING_FIELDS[plan][BillingInterval.MONTHLY]
        return amount_kobo > 0 and bool(getattr(settings, field_name, None))

    @classmethod
    def _source_payload(cls) -> dict[str, Any]:
        plans: list[dict[str, Any]] = []
        for plan in PLAN_ORDER:
            entitlements = get_plan_entitlements(plan)
            amount_kobo = cls._amount_kobo(plan)
            plans.append(
                {
                    "plan_code": plan.value,
                    "amount_kobo": amount_kobo,
                    "checkout_enabled": cls._checkout_enabled(plan, amount_kobo),
                    "features": {
                        feature.value: enabled for feature, enabled in entitlements.features.items()
                    },
                    "limits": {
                        resource.value: limit for resource, limit in entitlements.limits.items()
                    },
                }
            )
        return {"currency": DEFAULT_CURRENCY, "plans": plans}

    @classmethod
    def _cache_version(cls) -> str:
        encoded = json.dumps(
            cls._source_payload(),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:16]

    @classmethod
    def _cache_key(cls) -> str:
        return build_cache_key(
            "subscriptions",
            "public-plans",
            cls._cache_version(),
        )

    @classmethod
    def build_catalogue(cls) -> PublicSubscriptionCatalogue:
        source = cls._source_payload()
        plans_by_code = {item["plan_code"]: item for item in source["plans"]}
        plans: list[PublicSubscriptionPlan] = []

        for plan in PLAN_ORDER:
            item = plans_by_code[plan.value]
            amount_kobo = int(item["amount_kobo"])
            plans.append(
                PublicSubscriptionPlan(
                    plan_code=plan.value,
                    name=PLAN_DISPLAY_NAMES[plan],
                    amount=amount_kobo // 100,
                    amount_kobo=amount_kobo,
                    currency=DEFAULT_CURRENCY,
                    billing_interval=BillingInterval.MONTHLY,
                    trial_days=(
                        DEFAULT_TRIAL_DAYS if plan == SubscriptionPlan.FREE_TRIAL else None
                    ),
                    checkout_enabled=bool(item["checkout_enabled"]),
                    features=dict(item["features"]),
                    limits=dict(item["limits"]),
                )
            )

        return PublicSubscriptionCatalogue(
            currency=DEFAULT_CURRENCY,
            billing_intervals=[BillingInterval.MONTHLY],
            cache_version=cls._cache_version(),
            plans=plans,
        )

    @classmethod
    async def get_catalogue(cls) -> PublicSubscriptionCatalogue:
        key = cls._cache_key()
        cached = await CacheManager.get_json(key)
        if cached is not None:
            return PublicSubscriptionCatalogue.model_validate(cached)

        catalogue = cls.build_catalogue()
        await CacheManager.set_json(
            key=key,
            value=catalogue.model_dump(mode="json"),
            ttl=settings.CACHE_LONG_TTL_SECONDS,
        )
        return catalogue
