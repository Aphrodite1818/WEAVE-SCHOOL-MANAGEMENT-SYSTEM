from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_branding.schemas import TenantBrandingUpdate
from app.modules.tenant_branding.service import TenantBrandingService
from app.tenant_management.models import SubscriptionPlan, Tenant, TenantStatus, TenantVerificationStatus


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


@pytest.mark.asyncio
async def test_update_tenant_branding_rejects_external_logo_urls() -> None:
    tenant_id = uuid.uuid4()
    tenant = _build_tenant(tenant_id, logo_url="https://cdn.weave.test/logo.png")
    actor = _build_admin(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.tenant_branding.service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
        patch(
            "app.modules.tenant_branding.service.TenantBrandingRepository.get_by_tenant_id_for_update",
            new=AsyncMock(),
        ) as get_branding_for_update,
    ):
        with pytest.raises(BadRequestException, match="logo_url must match the tenant's uploaded school logo"):
            await TenantBrandingService.update_tenant_branding(
                db=db,
                actor=actor,
                payload=TenantBrandingUpdate(
                    brand_name="Greenfield Academy",
                    logo_url="https://evil.example/logo.png",
                ),
            )

    get_branding_for_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_tenant_branding_allows_current_uploaded_logo_reference() -> None:
    tenant_id = uuid.uuid4()
    tenant_logo_url = "https://cdn.weave.test/logo.png"
    tenant = _build_tenant(tenant_id, logo_url=tenant_logo_url)
    actor = _build_admin(tenant_id)
    db = AsyncMock()

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
            payload=TenantBrandingUpdate(logo_url=tenant_logo_url),
        )

    assert response.logo_url == tenant_logo_url
    assert response.header_color == "#F8FAFC"
    assert response.background_color == "#F8FAFC"
    assert response.tokens["--color-header-background"] == "248 250 252"
    assert response.tokens["--color-workspace-background"] == "248 250 252"
    assert response.theme_version == 0
    db.commit.assert_not_awaited()
