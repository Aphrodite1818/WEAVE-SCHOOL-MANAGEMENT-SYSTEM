"""Authoritative curriculum, specialization, and elective resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
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


@dataclass(frozen=True, slots=True)
class ResolvedCurriculumOffering:
    """One curriculum subject applicable to a class/student for one term."""

    curriculum_offering_id: uuid.UUID
    curriculum_subject_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    department_id: uuid.UUID | None
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
        department_id: uuid.UUID | None,
    ) -> list[ResolvedCurriculumOffering]:
        result = await db.execute(
            select(CurriculumOffering, CurriculumSubject)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
            )
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.academic_term_id == academic_term_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.is_active.is_(True),
                Curriculum.tenant_id == tenant_id,
                Curriculum.academic_level_id == academic_level_id,
                or_(
                    CurriculumOffering.department_id.is_(None),
                    CurriculumOffering.department_id == department_id,
                ),
            )
            .order_by(CurriculumSubject.subject_id, CurriculumOffering.department_id)
        )

        # A department-specific offering takes precedence over a general offering
        # for the same curriculum subject, preventing duplicate subject cards/results.
        resolved: dict[uuid.UUID, ResolvedCurriculumOffering] = {}
        for offering, curriculum_subject in result.all():
            candidate = ResolvedCurriculumOffering(
                curriculum_offering_id=offering.id,
                curriculum_subject_id=curriculum_subject.id,
                subject_id=curriculum_subject.subject_id,
                academic_term_id=academic_term_id,
                department_id=offering.department_id,
                is_elective=curriculum_subject.is_elective,
            )
            current = resolved.get(curriculum_subject.id)
            if current is None or (
                current.department_id is None and candidate.department_id is not None
            ):
                resolved[curriculum_subject.id] = candidate
        return list(resolved.values())

    @staticmethod
    async def resolve_department_for_student(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: StudentEnrollment,
        academic_term: AcademicTerm,
    ) -> uuid.UUID | None:
        """Resolve specialization from the student's class for this exact term."""

        if enrollment.class_id is None:
            return None
        assignment = (
            await db.execute(
                select(ClassTermDepartmentAssignment).where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == enrollment.class_id,
                    ClassTermDepartmentAssignment.academic_term_id == academic_term.id,
                )
            )
        ).scalar_one_or_none()
        return assignment.department_id if assignment is not None else None

    @staticmethod
    async def resolve_student_offerings(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        """Resolve every offering the student may take, including untouched electives."""

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
            raise ConflictException(
                "Student enrollment for this academic session is required."
            )

        department_id = await CurriculumResolutionService.resolve_department_for_student(
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
            department_id=department_id,
        )

    @staticmethod
    async def resolve_student_curriculum(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        """Return report-card-required curriculum for one student and term.

        Compulsory subjects always participate. An elective is intentionally ignored
        until at least one assessment score has actually been recorded for it. As soon
        as score activity exists, the elective becomes a normal required result and
        the standard completeness/locking rules apply.
        """

        offerings = await CurriculumResolutionService.resolve_student_offerings(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        elective_ids = {
            offering.curriculum_subject_id
            for offering in offerings
            if offering.is_elective
        }
        if not elective_ids:
            return offerings

        participating = set(
            (
                await db.execute(
                    select(StudentSubjectResult.curriculum_subject_id)
                    .join(
                        StudentAssessmentScore,
                        StudentAssessmentScore.student_subject_result_id
                        == StudentSubjectResult.id,
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
            if not offering.is_elective
            or offering.curriculum_subject_id in participating
        ]
