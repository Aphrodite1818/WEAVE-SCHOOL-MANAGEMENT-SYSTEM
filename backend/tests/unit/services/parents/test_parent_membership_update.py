from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.parents.models import (
    ParentInvitation,
    ParentInvitationStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.parents.schemas import ParentMembershipNotificationUpdateRequest
from app.modules.parents.service import ParentInvitationService, ParentMembershipService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


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


def _invitation(tenant_id: uuid.UUID) -> ParentInvitation:
    now = datetime.now(timezone.utc)
    return ParentInvitation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        student_id=uuid.uuid4(),
        invited_email="parent@example.com",
        relationship_type="guardian",
        admission_number_snapshot="WVS-001",
        token_digest="hashed-token",
        status=ParentInvitationStatus.PENDING,
        expires_at=now,
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


@pytest.mark.asyncio
async def test_revoke_parent_invitation_refreshes_before_response() -> None:
    tenant_id = uuid.uuid4()
    invitation = _invitation(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.parents.service.ParentInvitationRepository.get_by_id",
            new=AsyncMock(return_value=invitation),
        ),
        patch(
            "app.modules.parents.service.ParentInvitationRepository.save",
            new=AsyncMock(return_value=invitation),
        ),
    ):
        response = await ParentInvitationService.revoke_invitation(
            db=db,
            actor=_admin(tenant_id),
            invitation_id=invitation.id,
        )

    assert invitation.status == ParentInvitationStatus.REVOKED
    assert invitation.revoked_at is not None
    assert response.status == ParentInvitationStatus.REVOKED.value
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(invitation)
