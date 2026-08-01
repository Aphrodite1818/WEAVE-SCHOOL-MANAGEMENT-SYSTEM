import pytest
from pydantic import ValidationError

from app.modules.tenant_branding.schemas import TenantBrandingUpdate


def test_tenant_branding_update_accepts_full_hex_colors() -> None:
    payload = TenantBrandingUpdate(
        primary_color="#2563EB",
        accent_color="#4f46e5",
        sidebar_color="#0F172A",
        header_color="#F8FAFC",
        background_color="#E2E8F0",
        surface_color="#FFFFFF",
    )

    assert payload.primary_color == "#2563EB"
    assert payload.accent_color == "#4f46e5"
    assert payload.sidebar_color == "#0F172A"
    assert payload.header_color == "#F8FAFC"
    assert payload.background_color == "#E2E8F0"
    assert payload.surface_color == "#FFFFFF"


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("primary_color", "2563EB"),
        ("accent_color", "#ABC"),
        ("sidebar_color", "blue"),
        ("header_color", "#123"),
        ("background_color", "slate"),
        ("surface_color", "white"),
    ],
)
def test_tenant_branding_update_rejects_non_strict_hex_colors(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        TenantBrandingUpdate(**{field_name: value})
