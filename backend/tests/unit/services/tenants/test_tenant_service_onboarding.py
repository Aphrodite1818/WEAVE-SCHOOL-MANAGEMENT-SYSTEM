from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.tenant_management.service import TenantService
from app.tenant_management.schemas import TenantUpdate


def test_tenant_update_rejects_client_owned_onboarding_completed():
    with pytest.raises(ValidationError):
        TenantUpdate(onboarding_completed=True)


@pytest.mark.asyncio
async def test_update_tenant_profile_marks_onboarding_complete_when_prefix_exists():
    tenant = SimpleNamespace(
        id=uuid4(),
        school_name="New Horizon School",
        email="admin@wvs.example",
        admission_number_prefix=None,
        onboarding_completed=False,
        phone=None,
        address="1 School Road",
        city="Lagos",
        state="Lagos",
        country="Nigeria",
        logo_url=None,
        timezone="Africa/Lagos",
        language="en",
        school_bot_whatssap_number=None,
    )
    db = AsyncMock()

    with patch(
        "app.tenant_management.service.TenantRepository.get_by_id",
        new=AsyncMock(return_value=tenant),
    ), patch(
        "app.tenant_management.service.TenantRepository.get_by_admission_number_prefix",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.tenant_management.service.TenantRepository.save",
        new=AsyncMock(side_effect=lambda _db, saved_tenant: saved_tenant),
    ):
        updated = await TenantService.update_tenant_profile(
            db=db,
            tenant_id=tenant.id,
            payload=TenantUpdate(
                admission_number_prefix="wvs",
                address="1 School Road",
                city="Lagos",
                state="Lagos",
            ),
        )

    assert updated.admission_number_prefix == "WVS"
    assert updated.onboarding_completed is True
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_update_tenant_profile_marks_onboarding_incomplete_when_prefix_removed():
    tenant = SimpleNamespace(
        id=uuid4(),
        school_name="New Horizon School",
        email="admin@wvs.example",
        admission_number_prefix="WVS",
        onboarding_completed=True,
        phone=None,
        address="1 School Road",
        city="Lagos",
        state="Lagos",
        country="Nigeria",
        logo_url=None,
        timezone="Africa/Lagos",
        language="en",
        school_bot_whatssap_number=None,
    )
    db = AsyncMock()

    with patch(
        "app.tenant_management.service.TenantRepository.get_by_id",
        new=AsyncMock(return_value=tenant),
    ), patch(
        "app.tenant_management.service.TenantRepository.save",
        new=AsyncMock(side_effect=lambda _db, saved_tenant: saved_tenant),
    ):
        updated = await TenantService.update_tenant_profile(
            db=db,
            tenant_id=tenant.id,
            payload=TenantUpdate(admission_number_prefix=None),
        )

    assert updated.admission_number_prefix is None
    assert updated.onboarding_completed is False


@pytest.mark.asyncio
async def test_general_tenant_update_recomputes_onboarding_from_real_fields():
    tenant = SimpleNamespace(
        id=uuid4(),
        school_name="New Horizon School",
        email="admin@wvs.example",
        admission_number_prefix="WVS",
        onboarding_completed=False,
        phone=None,
        address=None,
        city="Lagos",
        state="Lagos",
        country="Nigeria",
        logo_url=None,
        timezone="Africa/Lagos",
        language="en",
        school_bot_whatssap_number=None,
    )
    db = AsyncMock()

    with patch(
        "app.tenant_management.service.TenantRepository.get_by_id",
        new=AsyncMock(return_value=tenant),
    ), patch(
        "app.tenant_management.service.TenantRepository.save",
        new=AsyncMock(side_effect=lambda _db, saved_tenant: saved_tenant),
    ):
        updated = await TenantService.update_tenant_profile(
            db=db,
            tenant_id=tenant.id,
            payload=TenantUpdate(phone="+2348012345678"),
        )

    assert updated.phone == "+2348012345678"
    assert updated.onboarding_completed is False
