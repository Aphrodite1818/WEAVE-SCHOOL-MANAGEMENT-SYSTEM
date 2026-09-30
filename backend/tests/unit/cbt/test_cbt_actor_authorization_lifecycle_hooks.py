from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.cbt.auth.service import CBTActorAuthorizationService
from app.modules.teachers.models import (
    TeacherAccountStatus,
    TeacherMembershipStatus,
)
from app.modules.teachers.schemas import (
    TeacherMembershipEndRequest,
    TeacherMembershipSuspendRequest,
    TeacherPasswordChangeRequest,
)
from app.modules.teachers.service import TeacherAccountService, TeacherMembershipService
from app.modules.tenant_admins.models import TenantAdminStatus
from app.modules.tenant_admins.schemas import TenantAdminUpdate
from app.modules.tenant_admins.service import TenantAdminService


def _membership(*, status: TeacherMembershipStatus = TeacherMembershipStatus.ACTIVE):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        teacher_account_id=uuid4(),
        staff_id="T-001",
        job_title="Teacher",
        department=None,
        employment_type=None,
        status=status,
        joined_at=now,
        ended_at=None,
        end_reason=None,
        receive_email_notifications=True,
        receive_push_notifications=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_teacher_suspension_revokes_cbt_authorizations_in_same_service_flow(monkeypatch) -> None:
    membership = _membership()
    actor = SimpleNamespace(tenant_id=membership.tenant_id)
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipRepository.get_by_id",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipRepository.save",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipService._revoke_membership_sessions",
        AsyncMock(),
    )
    revoke = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.modules.teachers.service.CBTActorAuthorizationService.revoke_for_teacher_membership",
        revoke,
    )

    await TeacherMembershipService.suspend_membership(
        db,
        actor=actor,
        membership_id=membership.id,
        payload=TeacherMembershipSuspendRequest(reason="Security suspension"),
    )

    assert membership.status == TeacherMembershipStatus.SUSPENDED
    revoke.assert_awaited_once_with(
        db,
        tenant_id=membership.tenant_id,
        membership_id=membership.id,
        reason="membership_suspended",
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_teacher_membership_end_revokes_cbt_authorizations(monkeypatch) -> None:
    membership = _membership()
    actor = SimpleNamespace(tenant_id=membership.tenant_id)
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipRepository.get_by_id",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipRepository.save",
        AsyncMock(return_value=membership),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherMembershipService._revoke_membership_sessions",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.SubscriptionFeatureService.invalidate_tenant_subscription_state",
        AsyncMock(),
    )
    revoke = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.modules.teachers.service.CBTActorAuthorizationService.revoke_for_teacher_membership",
        revoke,
    )

    await TeacherMembershipService.end_membership(
        db,
        actor=actor,
        membership_id=membership.id,
        payload=TeacherMembershipEndRequest(reason="Employment ended"),
    )

    assert membership.status == TeacherMembershipStatus.INACTIVE
    revoke.assert_awaited_once_with(
        db,
        tenant_id=membership.tenant_id,
        membership_id=membership.id,
        reason="membership_ended",
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_teacher_password_change_revokes_all_teacher_cbt_authorizations(monkeypatch) -> None:
    account_id = uuid4()
    account = SimpleNamespace(
        id=account_id,
        password_hash="old-hash",
        is_active=True,
        is_verified=True,
        account_status=TeacherAccountStatus.ACTIVE,
    )
    db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())

    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherAccountRepository.get_by_id",
        AsyncMock(return_value=account),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherAccountRepository.save",
        AsyncMock(return_value=account),
    )
    monkeypatch.setattr(
        "app.modules.teachers.service.TeacherAccountRepository.list_memberships",
        AsyncMock(return_value=[]),
    )
    verify = Mock(side_effect=[True, False])
    monkeypatch.setattr("app.modules.teachers.service.verify_password", verify)
    monkeypatch.setattr("app.modules.teachers.service.hash_password", lambda _: "new-hash")
    revoke = AsyncMock(return_value=2)
    monkeypatch.setattr(
        "app.modules.teachers.service.CBTActorAuthorizationService.revoke_for_teacher_account",
        revoke,
    )

    await TeacherAccountService.change_password(
        db,
        account_id=account_id,
        payload=TeacherPasswordChangeRequest(
            current_password="OldPass123!",
            new_password="NewPass123!",
            confirm_password="NewPass123!",
        ),
    )

    assert account.password_hash == "new-hash"
    revoke.assert_awaited_once_with(
        db,
        teacher_account_id=account_id,
        reason="password_changed",
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_tenant_admin_becoming_ineligible_revokes_cbt_authorizations(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    admin = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        email="admin@example.com",
        password_hash="hash",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        last_login_at=None,
        created_at=now,
        updated_at=now,
        passport_photo_url=None,
    )
    db = AsyncMock()

    monkeypatch.setattr(
        "app.modules.tenant_admins.service.TenantAdminRepository.get_by_id",
        AsyncMock(return_value=admin),
    )
    monkeypatch.setattr(
        "app.modules.tenant_admins.service.TenantAdminRepository.save",
        AsyncMock(return_value=admin),
    )
    monkeypatch.setattr(
        "app.modules.tenant_admins.service.AuthIdentityService.deactivate_for_actor",
        AsyncMock(),
    )
    revoke = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.modules.tenant_admins.service.CBTActorAuthorizationService.revoke_for_tenant_admin",
        revoke,
    )

    response = await TenantAdminService.update_tenant_admin(
        db,
        admin_id=admin.id,
        payload=TenantAdminUpdate(is_active=False),
    )

    assert response is not None
    assert response.is_active is False
    revoke.assert_awaited_once_with(
        db,
        tenant_id=admin.tenant_id,
        tenant_admin_id=admin.id,
        reason="tenant_admin_access_revoked",
    )
