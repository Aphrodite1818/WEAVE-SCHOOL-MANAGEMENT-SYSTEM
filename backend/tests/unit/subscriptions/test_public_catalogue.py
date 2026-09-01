import pytest

from app.config.settings import settings
from app.modules.subscriptions.catalogue import PublicSubscriptionCatalogueService


@pytest.mark.asyncio
async def test_public_catalogue_is_term_priced_and_includes_permanent_free(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_TERM_AMOUNT_KOBO", 1_700_000)
    catalogue = PublicSubscriptionCatalogueService.build_catalogue()
    by_code = {item.plan_code: item for item in catalogue.plans}
    assert catalogue.billing_intervals == ["term"]
    assert by_code["free"].amount_kobo == 0
    assert by_code["plus"].amount_kobo == 1_700_000
    assert "free_trial" not in by_code
    assert by_code["free"].features["advanced_analytics"] is True
