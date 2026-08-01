from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.media.models import MediaOwnerType, MediaPurpose
from app.modules.media.service import MediaService


@pytest.mark.asyncio
async def test_school_logo_attachment_invalidates_effective_branding_cache() -> None:
    tenant_id = uuid.uuid4()
    tenant = MagicMock(logo_url=None)
    media_asset = MagicMock()
    db = AsyncMock()

    with (
        patch.object(MediaService, "_get_owner_media_url_for_attachment", return_value="https://cdn.test/logo.png"),
        patch.object(MediaService, "_get_tenant", new=AsyncMock(return_value=tenant)),
        patch("app.modules.media.service.TenantRepository.save", new=AsyncMock()) as save_tenant,
        patch("app.modules.media.service.invalidate_tenant_branding", new=AsyncMock()) as invalidate,
    ):
        await MediaService._attach_media_to_owner(
            db=db,
            tenant_id=tenant_id,
            owner_type=MediaOwnerType.TENANT,
            owner_id=tenant_id,
            purpose=MediaPurpose.SCHOOL_LOGO,
            media_asset=media_asset,
        )

    assert tenant.logo_url == "https://cdn.test/logo.png"
    save_tenant.assert_awaited_once_with(db=db, tenant=tenant)
    invalidate.assert_awaited_once_with(tenant_id, db=db)
