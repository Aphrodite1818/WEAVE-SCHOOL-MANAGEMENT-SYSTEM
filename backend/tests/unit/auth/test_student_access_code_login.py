"""Regression coverage for student password/access-code authentication."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config.security import hash_password
from app.core.exceptions import UnauthorizedException
from app.modules.auth.student_authentication import authenticate_student_actor
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.schemas import IdentityResolution
from app.modules.students.models import (
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.tenant_management.models import TenantStatus, TenantVerificationStatus


@pytest.mark.asyncio
async def test_access_code_login_returns_forced_reset_actor(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="WVS-2026-0001",
        password_hash=None,
        first_name="Taiwo",
        last_name="Ayimora",
        is_active=True,
        is_verified=True,
        account_status=StudentAccountStatus.ACTIVE,
        password_reset_required=True,
        last_login_at=None,
        profile_status=StudentProfileStatus.COMPLETE,
        passport_photo_url=None,
        is_archived=False,
    )
    tenant = SimpleNamespace(
        id=tenant_id,
        school_name="Test School",
        logo_url=None,
        is_deleted=False,
        verification_status=TenantVerificationStatus.ACTIVE,
        status=TenantStatus.ACTIVE,
    )
    db = SimpleNamespace(add=lambda _value: None, flush=AsyncMock())

    monkeypatch.setattr(
        "app.modules.auth.student_authentication.AuthIdentityService.resolve_identifier",
        AsyncMock(
            return_value=IdentityResolution(
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                tenant_id=tenant_id,
                lookup_table="students",
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.TenantRepository.get_by_id",
        AsyncMock(return_value=tenant),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentAccessCodeRepository.get_active_code_by_digest",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
    )

    actor = await authenticate_student_actor(
        db,
        admission_number=" wvs-2026-0001 ",
        credential="12345678",
    )

    assert actor.actor_type == "student"
    assert actor.email == "WVS-2026-0001"
    assert actor.password_reset_required is True
    assert actor.user is not None
    assert actor.user.admission_number == "WVS-2026-0001"
    assert actor.user.password_reset_required is True


@pytest.mark.asyncio
async def test_old_password_is_rejected_after_admin_password_reset(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="WVS-2026-0002",
        password_hash=None,
        first_name="Ada",
        last_name="Student",
        is_active=True,
        is_verified=True,
        account_status=StudentAccountStatus.ACTIVE,
        password_reset_required=True,
        last_login_at=None,
        profile_status=StudentProfileStatus.COMPLETE,
        passport_photo_url=None,
        is_archived=False,
    )
    tenant = SimpleNamespace(
        id=tenant_id,
        school_name="Test School",
        logo_url=None,
        is_deleted=False,
        verification_status=TenantVerificationStatus.ACTIVE,
        status=TenantStatus.ACTIVE,
    )
    db = SimpleNamespace(add=lambda _value: None, flush=AsyncMock())

    monkeypatch.setattr(
        "app.modules.auth.student_authentication.AuthIdentityService.resolve_identifier",
        AsyncMock(
            return_value=IdentityResolution(
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                tenant_id=tenant_id,
                lookup_table="students",
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.TenantRepository.get_by_id",
        AsyncMock(return_value=tenant),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentAccessCodeRepository.get_active_code_by_digest",
        AsyncMock(return_value=None),
    )

    with pytest.raises(UnauthorizedException):
        await authenticate_student_actor(
            db,
            admission_number="WVS-2026-0002",
            credential="OldPass123",
        )


@pytest.mark.asyncio
async def test_existing_password_login_still_works_without_admin_reset(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="WVS-2026-0003",
        password_hash=hash_password("CurrentPass123"),
        first_name="Ada",
        last_name="Student",
        is_active=True,
        is_verified=True,
        account_status=StudentAccountStatus.ACTIVE,
        password_reset_required=False,
        last_login_at=None,
        profile_status=StudentProfileStatus.COMPLETE,
        passport_photo_url=None,
        is_archived=False,
    )
    tenant = SimpleNamespace(
        id=tenant_id,
        school_name="Test School",
        logo_url=None,
        is_deleted=False,
        verification_status=TenantVerificationStatus.ACTIVE,
        status=TenantStatus.ACTIVE,
    )
    db = SimpleNamespace(add=lambda _value: None, flush=AsyncMock())

    monkeypatch.setattr(
        "app.modules.auth.student_authentication.AuthIdentityService.resolve_identifier",
        AsyncMock(
            return_value=IdentityResolution(
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                tenant_id=tenant_id,
                lookup_table="students",
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.TenantRepository.get_by_id",
        AsyncMock(return_value=tenant),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    get_code = AsyncMock()
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentAccessCodeRepository.get_active_code_by_digest",
        get_code,
    )

    actor = await authenticate_student_actor(
        db,
        admission_number="WVS-2026-0003",
        credential="CurrentPass123",
    )

    assert actor.password_reset_required is False
    get_code.assert_not_awaited()
