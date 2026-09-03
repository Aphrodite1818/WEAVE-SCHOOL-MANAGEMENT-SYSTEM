"""Repositories for curriculum membership lifecycle decisions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.curriculum_models import (
    Curriculum,
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.models import (
    AcademicTerm,
    AcademicTermStatus,
    StudentSubjectResult,
    TeacherAssignment,
    TeacherAssignmentLifecycleAudit,
)


class CurriculumSubjectRepository:
    """Persistence and dependency snapshots for one level-subject membership."""

    LIVE_TERM_STATUSES = (
        AcademicTermStatus.DRAFT,
        AcademicTermStatus.OPEN,
        AcademicTermStatus.CLOSING,
    )

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> CurriculumSubject | None:
        query = select(CurriculumSubject).where(
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == curriculum_subject_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_for_curriculum_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> CurriculumSubject | None:
        return (
            await db.execute(
                select(CurriculumSubject).where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.curriculum_id == curriculum_id,
                    CurriculumSubject.subject_id == subject_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_context(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> tuple[CurriculumSubject, Curriculum] | None:
        query = (
            select(CurriculumSubject, Curriculum)
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .where(
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.id == curriculum_subject_id,
                Curriculum.tenant_id == tenant_id,
            )
        )
        if lock:
            query = query.with_for_update(of=CurriculumSubject)
        return (await db.execute(query)).first()

    @staticmethod
    async def list_department_links(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> list[CurriculumSubjectDepartment]:
        query = select(CurriculumSubjectDepartment).where(
            CurriculumSubjectDepartment.tenant_id == tenant_id,
            CurriculumSubjectDepartment.curriculum_subject_id == curriculum_subject_id,
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars())

    @staticmethod
    async def add(db: AsyncSession, row: CurriculumSubject) -> CurriculumSubject:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def save(db: AsyncSession, row: CurriculumSubject) -> CurriculumSubject:
        db.add(row)
        await db.flush()
        return row

    @staticmethod
    async def delete(db: AsyncSession, row: CurriculumSubject) -> None:
        await db.delete(row)

    @staticmethod
    async def count_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> dict[str, int]:
        """Return configuration, historical and live operational references."""

        def count_subquery(model, *conditions):
            return select(func.count()).select_from(model).where(*conditions).scalar_subquery()

        department_links_total = count_subquery(
            CurriculumSubjectDepartment,
            CurriculumSubjectDepartment.tenant_id == tenant_id,
            CurriculumSubjectDepartment.curriculum_subject_id == curriculum_subject_id,
        )
        teacher_assignments_total = count_subquery(
            TeacherAssignment,
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
        )
        teacher_assignments_active = count_subquery(
            TeacherAssignment,
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
            TeacherAssignment.is_active.is_(True),
        )
        teacher_assignment_audits_total = count_subquery(
            TeacherAssignmentLifecycleAudit,
            TeacherAssignmentLifecycleAudit.tenant_id == tenant_id,
            TeacherAssignmentLifecycleAudit.curriculum_subject_id == curriculum_subject_id,
        )
        results_total = count_subquery(
            StudentSubjectResult,
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.curriculum_subject_id == curriculum_subject_id,
        )
        results_live = (
            select(func.count())
            .select_from(StudentSubjectResult)
            .join(AcademicTerm, AcademicTerm.id == StudentSubjectResult.academic_term_id)
            .where(
                StudentSubjectResult.tenant_id == tenant_id,
                StudentSubjectResult.curriculum_subject_id == curriculum_subject_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(CurriculumSubjectRepository.LIVE_TERM_STATUSES),
            )
            .scalar_subquery()
        )

        row = (
            await db.execute(
                select(
                    department_links_total.label("department_links_total"),
                    teacher_assignments_total.label("teacher_assignments_total"),
                    teacher_assignments_active.label("teacher_assignments_active"),
                    teacher_assignment_audits_total.label("teacher_assignment_audits_total"),
                    results_total.label("results_total"),
                    results_live.label("results_live"),
                )
            )
        ).one()
        return {
            "department_links_total": int(row.department_links_total),
            "teacher_assignments_total": int(row.teacher_assignments_total),
            "teacher_assignments_active": int(row.teacher_assignments_active),
            "teacher_assignment_audits_total": int(row.teacher_assignment_audits_total),
            "results_total": int(row.results_total),
            "results_live": int(row.results_live),
        }
