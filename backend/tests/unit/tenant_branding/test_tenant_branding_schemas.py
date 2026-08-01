import pytest
from pydantic import ValidationError

from app.modules.tenant_branding.schemas import TenantBrandingUpdate


def test_tenant_branding_update_accepts_palette_and_enabled_state() -> None:
    payload = TenantBrandingUpdate(palette_key="gold", is_enabled=True)

    assert payload.palette_key == "gold"
    assert payload.is_enabled is True


def test_tenant_branding_update_rejects_unknown_palette() -> None:
    with pytest.raises(ValidationError, match="palette_key"):
        TenantBrandingUpdate(palette_key="neon-green")


@pytest.mark.parametrize(
    "field_name",
    [
        "brand_name",
        "primary_color",
        "accent_color",
        "sidebar_color",
        "header_color",
        "background_color",
        "surface_color",
    ],
)
def test_tenant_branding_update_rejects_direct_identity_and_color_fields(
    field_name: str,
) -> None:
    with pytest.raises(ValidationError):
        TenantBrandingUpdate(**{field_name: "#2563EB"})
