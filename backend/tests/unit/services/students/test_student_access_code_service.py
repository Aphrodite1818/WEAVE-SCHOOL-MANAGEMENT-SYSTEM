"""Student access-code service regression coverage."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.students.models import (
    AcademicStatus,
    StudentAccessCodePurpose,
)
from app.modules.students.schemas import StudentAdminAccessCodeResponse
from app.modules.students.service import StudentAccessCodeService


@pytest.mark.asyncio
async def test_admin_password_reset_invalidates_existing_student_password(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="WVS-2026-0004",
        first_name="Ada",
        last_name="Student",
        password_hash="existing-hash",
        password_reset_required=False,
        status=AcademicStatus.ACTIVE,
        is_archived=False,
    )
    admin = SimpleNamespace(id=admin_id, tenant_id=tenant_id)
    response = StudentAdminAccessCodeResponse(
        student_id=student_id,
        admission_number=student.admission_number,
        full_name="Ada Student",
        purpose=StudentAccessCodePurpose.PASSWORD_RESET,
        access_code="12345678",
        expires_at=datetime.now(timezone.utc),
    )
    db = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
    )

    monkeypatch.setattr(
        "app.modules.students.service.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.students.service.StudentAccessCodeService._create_code",
        AsyncMock(return_value=response),
    )
    save_student = AsyncMock(return_value=student)
    monkeypatch.setattr(
        "app.modules.students.service.StudentRepository.save",
        save_student,
    )

    result = await StudentAccessCodeService.generate_for_admin(
        db,
        actor=admin,
        student_id=student_id,
        purpose=StudentAccessCodePurpose.PASSWORD_RESET,
    )

    assert result is response
    assert student.password_hash is None
    assert student.password_reset_required is True
    db.execute.assert_awaited_once()
    save_student.assert_awaited_once_with(db, student)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_initial_setup_code_does_not_clear_existing_password(
    monkeypatch,
) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        admission_number="WVS-2026-0005",
        first_name="Ada",
        last_name="Student",
        password_hash="existing-hash",
        password_reset_required=False,
        status=AcademicStatus.ACTIVE,
        is_archived=False,
    )
    admin = SimpleNamespace(id=admin_id, tenant_id=tenant_id)
    response = StudentAdminAccessCodeResponse(
        student_id=student_id,
        admission_number=student.admission_number,
        full_name="Ada Student",
        purpose=StudentAccessCodePurpose.INITIAL_SETUP,
        access_code="12345678",
        expires_at=datetime.now(timezone.utc),
    )
    db = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
    )

    monkeypatch.setattr(
        "app.modules.students.service.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.students.service.StudentAccessCodeService._create_code",
        AsyncMock(return_value=response),
    )
    monkeypatch.setattr(
        "app.modules.students.service.StudentRepository.save",
        AsyncMock(return_value=student),
    )

    await StudentAccessCodeService.generate_for_admin(
        db,
        actor=admin,
        student_id=student_id,
        purpose=StudentAccessCodePurpose.INITIAL_SETUP,
    )

    assert student.password_hash == "existing-hash"
    assert student.password_reset_required is True
    db.execute.assert_not_awaited()
