from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.modules.student_academics.models import AcademicSession, AcademicSessionStatus
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentProfileStatus,
)
from app.modules.students.schemas import (
    StudentAdminProfileUpdate,
    StudentEnrollmentDetailResponse,
)
from app.modules.students.service import StudentEnrollmentService


def _student(tenant_id: uuid.UUID, class_id: uuid.UUID) -> Student:
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
        admission_date=date(2026, 1, 10),
        status=AcademicStatus.ACTIVE,
        profile_status=StudentProfileStatus.COMPLETE,
        class_id=class_id,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )


def test_admin_profile_update_rejects_class_fields() -> None:
    with pytest.raises(ValidationError):
        StudentAdminProfileUpdate(class_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_enrollment_history_adds_display_labels_once() -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    class_id = uuid.uuid4()
    level_id = uuid.uuid4()
    session_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    enrollment = StudentEnrollment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        student_id=student_id,
        academic_level_id=level_id,
        class_id=class_id,
        academic_session_id=session_id,
        started_on=date(2026, 9, 1),
        is_current=True,
        outcome=StudentEnrollmentOutcome.ENROLLED,
        created_at=now,
        updated_at=now,
    )
    classroom = type("Classroom", (), {"academic_level_name": "JSS 1", "arm": "Blue"})()
    level = type("Level", (), {"name": "JSS 1"})()
    session = AcademicSession(
        id=session_id,
        tenant_id=tenant_id,
        name="2026/2027",
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )

    with (
        patch(
            "app.modules.students.service.StudentRepository.get_by_id",
            new=AsyncMock(return_value=_student(tenant_id, class_id)),
        ),
        patch(
            "app.modules.students.service.StudentEnrollmentRepository.list_for_student",
            new=AsyncMock(return_value=[enrollment]),
        ),
        patch(
            "app.modules.students.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.students.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.students.service.AcademicSessionLifecycleRepository.get_by_id",
            new=AsyncMock(return_value=session),
        ),
    ):
        rows = await StudentEnrollmentService.list_history(
            AsyncMock(),
            tenant_id=tenant_id,
            student_id=student_id,
        )

    assert rows == [
        StudentEnrollmentDetailResponse(
            **StudentEnrollmentDetailResponse.model_validate(enrollment).model_dump(
                exclude={"class_name", "class_arm", "academic_level_name", "academic_session_name"}
            ),
            class_name="JSS 1",
            class_arm="Blue",
            academic_level_name="JSS 1",
            academic_session_name="2026/2027",
        )
    ]
