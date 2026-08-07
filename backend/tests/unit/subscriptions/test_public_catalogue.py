from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.config.settings import settings
from app.modules.subscriptions.catalogue import PublicSubscriptionCatalogueService


@pytest.mark.asyncio
async def test_public_catalogue_uses_environment_backed_prices(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO", 1_700_000)
    monkeypatch.setattr(settings, "PAYSTACK_PROFESSIONAL_MONTHLY_AMOUNT_KOBO", 3_900_000)
    monkeypatch.setattr(settings, "PAYSTACK_ENTERPRISE_MONTHLY_AMOUNT_KOBO", 8_500_000)
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_plus")
    monkeypatch.setattr(settings, "PAYSTACK_PROFESSIONAL_MONTHLY_PLAN_CODE", "PLN_professional")
    monkeypatch.setattr(settings, "PAYSTACK_ENTERPRISE_MONTHLY_PLAN_CODE", "PLN_enterprise")

    catalogue = PublicSubscriptionCatalogueService.build_catalogue()
    plans = {plan.plan_code: plan for plan in catalogue.plans}

    assert plans["plus"].amount == 17_000
    assert plans["plus"].amount_kobo == 1_700_000
    assert plans["professional"].amount == 39_000
    assert plans["enterprise"].amount == 85_000
    assert plans["plus"].checkout_enabled is True
    assert plans["plus"].limits["students"] == 500
    assert plans["plus"].limits["teachers"] == 50
    assert plans["plus"].limits["classes"] == 50
    assert plans["professional"].features["advanced_analytics"] is True


@pytest.mark.asyncio
async def test_public_catalogue_uses_long_cache(monkeypatch):
    cached_payload = PublicSubscriptionCatalogueService.build_catalogue().model_dump(mode="json")
    get_json = AsyncMock(return_value=cached_payload)
    set_json = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "app.modules.subscriptions.catalogue.CacheManager.get_json",
        get_json,
    )
    monkeypatch.setattr(
        "app.modules.subscriptions.catalogue.CacheManager.set_json",
        set_json,
    )

    result = await PublicSubscriptionCatalogueService.get_catalogue()

    assert result.cache_version == cached_payload["cache_version"]
    get_json.assert_awaited_once()
    set_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalogue_cache_key_changes_when_price_changes(monkeypatch):
    first_key = PublicSubscriptionCatalogueService._cache_key()
    monkeypatch.setattr(
        settings,
        "PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO",
        settings.PAYSTACK_PLUS_MONTHLY_AMOUNT_KOBO + 100,
    )
    second_key = PublicSubscriptionCatalogueService._cache_key()

    assert first_key != second_key
