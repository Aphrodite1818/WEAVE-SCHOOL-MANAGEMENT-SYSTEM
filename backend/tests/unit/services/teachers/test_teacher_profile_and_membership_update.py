from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestException
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherInvitation,
    TeacherInvitationStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.teachers.patch_service import TeacherPatchService
from app.modules.teachers.schemas import (
    TeacherAccountProfileUpdateRequest,
    TeacherMembershipUpdateRequest,
)
from app.modules.teachers.service import TeacherInvitationService
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


def _account() -> TeacherAccount:
    now = datetime.now(timezone.utc)
    return TeacherAccount(
        id=uuid.uuid4(),
        email="teacher@example.com",
        password_hash="hashed",
        first_name="Ada",
        last_name="Lovelace",
        phone_number="+2348012345678",
        qualification="B.Ed",
        specialization="Mathematics",
        account_status=TeacherAccountStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _membership(tenant_id: uuid.UUID, account_id: uuid.UUID) -> TeacherMembership:
    now = datetime.now(timezone.utc)
    return TeacherMembership(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        teacher_account_id=account_id,
        staff_id="TCH-001",
        job_title="Teacher",
        department="Science",
        employment_type="full_time",
        status=TeacherMembershipStatus.ACTIVE,
        joined_at=now,
        receive_email_notifications=True,
        receive_push_notifications=True,
        created_at=now,
        updated_at=now,
    )


def _invitation(tenant_id: uuid.UUID) -> TeacherInvitation:
    now = datetime.now(timezone.utc)
    return TeacherInvitation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        invited_email="teacher@example.com",
        token_digest="hashed-token",
        staff_id="TCH-002",
        status=TeacherInvitationStatus.PENDING,
        expires_at=now,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_teacher_profile_rejects_null_required_name() -> None:
    account = _account()
    db = AsyncMock()

    with patch(
        "app.modules.teachers.patch_service.TeacherAccountRepository.get_by_id",
        new=AsyncMock(return_value=account),
    ):
        with pytest.raises(BadRequestException):
            await TeacherPatchService.update_account_profile(
                db=db,
                account_id=account.id,
                payload=TeacherAccountProfileUpdateRequest(first_name=None),
            )


@pytest.mark.asyncio
async def test_teacher_profile_clears_explicit_nullable_field() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.patch_service.TeacherAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.teachers.patch_service.TeacherAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await TeacherPatchService.update_account_profile(
            db=db,
            account_id=account.id,
            payload=TeacherAccountProfileUpdateRequest(qualification=None),
        )

    assert account.qualification is None
    assert account.specialization == "Mathematics"
    assert response.qualification is None


@pytest.mark.asyncio
async def test_teacher_profile_applies_only_explicit_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.patch_service.TeacherAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.teachers.patch_service.TeacherAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await TeacherPatchService.update_account_profile(
            db=db,
            account_id=account.id,
            payload=TeacherAccountProfileUpdateRequest(specialization="Physics"),
        )

    assert account.specialization == "Physics"
    assert account.qualification == "B.Ed"
    assert response.specialization == "Physics"


@pytest.mark.asyncio
async def test_teacher_membership_rejects_null_boolean_preference() -> None:
    tenant_id = uuid.uuid4()
    account = _account()
    membership = _membership(tenant_id, account.id)
    db = AsyncMock()

    with patch(
        "app.modules.teachers.patch_service.TeacherMembershipRepository.get_by_id",
        new=AsyncMock(return_value=membership),
    ):
        with pytest.raises(BadRequestException):
            await TeacherPatchService.update_membership(
                db=db,
                actor=_admin(tenant_id),
                membership_id=membership.id,
                payload=TeacherMembershipUpdateRequest(receive_email_notifications=None),
            )


@pytest.mark.asyncio
async def test_teacher_membership_clears_nullable_employment_field() -> None:
    tenant_id = uuid.uuid4()
    account = _account()
    membership = _membership(tenant_id, account.id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.patch_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.patch_service.TeacherMembershipRepository.save",
            new=AsyncMock(return_value=membership),
        ),
    ):
        response = await TeacherPatchService.update_membership(
            db=db,
            actor=_admin(tenant_id),
            membership_id=membership.id,
            payload=TeacherMembershipUpdateRequest(department=None),
        )

    assert membership.department is None
    assert membership.job_title == "Teacher"
    assert response.department is None


@pytest.mark.asyncio
async def test_teacher_membership_applies_only_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    account = _account()
    membership = _membership(tenant_id, account.id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.patch_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.patch_service.TeacherMembershipRepository.save",
            new=AsyncMock(return_value=membership),
        ),
    ):
        response = await TeacherPatchService.update_membership(
            db=db,
            actor=_admin(tenant_id),
            membership_id=membership.id,
            payload=TeacherMembershipUpdateRequest(receive_push_notifications=False),
        )

    assert membership.receive_push_notifications is False
    assert membership.receive_email_notifications is True
    assert response.receive_push_notifications is False


@pytest.mark.asyncio
async def test_revoke_teacher_invitation_refreshes_before_response() -> None:
    tenant_id = uuid.uuid4()
    invitation = _invitation(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.service.TeacherInvitationRepository.get_by_id",
            new=AsyncMock(return_value=invitation),
        ),
        patch(
            "app.modules.teachers.service.TeacherInvitationRepository.save",
            new=AsyncMock(return_value=invitation),
        ),
    ):
        response = await TeacherInvitationService.revoke_invitation(
            db=db,
            actor=_admin(tenant_id),
            invitation_id=invitation.id,
        )

    assert invitation.status == TeacherInvitationStatus.REVOKED
    assert invitation.revoked_at is not None
    assert response.status == TeacherInvitationStatus.REVOKED.value
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(invitation)
