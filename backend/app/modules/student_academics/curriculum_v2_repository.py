"""Repositories for curriculum membership lifecycle decisions."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.curriculum_models import (
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
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
    PUBLISHED_TERM_STATUSES = (
        AcademicTermStatus.OPEN,
        AcademicTermStatus.CLOSING,
        AcademicTermStatus.CLOSED,
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
        """Return historical, live, and semantic-use references for one membership."""

        def count_subquery(model, *conditions):
            return select(func.count()).select_from(model).where(*conditions).scalar_subquery()

        offerings_total = count_subquery(
            CurriculumOffering,
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
        )
        offerings_live = (
            select(func.count())
            .select_from(CurriculumOffering)
            .join(AcademicTerm, AcademicTerm.id == CurriculumOffering.academic_term_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(CurriculumSubjectRepository.LIVE_TERM_STATUSES),
            )
            .scalar_subquery()
        )
        offerings_published = (
            select(func.count())
            .select_from(CurriculumOffering)
            .join(AcademicTerm, AcademicTerm.id == CurriculumOffering.academic_term_id)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(CurriculumSubjectRepository.PUBLISHED_TERM_STATUSES),
            )
            .scalar_subquery()
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
                    offerings_total.label("offerings_total"),
                    offerings_live.label("offerings_live"),
                    offerings_published.label("offerings_published"),
                    teacher_assignments_total.label("teacher_assignments_total"),
                    teacher_assignments_active.label("teacher_assignments_active"),
                    teacher_assignment_audits_total.label("teacher_assignment_audits_total"),
                    results_total.label("results_total"),
                    results_live.label("results_live"),
                )
            )
        ).one()
        return {
            "offerings_total": int(row.offerings_total),
            "offerings_live": int(row.offerings_live),
            "offerings_published": int(row.offerings_published),
            "teacher_assignments_total": int(row.teacher_assignments_total),
            "teacher_assignments_active": int(row.teacher_assignments_active),
            "teacher_assignment_audits_total": int(row.teacher_assignment_audits_total),
            "results_total": int(row.results_total),
            "results_live": int(row.results_live),
        }
