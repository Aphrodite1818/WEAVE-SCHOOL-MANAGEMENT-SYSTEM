from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException
from app.modules.parents.account_patch_service import ParentAccountPatchService
from app.modules.parents.models import ParentAccount, ParentAccountStatus
from app.modules.parents.schemas import ParentAccountProfileUpdateRequest


def _account() -> ParentAccount:
    now = datetime.now(timezone.utc)
    return ParentAccount(
        id=uuid.uuid4(),
        email="parent@example.com",
        password_hash="hashed",
        first_name="Ada",
        last_name="Lovelace",
        phone_number="+2348012345678",
        occupation="Engineer",
        address="1 Example Street",
        emergency_phone="+2348098765432",
        account_status=ParentAccountStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_parent_profile_rejects_null_required_name() -> None:
    account = _account()
    db = AsyncMock()

    with patch(
        "app.modules.parents.account_patch_service.ParentAccountRepository.get_by_id",
        new=AsyncMock(return_value=account),
    ):
        with pytest.raises(BadRequestException):
            await ParentAccountPatchService.update_profile(
                db=db,
                account_id=account.id,
                payload=ParentAccountProfileUpdateRequest(first_name=None),
            )


@pytest.mark.asyncio
async def test_parent_profile_clears_explicit_nullable_field() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.parents.account_patch_service.ParentAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.parents.account_patch_service.ParentAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await ParentAccountPatchService.update_profile(
            db=db,
            account_id=account.id,
            payload=ParentAccountProfileUpdateRequest(occupation=None),
        )

    assert account.occupation is None
    assert account.phone_number == "+2348012345678"
    assert response.occupation is None


@pytest.mark.asyncio
async def test_parent_profile_applies_only_explicit_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.parents.account_patch_service.ParentAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.parents.account_patch_service.ParentAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await ParentAccountPatchService.update_profile(
            db=db,
            account_id=account.id,
            payload=ParentAccountProfileUpdateRequest(first_name="Grace"),
        )

    assert account.first_name == "Grace"
    assert account.last_name == "Lovelace"
    assert account.occupation == "Engineer"
    assert response.first_name == "Grace"
