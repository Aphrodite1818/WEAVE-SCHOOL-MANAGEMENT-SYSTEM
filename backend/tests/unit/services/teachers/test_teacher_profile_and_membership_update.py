from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.teachers.schemas import (
    TeacherAccountProfileUpdateRequest,
    TeacherMembershipUpdateRequest,
)
from app.modules.teachers.service import TeacherAccountService, TeacherMembershipService
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


@pytest.mark.asyncio
async def test_update_teacher_profile_ignores_explicit_null_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.service.TeacherAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.teachers.service.TeacherAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await TeacherAccountService.update_profile(
            db=db,
            account_id=account.id,
            payload=TeacherAccountProfileUpdateRequest(
                first_name=None,
                last_name=None,
                qualification=None,
            ),
        )

    assert account.first_name == "Ada"
    assert account.last_name == "Lovelace"
    assert account.qualification == "B.Ed"
    assert response.first_name == "Ada"


@pytest.mark.asyncio
async def test_update_teacher_profile_applies_explicit_values() -> None:
    account = _account()
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.service.TeacherAccountRepository.get_by_id",
            new=AsyncMock(return_value=account),
        ),
        patch(
            "app.modules.teachers.service.TeacherAccountRepository.save",
            new=AsyncMock(return_value=account),
        ),
    ):
        response = await TeacherAccountService.update_profile(
            db=db,
            account_id=account.id,
            payload=TeacherAccountProfileUpdateRequest(specialization="Physics"),
        )

    assert account.specialization == "Physics"
    assert response.specialization == "Physics"


@pytest.mark.asyncio
async def test_update_teacher_membership_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    account = _account()
    membership = _membership(tenant_id, account.id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.service.TeacherMembershipRepository.save",
            new=AsyncMock(return_value=membership),
        ),
    ):
        response = await TeacherMembershipService.update_membership(
            db=db,
            actor=_admin(tenant_id),
            membership_id=membership.id,
            payload=TeacherMembershipUpdateRequest(
                job_title=None,
                department=None,
                receive_email_notifications=None,
            ),
        )

    assert membership.job_title == "Teacher"
    assert membership.department == "Science"
    assert membership.receive_email_notifications is True
    assert response.job_title == "Teacher"


@pytest.mark.asyncio
async def test_update_teacher_membership_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    account = _account()
    membership = _membership(tenant_id, account.id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.teachers.service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.service.TeacherMembershipRepository.save",
            new=AsyncMock(return_value=membership),
        ),
    ):
        response = await TeacherMembershipService.update_membership(
            db=db,
            actor=_admin(tenant_id),
            membership_id=membership.id,
            payload=TeacherMembershipUpdateRequest(receive_push_notifications=False),
        )

    assert membership.receive_push_notifications is False
    assert response.receive_push_notifications is False
