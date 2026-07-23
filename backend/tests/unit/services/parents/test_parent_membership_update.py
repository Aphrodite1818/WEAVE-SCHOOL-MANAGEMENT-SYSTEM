from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.parents.models import ParentMembership, ParentMembershipStatus
from app.modules.parents.schemas import ParentMembershipNotificationUpdateRequest
from app.modules.parents.service import ParentMembershipService


def _membership() -> ParentMembership:
    now = datetime.now(timezone.utc)
    return ParentMembership(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        parent_account_id=uuid.uuid4(),
        status=ParentMembershipStatus.ACTIVE,
        joined_at=now,
        receive_email_notifications=True,
        receive_push_notifications=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_notifications_ignores_explicit_null_values() -> None:
    membership = _membership()
    db = AsyncMock()

    with patch(
        "app.modules.parents.service.ParentMembershipRepository.save",
        new=AsyncMock(return_value=membership),
    ):
        response = await ParentMembershipService.update_notifications(
            db=db,
            membership=membership,
            payload=ParentMembershipNotificationUpdateRequest(
                receive_email_notifications=None,
                receive_push_notifications=None,
            ),
        )

    assert membership.receive_email_notifications is True
    assert membership.receive_push_notifications is True
    assert response.receive_email_notifications is True
    assert response.receive_push_notifications is True


@pytest.mark.asyncio
async def test_update_notifications_applies_explicit_boolean_values() -> None:
    membership = _membership()
    db = AsyncMock()

    with patch(
        "app.modules.parents.service.ParentMembershipRepository.save",
        new=AsyncMock(return_value=membership),
    ):
        response = await ParentMembershipService.update_notifications(
            db=db,
            membership=membership,
            payload=ParentMembershipNotificationUpdateRequest(
                receive_email_notifications=False,
            ),
        )

    assert membership.receive_email_notifications is False
    assert membership.receive_push_notifications is True
    assert response.receive_email_notifications is False
