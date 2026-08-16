"""Authoritative term, department, and elective curriculum resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.repository import DepartmentRepository
from app.modules.student_academics.models import (
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
    LevelSubject,
    StudentAssessmentScore,
    StudentDepartmentAssignment,
    StudentSubjectResult,
    SubjectOffering,
)
from app.modules.students.models import StudentEnrollment
from app.modules.student_academics.schemas import (
    StudentDepartmentAssignmentCreate,
    StudentDepartmentAssignmentResponse,
    SubjectOfferingCreate,
    SubjectOfferingResponse,
)
from app.modules.students.repository import StudentEnrollmentRepository


TERM_POSITION = {
    AcademicTermName.FIRST_TERM: 1,
    AcademicTermName.SECOND_TERM: 2,
    AcademicTermName.THIRD_TERM: 3,
}


@dataclass(frozen=True)
class ResolvedCurriculumOffering:
    level_subject_id: uuid.UUID
    subject_id: uuid.UUID
    academic_term_id: uuid.UUID
    department_id: uuid.UUID | None
    is_elective: bool


class CurriculumResolutionService:
    """Single source of truth for subject applicability and participation."""

    @staticmethod
    def _ensure_term_can_change(term: AcademicTerm) -> None:
        if term.status in {AcademicTermStatus.CLOSED, AcademicTermStatus.CLOSING}:
            raise ConflictException("Closed academic term curriculum cannot be changed.")

    @staticmethod
    async def create_subject_offering(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        level_subject_id: uuid.UUID,
        payload: SubjectOfferingCreate,
    ) -> SubjectOfferingResponse:
        level_subject = (
            await db.execute(
                select(LevelSubject).where(
                    LevelSubject.tenant_id == tenant_id,
                    LevelSubject.id == level_subject_id,
                    LevelSubject.is_active.is_(True),
                    LevelSubject.archived_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if level_subject is None:
            raise NotFoundException("Level subject not found.")
        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.id == payload.academic_term_id,
                )
            )
        ).scalar_one_or_none()
        if term is None:
            raise NotFoundException("Academic term not found.")
        CurriculumResolutionService._ensure_term_can_change(term)
        if payload.department_id is not None:
            department = await DepartmentRepository.get_by_id(db, tenant_id, payload.department_id)
            if department is None or not department.is_active or department.archived_at:
                raise NotFoundException("Department not found or inactive.")
        existing = (
            await db.execute(
                select(SubjectOffering).where(
                    SubjectOffering.tenant_id == tenant_id,
                    SubjectOffering.level_subject_id == level_subject_id,
                    SubjectOffering.academic_term_id == term.id,
                    SubjectOffering.department_id == payload.department_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictException("This curriculum offering already exists.")
        offering = SubjectOffering(
            tenant_id=tenant_id,
            level_subject_id=level_subject_id,
            academic_term_id=term.id,
            department_id=payload.department_id,
            is_elective=payload.is_elective,
        )
        try:
            db.add(offering)
            await db.commit()
            await db.refresh(offering)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("This curriculum offering already exists.") from exc
        return SubjectOfferingResponse.model_validate(offering)

    @staticmethod
    async def list_subject_offerings(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        level_subject_id: uuid.UUID,
    ) -> list[SubjectOfferingResponse]:
        rows = list(
            (
                await db.execute(
                    select(SubjectOffering)
                    .where(
                        SubjectOffering.tenant_id == tenant_id,
                        SubjectOffering.level_subject_id == level_subject_id,
                    )
                    .order_by(SubjectOffering.created_at.asc())
                )
            ).scalars()
        )
        return [SubjectOfferingResponse.model_validate(row) for row in rows]

    @staticmethod
    async def assign_student_department(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        admin_id: uuid.UUID,
        payload: StudentDepartmentAssignmentCreate,
    ) -> StudentDepartmentAssignmentResponse:
        enrollment = (
            await db.execute(
                select(StudentEnrollment).where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.id == payload.student_enrollment_id,
                )
            )
        ).scalar_one_or_none()
        if enrollment is None:
            raise NotFoundException("Student enrollment not found.")
        department = await DepartmentRepository.get_by_id(db, tenant_id, payload.department_id)
        if department is None or not department.is_active or department.archived_at:
            raise NotFoundException("Department not found or inactive.")
        term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.id == payload.effective_from_term_id,
                )
            )
        ).scalar_one_or_none()
        if term is None or term.academic_session_id != enrollment.academic_session_id:
            raise ConflictException(
                "Effective term must belong to the enrollment's academic session."
            )
        CurriculumResolutionService._ensure_term_can_change(term)
        assignment = StudentDepartmentAssignment(
            tenant_id=tenant_id,
            student_enrollment_id=enrollment.id,
            department_id=department.id,
            effective_from_term_id=term.id,
            assigned_by_admin_id=admin_id,
        )
        try:
            db.add(assignment)
            await db.commit()
            await db.refresh(assignment)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("A department assignment already starts in this term.") from exc
        return StudentDepartmentAssignmentResponse.model_validate(assignment)

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
            select(SubjectOffering, LevelSubject)
            .join(LevelSubject, LevelSubject.id == SubjectOffering.level_subject_id)
            .where(
                SubjectOffering.tenant_id == tenant_id,
                SubjectOffering.academic_term_id == academic_term_id,
                LevelSubject.tenant_id == tenant_id,
                LevelSubject.academic_level_id == academic_level_id,
                LevelSubject.is_active.is_(True),
                LevelSubject.archived_at.is_(None),
                or_(
                    SubjectOffering.department_id.is_(None),
                    SubjectOffering.department_id == department_id,
                ),
            )
        )
        resolved: dict[uuid.UUID, ResolvedCurriculumOffering] = {}
        for offering, level_subject in result.all():
            candidate = ResolvedCurriculumOffering(
                level_subject_id=level_subject.id,
                subject_id=level_subject.subject_id,
                academic_term_id=academic_term_id,
                department_id=offering.department_id,
                is_elective=offering.is_elective,
            )
            current = resolved.get(level_subject.id)
            if current is None or (
                current.department_id is None and candidate.department_id is not None
            ):
                resolved[level_subject.id] = candidate
        return list(resolved.values())

    @staticmethod
    async def resolve_department_for_student(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: StudentEnrollment,
        academic_term: AcademicTerm,
    ) -> uuid.UUID | None:
        assignment_rows = (
            await db.execute(
                select(StudentDepartmentAssignment, AcademicTerm)
                .join(
                    AcademicTerm,
                    AcademicTerm.id == StudentDepartmentAssignment.effective_from_term_id,
                )
                .where(
                    StudentDepartmentAssignment.tenant_id == tenant_id,
                    StudentDepartmentAssignment.student_enrollment_id == enrollment.id,
                    AcademicTerm.academic_session_id == academic_term.academic_session_id,
                )
            )
        ).all()
        requested_position = TERM_POSITION[academic_term.name]
        eligible = [
            (assignment, TERM_POSITION[effective_term.name])
            for assignment, effective_term in assignment_rows
            if TERM_POSITION[effective_term.name] <= requested_position
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda row: row[1])[0].department_id

    @staticmethod
    async def resolve_student_curriculum(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        offerings = await CurriculumResolutionService.resolve_student_offerings(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        elective_ids = {offering.level_subject_id for offering in offerings if offering.is_elective}
        if not elective_ids:
            return offerings
        participating = set(
            (
                await db.execute(
                    select(StudentSubjectResult.level_subject_id)
                    .join(
                        StudentAssessmentScore,
                        StudentAssessmentScore.student_subject_result_id == StudentSubjectResult.id,
                    )
                    .where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.student_id == student_id,
                        StudentSubjectResult.academic_term_id == academic_term_id,
                        StudentSubjectResult.level_subject_id.in_(elective_ids),
                    )
                    .distinct()
                )
            ).scalars()
        )
        return [
            offering
            for offering in offerings
            if not offering.is_elective or offering.level_subject_id in participating
        ]

    @staticmethod
    async def resolve_student_offerings(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumOffering]:
        """Resolve all offerings the student may take, including unstarted electives."""
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
        department_id = await CurriculumResolutionService.resolve_department_for_student(
            db,
            tenant_id=tenant_id,
            enrollment=enrollment,
            academic_term=term,
        )
        offerings = await CurriculumResolutionService.resolve_curriculum_offerings(
            db,
            tenant_id=tenant_id,
            academic_level_id=enrollment.academic_level_id,
            academic_term_id=term.id,
            department_id=department_id,
        )
        return offerings
