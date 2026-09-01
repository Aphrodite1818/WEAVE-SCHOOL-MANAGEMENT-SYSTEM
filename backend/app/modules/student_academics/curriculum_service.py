"""Authoritative curriculum, specialization, and elective resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    AcademicLevelStatus,
    Department,
)
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.models import (
    AcademicTerm,
    StudentAssessmentScore,
    StudentSubjectResult,
)
from app.modules.students.models import StudentEnrollment
from app.modules.students.repository import StudentEnrollmentRepository
from app.modules.subjects.models import Subject


@dataclass(frozen=True, slots=True)
class ResolvedCurriculumOffering:
    """One curriculum subject applicable to a class/student for one term."""

    curriculum_offering_id: uuid.UUID
    curriculum_subject_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    academic_level_department_id: uuid.UUID | None
    is_elective: bool


class CurriculumResolutionService:
    """Single source of truth for term curriculum applicability and participation."""

    @staticmethod
    async def resolve_curriculum_offerings(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        academic_term_id: uuid.UUID,
        academic_level_department_id: uuid.UUID | None,
    ) -> list[ResolvedCurriculumOffering]:
        result = await db.execute(
            select(CurriculumOffering, CurriculumSubject)
            .join(CurriculumSubject, CurriculumSubject.id == CurriculumOffering.curriculum_subject_id)
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
            .join(Subject, Subject.id == CurriculumSubject.subject_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.academic_term_id == academic_term_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.is_active.is_(True),
                Curriculum.tenant_id == tenant_id,
                Curriculum.academic_level_id == academic_level_id,
                AcademicLevel.tenant_id == tenant_id,
                AcademicLevel.status == AcademicLevelStatus.ACTIVE,
                Subject.tenant_id == tenant_id,
                Subject.is_active.is_(True),
                Subject.archived_at.is_(None),
                or_(
                    CurriculumOffering.academic_level_department_id.is_(None),
                    CurriculumOffering.academic_level_department_id == academic_level_department_id,
                ),
            )
            .order_by(
                CurriculumSubject.subject_id,
                CurriculumOffering.academic_level_department_id,
            )
        )

        resolved: dict[uuid.UUID, ResolvedCurriculumOffering] = {}
        for offering, curriculum_subject in result.all():
            if curriculum_subject.id in resolved:
                raise ConflictException(
                    "Curriculum offering scope is ambiguous for this term. "
                    "Use either a general offering or level-department offerings, not both."
                )
            resolved[curriculum_subject.id] = ResolvedCurriculumOffering(
                curriculum_offering_id=offering.id,
                curriculum_subject_id=curriculum_subject.id,
                subject_id=curriculum_subject.subject_id,
                academic_term_id=academic_term_id,
                academic_level_department_id=offering.academic_level_department_id,
                is_elective=curriculum_subject.is_elective,
            )
        return list(resolved.values())

    @staticmethod
    async def resolve_level_department_for_student(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: StudentEnrollment,
        academic_term: AcademicTerm,
    ) -> uuid.UUID | None:
        """Resolve specialization from the student's class for this exact term."""

        if enrollment.class_id is None:
            return None
        row = (
            await db.execute(
                select(
                    ClassTermDepartmentAssignment,
                    AcademicLevelDepartment,
                    Department,
                )
                .join(
                    AcademicLevelDepartment,
                    AcademicLevelDepartment.id
                    == ClassTermDepartmentAssignment.academic_level_department_id,
                )
                .join(Department, Department.id == AcademicLevelDepartment.department_id)
                .where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == enrollment.class_id,
                    ClassTermDepartmentAssignment.academic_term_id == academic_term.id,
                    AcademicLevelDepartment.tenant_id == tenant_id,
                    Department.tenant_id == tenant_id,
                )
            )
        ).first()
        if row is None:
            return None
        _assignment, link, department = row
        if link.academic_level_id != enrollment.academic_level_id:
            raise ConflictException("Class specialization does not belong to the student's academic level.")
        if (
            not link.is_active
            or link.archived_at is not None
            or not department.is_active
            or department.archived_at is not None
        ):
            raise ConflictException("Class specialization is no longer active for this academic level.")
        return link.id

    @staticmethod
    async def resolve_student_offerings(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.id == academic_term_id,
                )
            )
        ).scalar_one_or_none()
        if term is None:
            raise NotFoundException("Academic term not found.")

        enrollment = await StudentEnrollmentRepository.get_authoritative_for_session(
            db,
            tenant_id,
            student_id,
            term.academic_session_id,
        )
        if enrollment is None:
            raise ConflictException("Student enrollment for this academic session is required.")

        link_id = await CurriculumResolutionService.resolve_level_department_for_student(
            db,
            tenant_id=tenant_id,
            enrollment=enrollment,
            academic_term=term,
        )
        return await CurriculumResolutionService.resolve_curriculum_offerings(
            db,
            tenant_id=tenant_id,
            academic_level_id=enrollment.academic_level_id,
            academic_term_id=term.id,
            academic_level_department_id=link_id,
        )

    @staticmethod
    async def resolve_student_curriculum(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        """Return report-card-required curriculum for one student and term."""

        offerings = await CurriculumResolutionService.resolve_student_offerings(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        elective_ids = {
            offering.curriculum_subject_id for offering in offerings if offering.is_elective
        }
        if not elective_ids:
            return offerings

        participating = set(
            (
                await db.execute(
                    select(StudentSubjectResult.curriculum_subject_id)
                    .join(
                        StudentAssessmentScore,
                        StudentAssessmentScore.student_subject_result_id == StudentSubjectResult.id,
                    )
                    .where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.student_id == student_id,
                        StudentSubjectResult.academic_term_id == academic_term_id,
                        StudentSubjectResult.curriculum_subject_id.in_(elective_ids),
                        StudentAssessmentScore.score.is_not(None),
                    )
                    .distinct()
                )
            ).scalars()
        )
        return [
            offering
            for offering in offerings
            if not offering.is_elective or offering.curriculum_subject_id in participating
        ]
