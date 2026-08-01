from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pydantic import ValidationError
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_branding.models import TenantBranding
from app.modules.tenant_branding.schemas import TenantBrandingUpdate
from app.modules.tenant_branding.service import TenantBrandingService
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)


def _build_tenant(tenant_id: uuid.UUID, *, logo_url: str | None) -> Tenant:
    return Tenant(
        id=tenant_id,
        school_name="Greenfield Academy",
        slug="greenfield-academy",
        admission_number_prefix="GFA",
        email="hello@greenfield.test",
        country="Nigeria",
        logo_url=logo_url,
        status=TenantStatus.ACTIVE,
        plan=SubscriptionPlan.FREE_TRIAL,
        verification_status=TenantVerificationStatus.ACTIVE,
        is_deleted=False,
        onboarding_completed=True,
        max_students=500,
        max_teachers=50,
        timezone="Africa/Lagos",
        language="en",
    )


def _build_admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@greenfield.test",
        password_hash="hashed-password",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def test_update_tenant_branding_rejects_all_logo_url_inputs() -> None:
    with pytest.raises(ValidationError, match="logo_url"):
        TenantBrandingUpdate(logo_url="https://evil.example/logo.png")


@pytest.mark.asyncio
async def test_update_tenant_branding_uses_current_tenant_logo() -> None:
    tenant_id = uuid.uuid4()
    tenant_logo_url = "https://cdn.weave.test/logo.png"
    tenant = _build_tenant(tenant_id, logo_url=tenant_logo_url)
    tenant.plan = SubscriptionPlan.PROFESSIONAL
    actor = _build_admin(tenant_id)
    db = AsyncMock()
    db.add = MagicMock()

    with (
        patch(
            "app.modules.tenant_branding.service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.tenant_branding.service.TenantBrandingRepository.get_by_tenant_id_for_update",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await TenantBrandingService.update_tenant_branding(
            db=db,
            actor=actor,
            payload=TenantBrandingUpdate(palette_key="gold"),
        )

    assert response.logo_url == tenant_logo_url
    assert response.school_name == tenant.school_name
    assert response.palette_key == "gold"
    assert response.light_tokens["--color-primary"] == "161 98 7"
    assert response.light_tokens["--color-background"] == "248 250 252"
    assert response.token_schema_version == 2
    assert response.theme_version == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_disables_branding_increments_version_and_keeps_logo() -> None:
    tenant_id = uuid.uuid4()
    tenant = _build_tenant(tenant_id, logo_url="https://cdn.weave.test/logo.png")
    tenant.plan = SubscriptionPlan.ENTERPRISE
    actor = _build_admin(tenant_id)
    row = TenantBranding(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        palette_key="rose",
        logo_url="deprecated.png",
        primary_color="#111827",
        accent_color="#7C3AED",
        sidebar_color="#172554",
        header_color="#FFFFFF",
        surface_color="#FFFFFF",
        tokens={},
        is_enabled=True,
        theme_version=7,
        token_schema_version=0,
        updated_by_admin_id=actor.id,
    )
    db = AsyncMock()

    async def apply_reset(*, branding, defaults, **_kwargs):
        for key, value in defaults.items():
            setattr(branding, key, value)
        return branding

    with (
        patch(
            "app.modules.tenant_branding.service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.tenant_branding.service.TenantBrandingRepository.get_by_tenant_id_for_update",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.tenant_branding.service.TenantBrandingRepository.reset_branding",
            new=AsyncMock(side_effect=apply_reset),
        ),
        patch(
            "app.modules.tenant_branding.service.invalidate_tenant_branding", new=AsyncMock()
        ) as invalidate,
        patch(
            "app.modules.tenant_branding.service.flush_cache_invalidation_events", new=AsyncMock()
        ),
    ):
        response = await TenantBrandingService.reset_tenant_branding(db=db, actor=actor)

    assert response.is_enabled is False
    assert response.is_default_theme is True
    assert response.theme_version == 8
    assert response.logo_url == tenant.logo_url
    assert response.school_name == tenant.school_name
    assert row.palette_key == "blue"
    assert row.token_schema_version == 2
    invalidate.assert_awaited_once_with(tenant_id, db=db)
    db.commit.assert_awaited_once()
