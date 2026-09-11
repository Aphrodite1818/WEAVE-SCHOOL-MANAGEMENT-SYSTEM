from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.students.models import AcademicStatus


@pytest.mark.asyncio
async def test_terminal_student_identity_is_not_reactivated_before_return_is_due() -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    identity = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier="STU-001",
        identifier_type=IdentifierType.ADMISSION_NUMBER,
        actor_type=ActorType.STUDENT,
        actor_id=student_id,
        is_active=False,
    )
    student = SimpleNamespace(status=AcademicStatus.GRADUATED)
    db = AsyncMock()

    with (
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_by_actor",
            new=AsyncMock(return_value=identity),
        ),
        patch(
            "app.modules.students.repository.StudentRepository.get_by_id",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.save",
            new=AsyncMock(),
        ) as save_identity,
        patch(
            "app.modules.auth_identity.service.AuthIdentityResponse.model_validate",
            return_value=object(),
        ),
    ):
        await AuthIdentityService.ensure_for_actor(
            db,
            tenant_id=tenant_id,
            payload=AuthIdentityCreate(
                identifier="STU-001",
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                is_active=True,
            ),
        )

    assert identity.is_active is False
    save_identity.assert_not_awaited()


@pytest.mark.asyncio
async def test_active_student_identity_can_be_reactivated_when_return_is_effective() -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    identity = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        identifier="STU-001",
        identifier_type=IdentifierType.ADMISSION_NUMBER,
        actor_type=ActorType.STUDENT,
        actor_id=student_id,
        is_active=False,
    )
    student = SimpleNamespace(status=AcademicStatus.ACTIVE)
    db = AsyncMock()

    with (
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.get_by_actor",
            new=AsyncMock(return_value=identity),
        ),
        patch(
            "app.modules.students.repository.StudentRepository.get_by_id",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.auth_identity.service.AuthIdentityRepository.save",
            new=AsyncMock(return_value=identity),
        ) as save_identity,
        patch(
            "app.modules.auth_identity.service.AuthIdentityResponse.model_validate",
            return_value=object(),
        ),
    ):
        await AuthIdentityService.ensure_for_actor(
            db,
            tenant_id=tenant_id,
            payload=AuthIdentityCreate(
                identifier="STU-001",
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=student_id,
                is_active=True,
            ),
        )

    assert identity.is_active is True
    save_identity.assert_awaited_once_with(db, identity)
