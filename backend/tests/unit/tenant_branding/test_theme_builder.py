import pytest

from app.modules.tenant_branding.theme_builder import (
    BRANDING_PALETTES,
    SEMANTIC_THEME_TOKEN_KEYS,
    build_default_theme_token_sets,
    build_palette_theme_token_sets,
    build_theme_token_sets,
    choose_readable_text_color,
    hex_to_rgb,
)
from app.modules.subscriptions.plans import get_plan_entitlements
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.tenant_management.models import SubscriptionPlan


def test_default_and_custom_palettes_have_complete_light_and_dark_contracts() -> None:
    payloads = [build_default_theme_token_sets()]
    payloads.extend(build_palette_theme_token_sets(key) for key in BRANDING_PALETTES)

    for payload in payloads:
        assert set(payload) == {"light", "dark"}
        assert set(payload["light"]) == SEMANTIC_THEME_TOKEN_KEYS
        assert set(payload["dark"]) == SEMANTIC_THEME_TOKEN_KEYS

    for palette_key in BRANDING_PALETTES:
        tokens = build_palette_theme_token_sets(palette_key)
        assert tokens["light"]["--color-on-primary"] == "255 255 255"
        assert tokens["light"]["--color-header-background"] == "255 255 255"
        assert tokens["dark"]["--color-background"] == "15 23 42"
        assert tokens["dark"]["--color-header-background"] == "15 23 42"
        assert tokens["dark"]["--color-sidebar-background"] == "15 23 42"


def test_pale_primary_uses_dark_readable_foreground() -> None:
    tokens = build_theme_token_sets(
        primary_color="#FDE68A",
        accent_color="#4F46E5",
        sidebar_color="#FFFFFF",
        header_color="#FFFFFF",
        background_color="#F8FAFC",
        surface_color="#FFFFFF",
    )
    assert tokens["light"]["--color-on-primary"] == "15 23 42"
    assert choose_readable_text_color(hex_to_rgb("#FDE68A")) == (15, 23, 42)


def test_surface_source_drives_surface_and_visible_border_tokens() -> None:
    tokens = build_theme_token_sets(
        primary_color="#1D4ED8",
        accent_color="#4F46E5",
        sidebar_color="#FFFFFF",
        header_color="#FFFFFF",
        background_color="#F8FAFC",
        surface_color="#FFF7ED",
    )["light"]
    assert tokens["--color-surface"] == "255 247 237"
    assert tokens["--color-border"] != tokens["--color-surface"]


def test_curated_palette_keeps_workspace_background_fixed() -> None:
    gold = build_palette_theme_token_sets("gold")
    blue = build_palette_theme_token_sets("blue")

    assert gold["light"]["--color-background"] == blue["light"]["--color-background"]
    assert gold["dark"]["--color-background"] == "15 23 42"
    assert blue["dark"]["--color-background"] == "15 23 42"


def test_unknown_palette_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown branding palette"):
        build_palette_theme_token_sets("neon-green")


def test_tenant_branding_is_professional_and_enterprise_only() -> None:
    assert not get_plan_entitlements(SubscriptionPlan.FREE_TRIAL).features[
        FeatureCode.TENANT_BRANDING
    ]
    assert not get_plan_entitlements(SubscriptionPlan.PLUS).features[FeatureCode.TENANT_BRANDING]
    assert get_plan_entitlements(SubscriptionPlan.PROFESSIONAL).features[
        FeatureCode.TENANT_BRANDING
    ]
    assert get_plan_entitlements(SubscriptionPlan.ENTERPRISE).features[FeatureCode.TENANT_BRANDING]
