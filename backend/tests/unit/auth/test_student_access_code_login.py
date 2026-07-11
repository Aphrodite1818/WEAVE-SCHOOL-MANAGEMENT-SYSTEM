"""Regression coverage for student password/access-code authentication."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.auth.student_authentication import authenticate_student_actor
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.schemas import IdentityResolution
from app.modules.students.models import (
    StudentAccountStatus,
    StudentProfileStatus,
)


@pytest.mark.asyncio
async def test_access_code_login_returns_forced_reset_actor(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="NHS-2026-0001",
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
    )
    tenant = SimpleNamespace(
        id=tenant_id,
        school_name="Test School",
        logo_url=None,
    )
    db = SimpleNamespace(flush=AsyncMock())

    monkeypatch.setattr(
        "app.modules.auth.student_authentication.AuthIdentityService.resolve_identifier",
        AsyncMock(
            return_value=IdentityResolution(
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                tenant_id=tenant_id,
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.TenantRepository.get_by_id",
        AsyncMock(return_value=tenant),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication._tenant_allows_login",
        lambda value: value is tenant,
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication.StudentAccessCodeRepository.get_active_code_by_digest",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
    )
    monkeypatch.setattr(
        "app.modules.auth.student_authentication._update_last_login_if_due",
        AsyncMock(return_value=True),
    )

    actor = await authenticate_student_actor(
        db,
        admission_number=" nhs-2026-0001 ",
        credential="12345678",
    )

    assert actor.actor_type == "student"
    assert actor.email == "NHS-2026-0001"
    assert actor.password_reset_required is True
    assert actor.user is not None
    assert actor.user.admission_number == "NHS-2026-0001"
    assert actor.user.password_reset_required is True
