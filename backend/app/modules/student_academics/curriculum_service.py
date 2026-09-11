"""Authoritative curriculum, specialization, and elective resolution."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    AcademicLevelStatus,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.models import (
    AcademicTerm,
    AcademicTermName,
    StudentAssessmentScore,
    StudentSubjectResult,
)
from app.modules.students.models import StudentEnrollment
from app.modules.students.repository import StudentEnrollmentRepository
from app.modules.subjects.models import Subject


_TERM_POSITIONS = {
    AcademicTermName.FIRST_TERM: 1,
    AcademicTermName.SECOND_TERM: 2,
    AcademicTermName.THIRD_TERM: 3,
}


@dataclass(frozen=True, slots=True)
class ResolvedCurriculumSubject:
    """One active curriculum subject applicable to a class for an exact term."""

    curriculum_subject_id: uuid.UUID
    subject_id: uuid.UUID
    academic_level_department_id: uuid.UUID | None
    is_elective: bool
    is_general: bool


class CurriculumResolutionService:
    """Single source of truth for class/term subject eligibility.

    Before a level's specialization threshold is reached, every active curriculum
    subject applies to every class in the level. Once specialization is active,
    a class must have an exact ClassTermDepartmentAssignment and receives general
    subjects plus subjects linked to that level-department identity.
    """

    @staticmethod
    def specialization_is_active(level: AcademicLevel, term: AcademicTerm) -> bool:
        threshold = level.specialization_required_from_term_position
        if threshold is None:
            return False
        position = _TERM_POSITIONS.get(term.name)
        return position is not None and position >= threshold

    @staticmethod
    async def _term(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> AcademicTerm:
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
        return term

    @staticmethod
    async def _level(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
    ) -> AcademicLevel:
        level = (
            await db.execute(
                select(AcademicLevel).where(
                    AcademicLevel.tenant_id == tenant_id,
                    AcademicLevel.id == academic_level_id,
                    AcademicLevel.status == AcademicLevelStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()
        if level is None:
            raise ConflictException("Academic level must be active.")
        return level

    @staticmethod
    async def resolve_level_department_for_class(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        academic_term: AcademicTerm,
        specialization_required: bool,
    ) -> uuid.UUID | None:
        """Return exact level-department identity when specialization is active."""

        if not specialization_required:
            return None
        joined = (
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
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == academic_term.id,
                    AcademicLevelDepartment.tenant_id == tenant_id,
                    Department.tenant_id == tenant_id,
                )
            )
        ).first()
        if joined is None:
            raise ConflictException(
                "This class requires a department specialization for the selected term."
            )
        _assignment, link, department = joined
        if link.academic_level_id != academic_level_id:
            raise ConflictException(
                "Class specialization does not belong to the class academic level."
            )
        if (
            not link.is_active
            or link.archived_at is not None
            or not department.is_active
            or department.archived_at is not None
        ):
            raise ConflictException(
                "Class specialization is no longer active for this academic level."
            )
        return link.id

    @staticmethod
    async def resolve_classes_subjects(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_ids: Iterable[uuid.UUID],
        academic_term_id: uuid.UUID,
        skip_unresolvable: bool = False,
    ) -> dict[uuid.UUID, list[ResolvedCurriculumSubject]]:
        """Resolve curriculum for many classes with query count independent of class count.

        ``skip_unresolvable`` is intended for bulk availability/reconciliation paths:
        inactive classes, inactive levels, or classes missing a required exact-term
        specialization resolve to an empty list instead of aborting the whole batch.
        The single-class API remains strict and delegates here with the flag disabled.
        """

        requested_ids = list(dict.fromkeys(class_ids))
        if not requested_ids:
            return {}

        classrooms = list(
            (
                await db.execute(
                    select(ClassRoom).where(
                        ClassRoom.tenant_id == tenant_id,
                        ClassRoom.id.in_(requested_ids),
                        ClassRoom.is_active.is_(True),
                        ClassRoom.archived_at.is_(None),
                    )
                )
            ).scalars()
        )
        classrooms_by_id = {row.id: row for row in classrooms}
        missing_classes = set(requested_ids) - set(classrooms_by_id)
        if missing_classes and not skip_unresolvable:
            raise NotFoundException("Active class not found.")

        resolved_by_class: dict[uuid.UUID, list[ResolvedCurriculumSubject]] = {
            class_id: [] for class_id in requested_ids
        }
        if not classrooms:
            return resolved_by_class

        term = await CurriculumResolutionService._term(
            db,
            tenant_id=tenant_id,
            academic_term_id=academic_term_id,
        )
        level_ids = {row.academic_level_id for row in classrooms}
        levels = list(
            (
                await db.execute(
                    select(AcademicLevel).where(
                        AcademicLevel.tenant_id == tenant_id,
                        AcademicLevel.id.in_(level_ids),
                        AcademicLevel.status == AcademicLevelStatus.ACTIVE,
                    )
                )
            ).scalars()
        )
        levels_by_id = {row.id: row for row in levels}
        invalid_level_classes = {
            row.id for row in classrooms if row.academic_level_id not in levels_by_id
        }
        if invalid_level_classes and not skip_unresolvable:
            raise ConflictException("Academic level must be active.")

        specialization_by_class: dict[uuid.UUID, bool] = {}
        for classroom in classrooms:
            level = levels_by_id.get(classroom.academic_level_id)
            specialization_by_class[classroom.id] = bool(
                level and CurriculumResolutionService.specialization_is_active(level, term)
            )

        required_class_ids = {
            class_id
            for class_id, required in specialization_by_class.items()
            if required and class_id not in invalid_level_classes
        }
        department_by_class: dict[uuid.UUID, uuid.UUID] = {}
        if required_class_ids:
            specialization_rows = (
                await db.execute(
                    select(
                        ClassTermDepartmentAssignment.class_id,
                        AcademicLevelDepartment.id,
                        AcademicLevelDepartment.academic_level_id,
                    )
                    .join(
                        AcademicLevelDepartment,
                        AcademicLevelDepartment.id
                        == ClassTermDepartmentAssignment.academic_level_department_id,
                    )
                    .join(Department, Department.id == AcademicLevelDepartment.department_id)
                    .where(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.academic_term_id == term.id,
                        ClassTermDepartmentAssignment.class_id.in_(required_class_ids),
                        AcademicLevelDepartment.tenant_id == tenant_id,
                        AcademicLevelDepartment.is_active.is_(True),
                        AcademicLevelDepartment.archived_at.is_(None),
                        Department.tenant_id == tenant_id,
                        Department.is_active.is_(True),
                        Department.archived_at.is_(None),
                    )
                )
            ).all()
            for class_id, level_department_id, level_id in specialization_rows:
                classroom = classrooms_by_id.get(class_id)
                if classroom is not None and classroom.academic_level_id == level_id:
                    department_by_class[class_id] = level_department_id

            unresolved_specializations = required_class_ids - set(department_by_class)
            if unresolved_specializations and not skip_unresolvable:
                raise ConflictException(
                    "This class requires a department specialization for the selected term."
                )

        usable_classes = [
            classroom
            for classroom in classrooms
            if classroom.id not in invalid_level_classes
            and (
                not specialization_by_class[classroom.id]
                or classroom.id in department_by_class
            )
        ]
        usable_level_ids = {row.academic_level_id for row in usable_classes}
        if not usable_level_ids:
            return resolved_by_class

        curriculum_rows = (
            await db.execute(
                select(CurriculumSubject, Curriculum.academic_level_id)
                .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
                .join(Subject, Subject.id == CurriculumSubject.subject_id)
                .where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.is_active.is_(True),
                    Curriculum.tenant_id == tenant_id,
                    Curriculum.academic_level_id.in_(usable_level_ids),
                    Subject.tenant_id == tenant_id,
                    Subject.is_active.is_(True),
                    Subject.archived_at.is_(None),
                )
                .order_by(Curriculum.academic_level_id, Subject.name, CurriculumSubject.id)
            )
        ).all()
        subjects_by_level: dict[uuid.UUID, list[CurriculumSubject]] = {}
        curriculum_subject_ids: list[uuid.UUID] = []
        for curriculum_subject, academic_level_id in curriculum_rows:
            subjects_by_level.setdefault(academic_level_id, []).append(curriculum_subject)
            curriculum_subject_ids.append(curriculum_subject.id)

        links_by_subject: dict[uuid.UUID, set[uuid.UUID]] = {}
        if curriculum_subject_ids:
            link_rows = (
                await db.execute(
                    select(CurriculumSubjectDepartment).where(
                        CurriculumSubjectDepartment.tenant_id == tenant_id,
                        CurriculumSubjectDepartment.curriculum_subject_id.in_(
                            curriculum_subject_ids
                        ),
                    )
                )
            ).scalars()
            for link in link_rows:
                links_by_subject.setdefault(link.curriculum_subject_id, set()).add(
                    link.academic_level_department_id
                )

        for classroom in usable_classes:
            specialization_active = specialization_by_class[classroom.id]
            level_department_id = department_by_class.get(classroom.id)
            resolved: list[ResolvedCurriculumSubject] = []
            for curriculum_subject in subjects_by_level.get(classroom.academic_level_id, []):
                department_links = links_by_subject.get(curriculum_subject.id, set())
                is_general = not department_links
                if specialization_active and not is_general:
                    if level_department_id not in department_links:
                        continue
                resolved.append(
                    ResolvedCurriculumSubject(
                        curriculum_subject_id=curriculum_subject.id,
                        subject_id=curriculum_subject.subject_id,
                        academic_level_department_id=(
                            None
                            if is_general or not specialization_active
                            else level_department_id
                        ),
                        is_elective=curriculum_subject.is_elective,
                        is_general=is_general,
                    )
                )
            resolved_by_class[classroom.id] = resolved
        return resolved_by_class

    @staticmethod
    async def resolve_class_subjects(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumSubject]:
        resolved = await CurriculumResolutionService.resolve_classes_subjects(
            db,
            tenant_id=tenant_id,
            class_ids=(class_id,),
            academic_term_id=academic_term_id,
            skip_unresolvable=False,
        )
        return resolved[class_id]

    @staticmethod
    async def resolve_student_subjects(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumSubject]:
        term = await CurriculumResolutionService._term(
            db,
            tenant_id=tenant_id,
            academic_term_id=academic_term_id,
        )
        enrollment = await StudentEnrollmentRepository.get_authoritative_for_session(
            db,
            tenant_id,
            student_id,
            term.academic_session_id,
        )
        if enrollment is None:
            raise ConflictException("Student enrollment for this academic session is required.")
        if enrollment.class_id is None:
            raise ConflictException("Student must belong to a class for curriculum resolution.")
        return await CurriculumResolutionService.resolve_class_subjects(
            db,
            tenant_id=tenant_id,
            class_id=enrollment.class_id,
            academic_term_id=academic_term_id,
        )

    @staticmethod
    async def resolve_level_department_for_student(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollment: StudentEnrollment,
        academic_term: AcademicTerm,
    ) -> uuid.UUID | None:
        """Resolve specialization for callers that explicitly need the identity."""

        if enrollment.class_id is None:
            return None
        level = await CurriculumResolutionService._level(
            db,
            tenant_id=tenant_id,
            academic_level_id=enrollment.academic_level_id,
        )
        active = CurriculumResolutionService.specialization_is_active(level, academic_term)
        return await CurriculumResolutionService.resolve_level_department_for_class(
            db,
            tenant_id=tenant_id,
            class_id=enrollment.class_id,
            academic_level_id=enrollment.academic_level_id,
            academic_term=academic_term,
            specialization_required=active,
        )

    @staticmethod
    async def resolve_student_curriculum(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> list[ResolvedCurriculumSubject]:
        """Return report-card-required curriculum for one student and term.

        Electives only become report-card-required after actual score participation.
        """

        subjects = await CurriculumResolutionService.resolve_student_subjects(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_term_id=academic_term_id,
        )
        elective_ids = {item.curriculum_subject_id for item in subjects if item.is_elective}
        if not elective_ids:
            return subjects

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
            item
            for item in subjects
            if not item.is_elective or item.curriculum_subject_id in participating
        ]
