"""Read-only current academic context for the student dashboard."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_onboarded_student
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.models import AcademicSession, AcademicTerm
from app.modules.students.models import Student, StudentEnrollment
from app.modules.students.repository import StudentEnrollmentRepository


class StudentAcademicContextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: uuid.UUID
    student_enrollment_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID | None = None
    academic_session_name: str | None = None
    academic_term_id: uuid.UUID | None = None
    academic_term_name: str | None = None
    academic_level_id: uuid.UUID | None = None
    academic_level_name: str | None = None
    class_id: uuid.UUID | None = None
    class_name: str | None = None
    class_arm: str | None = None
    academic_level_department_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    department_name: str | None = None


router = APIRouter(prefix="/students/me/academic-context", tags=["Student Academic Context"])


@router.get("", response_model=StudentAcademicContextResponse)
async def get_current_student_academic_context(
    db: DbSession,
    current_student: Student = Depends(get_current_onboarded_student),
) -> StudentAcademicContextResponse:
    tenant_id = current_student.tenant_id
    enrollment = await StudentEnrollmentRepository.get_current(
        db,
        tenant_id,
        current_student.id,
    )
    if enrollment is None:
        return StudentAcademicContextResponse(student_id=current_student.id)

    session = (
        await db.execute(
            select(AcademicSession).where(
                AcademicSession.tenant_id == tenant_id,
                AcademicSession.id == enrollment.academic_session_id,
            )
        )
    ).scalar_one_or_none()
    term = (
        await db.execute(
            select(AcademicTerm).where(
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.academic_session_id == enrollment.academic_session_id,
                AcademicTerm.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    level = (
        await db.execute(
            select(AcademicLevel).where(
                AcademicLevel.tenant_id == tenant_id,
                AcademicLevel.id == enrollment.academic_level_id,
            )
        )
    ).scalar_one_or_none()

    classroom = None
    arm = None
    level_department = None
    department = None
    if enrollment.class_id is not None:
        classroom = (
            await db.execute(
                select(ClassRoom).where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.id == enrollment.class_id,
                )
            )
        ).scalar_one_or_none()
        if classroom is not None:
            arm = (
                await db.execute(
                    select(ArmLabel).where(
                        ArmLabel.tenant_id == tenant_id,
                        ArmLabel.id == classroom.arm_label_id,
                    )
                )
            ).scalar_one_or_none()

    if classroom is not None and term is not None:
        assignment = (
            await db.execute(
                select(ClassTermDepartmentAssignment).where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == classroom.id,
                    ClassTermDepartmentAssignment.academic_term_id == term.id,
                )
            )
        ).scalar_one_or_none()
        if assignment is not None:
            row = (
                await db.execute(
                    select(AcademicLevelDepartment, Department)
                    .join(
                        Department,
                        and_(
                            Department.id == AcademicLevelDepartment.department_id,
                            Department.tenant_id == tenant_id,
                        ),
                    )
                    .where(
                        AcademicLevelDepartment.tenant_id == tenant_id,
                        AcademicLevelDepartment.id == assignment.academic_level_department_id,
                        AcademicLevelDepartment.academic_level_id == enrollment.academic_level_id,
                    )
                )
            ).first()
            if row is not None:
                level_department, department = row

    return StudentAcademicContextResponse(
        student_id=current_student.id,
        student_enrollment_id=enrollment.id,
        academic_session_id=enrollment.academic_session_id,
        academic_session_name=session.name if session else None,
        academic_term_id=term.id if term else None,
        academic_term_name=(getattr(term.name, "value", term.name) if term else None),
        academic_level_id=enrollment.academic_level_id,
        academic_level_name=level.name if level else None,
        class_id=enrollment.class_id,
        class_name=level.name if classroom is not None and level is not None else None,
        class_arm=arm.label if arm is not None else None,
        academic_level_department_id=level_department.id if level_department else None,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
    )
