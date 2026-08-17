"""Stable CBT projection for currently eligible student enrollments."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import CBTStudentEnrollmentSnapshot
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def project_student_enrollment(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(StudentEnrollment, Student)
        .join(Student, Student.id == StudentEnrollment.student_id)
        .where(
            StudentEnrollment.tenant_id == tenant_id,
            StudentEnrollment.id == entity_id,
        )
    ).first()
    if row is None:
        return None
    enrollment, student = row
    if (
        not enrollment.is_current
        or student.status != AcademicStatus.ACTIVE
        or student.is_archived
    ):
        return None
    return CBTStudentEnrollmentSnapshot(
        id=enrollment.id,
        student_id=student.id,
        admission_number=student.admission_number,
        first_name=student.first_name,
        last_name=student.last_name,
        academic_level_id=enrollment.academic_level_id,
        class_id=enrollment.class_id,
        academic_session_id=enrollment.academic_session_id,
        is_current=enrollment.is_current,
        student_status=_value(student.status),
    ).model_dump(mode="json")
