from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.parents.models import ParentAccount, ParentAccountStatus
from app.modules.parents.schemas import ParentAccountProfileUpdateRequest
from app.modules.parents.service import ParentAccountService


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
async def test_update_parent_profile_ignores_explicit_null_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.parents.service.ParentAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.parents.service.ParentAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await ParentAccountService.update_profile(
            db=db,
            account_id=account.id,
            payload=ParentAccountProfileUpdateRequest(
                first_name=None,
                last_name=None,
                phone_number=None,
                occupation=None,
            ),
        )

    assert account.first_name == "Ada"
    assert account.last_name == "Lovelace"
    assert account.phone_number == "+2348012345678"
    assert account.occupation == "Engineer"
    assert response.first_name == "Ada"


@pytest.mark.asyncio
async def test_update_parent_profile_applies_explicit_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.parents.service.ParentAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.parents.service.ParentAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await ParentAccountService.update_profile(
            db=db,
            account_id=account.id,
            payload=ParentAccountProfileUpdateRequest(first_name="Grace"),
        )

    assert account.first_name == "Grace"
    assert response.first_name == "Grace"
