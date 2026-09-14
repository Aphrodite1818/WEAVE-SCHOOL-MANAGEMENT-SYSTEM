from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.modules.students.placement_service import StudentPlacementService
from app.modules.students.repository import StudentRepository
from app.modules.students.schemas import (
    StudentAdminProfileUpdate,
    StudentEnrollmentDetailResponse,
)


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
        admission_date=date(2026, 1, 10),
        status=AcademicStatus.ACTIVE,
        profile_status=StudentProfileStatus.COMPLETE,
        is_archived=False,
        created_at=now,
        updated_at=now,
    )


def test_admin_profile_update_rejects_class_fields() -> None:
    with pytest.raises(ValidationError):
        StudentAdminProfileUpdate(class_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_placement_history_returns_canonical_segment_with_display_labels() -> None:
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
        entry_outcome=StudentEnrollmentOutcome.ENROLLED,
        entry_reason="Initial admission",
        created_at=now,
        updated_at=now,
    )
    classroom = type("Classroom", (), {"id": class_id})()
    level = type("Level", (), {"name": "JSS 1"})()
    session = AcademicSession(
        id=session_id,
        tenant_id=tenant_id,
        name="2026/2027",
        status=AcademicSessionStatus.OPEN,
        is_current=True,
    )
    arm = type("Arm", (), {"label": "Blue"})()
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(enrollment, classroom, level, session, arm)]
    db.execute.return_value = result

    with patch.object(
        StudentRepository,
        "get_by_id",
        new=AsyncMock(return_value=_student(tenant_id)),
    ):
        rows = await StudentPlacementService.list_history(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
        )

    assert rows == [
        StudentEnrollmentDetailResponse(
            id=enrollment.id,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_level_id=level_id,
            class_id=class_id,
            academic_session_id=session_id,
            started_on=date(2026, 9, 1),
            ended_on=None,
            entry_outcome=StudentEnrollmentOutcome.ENROLLED,
            exit_outcome=None,
            entry_reason="Initial admission",
            exit_reason=None,
            created_by_admin_id=None,
            ended_by_admin_id=None,
            created_at=now,
            updated_at=now,
            class_name="JSS 1",
            class_arm="Blue",
            academic_level_name="JSS 1",
            academic_session_name="2026/2027",
            lifecycle_state="current",
        )
    ]
