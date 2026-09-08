from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.branding.service import CBTBrandingProjectionService
from app.modules.cbt.enums import CBTServerStatus


def _server(tenant_id):
    return AuthenticatedCBTServer(
        server_id=uuid4(),
        credential_id=uuid4(),
        tenant_id=tenant_id,
        server_name="Exam Hall Server",
        status=CBTServerStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_branding_projection_uses_effective_theme_and_media_asset_revision() -> None:
    tenant_id = uuid4()
    logo_asset_id = uuid4()
    db = AsyncMock()
    effective = SimpleNamespace(
        tenant_id=tenant_id,
        school_name="Greenfield School",
        logo_url="https://cdn.example.test/logo.png",
        is_enabled=True,
        is_default_theme=False,
        theme_version=7,
        token_schema_version=2,
        light_tokens={"primary": "#111111"},
        dark_tokens={"primary": "#eeeeee"},
    )

    with (
        patch(
            "app.modules.cbt.branding.service.TenantBrandingService.get_effective_tenant_branding",
            new=AsyncMock(return_value=effective),
        ),
        patch(
            "app.modules.cbt.branding.service.MediaAssetRepository.get_current_for_owner",
            new=AsyncMock(return_value=SimpleNamespace(id=logo_asset_id)),
        ),
    ):
        response = await CBTBrandingProjectionService.build_projection(
            db,
            current_server=_server(tenant_id),
        )

    assert response.tenant_id == tenant_id
    assert response.school_name == "Greenfield School"
    assert response.logo_revision == logo_asset_id
    assert response.theme_version == 7
    assert response.is_default_theme is False


@pytest.mark.asyncio
async def test_branding_projection_keeps_logo_when_custom_theme_is_disabled() -> None:
    tenant_id = uuid4()
    db = AsyncMock()
    effective = SimpleNamespace(
        tenant_id=tenant_id,
        school_name="Greenfield School",
        logo_url="https://cdn.example.test/logo.png",
        is_enabled=False,
        is_default_theme=True,
        theme_version=4,
        token_schema_version=2,
        light_tokens={"primary": "#111111"},
        dark_tokens={"primary": "#eeeeee"},
    )

    with (
        patch(
            "app.modules.cbt.branding.service.TenantBrandingService.get_effective_tenant_branding",
            new=AsyncMock(return_value=effective),
        ),
        patch(
            "app.modules.cbt.branding.service.MediaAssetRepository.get_current_for_owner",
            new=AsyncMock(return_value=None),
        ),
    ):
        response = await CBTBrandingProjectionService.build_projection(
            db,
            current_server=_server(tenant_id),
        )

    assert response.is_enabled is False
    assert response.is_default_theme is True
    assert response.logo_url == "https://cdn.example.test/logo.png"
    assert response.logo_revision is None
