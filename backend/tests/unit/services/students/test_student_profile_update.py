from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException
from app.modules.students.admin_contracts import StudentAdminContractService
from app.modules.students.models import (
    AcademicStatus,
    Gender,
    Student,
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.modules.students.schemas import StudentAdminProfileUpdate, StudentSelfUpdate
from app.modules.students.service import StudentService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _student(tenant_id: uuid.UUID) -> Student:
    now = datetime.now(timezone.utc)
    return Student(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        admission_number="STD/2026/0001",
        password_hash="hashed",
        first_name="Ada",
        last_name="Lovelace",
        account_status=StudentAccountStatus.ACTIVE,
        is_verified=True,
        is_active=True,
        password_reset_required=False,
        date_of_birth=date(2012, 5, 1),
        gender=Gender.FEMALE,
        admission_date=date(2026, 1, 10),
        status=AcademicStatus.ACTIVE,
        promotion_hold=False,
        profile_status=StudentProfileStatus.COMPLETE,
        state_of_origin="Lagos",
        is_archived=False,
        created_at=now,
        updated_at=now,
    )


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


@pytest.mark.asyncio
async def test_admin_student_profile_rejects_null_required_field() -> None:
    tenant_id = uuid.uuid4()
    student = _student(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.students.admin_contracts.StudentRepository.get_by_id",
        new=AsyncMock(return_value=student),
    ):
        with pytest.raises(BadRequestException):
            await StudentAdminContractService.update_profile(
                db=db,
                actor=_admin(tenant_id),
                student_id=student.id,
                payload=StudentAdminProfileUpdate(first_name=None),
            )


@pytest.mark.asyncio
async def test_admin_student_profile_can_clear_nullable_field() -> None:
    tenant_id = uuid.uuid4()
    student = _student(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.admin_contracts.StudentRepository.get_by_id",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.admin_contracts.StudentService._build_detail_response",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.admin_contracts.StudentRepository.save",
            new=AsyncMock(return_value=student),
        ),
    ):
        response = await StudentAdminContractService.update_profile(
            db=db,
            actor=_admin(tenant_id),
            student_id=student.id,
            payload=StudentAdminProfileUpdate(state_of_origin=None),
        )

    assert student.state_of_origin is None
    assert response.state_of_origin is None


@pytest.mark.asyncio
async def test_admin_student_profile_applies_explicit_value() -> None:
    tenant_id = uuid.uuid4()
    student = _student(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.admin_contracts.StudentRepository.get_by_id",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.admin_contracts.StudentService._build_detail_response",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.admin_contracts.StudentRepository.save",
            new=AsyncMock(return_value=student),
        ),
    ):
        response = await StudentAdminContractService.update_profile(
            db=db,
            actor=_admin(tenant_id),
            student_id=student.id,
            payload=StudentAdminProfileUpdate(first_name="Grace"),
        )

    assert student.first_name == "Grace"
    assert response.first_name == "Grace"


def test_student_self_update_rejects_explicit_nulls() -> None:
    with pytest.raises(ValidationError):
        StudentSelfUpdate(first_name=None, gender=None)


@pytest.mark.asyncio
async def test_student_self_update_applies_only_supplied_fields() -> None:
    tenant_id = uuid.uuid4()
    student = _student(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.service.StudentRepository.get_by_id",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.service.StudentService._build_detail_response",
            new=AsyncMock(return_value=student),
        ),
        patch(
            "app.modules.students.service.StudentRepository.save",
            new=AsyncMock(return_value=student),
        ),
    ):
        await StudentService.update_my_student_profile(
            db=db,
            actor=student,
            payload=StudentSelfUpdate(first_name="Grace"),
        )

    assert student.first_name == "Grace"
    assert student.last_name == "Lovelace"
    assert student.gender == Gender.FEMALE
