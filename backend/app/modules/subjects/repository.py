"""Tenant-scoped subject repository and teacher membership capabilities."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.subjects.models import Subject
from app.modules.teachers.models import TeacherMembership, TeacherMembershipSubject


def _subject_teacher_load_options() -> tuple:
    return (
        selectinload(Subject.teacher_links)
        .selectinload(TeacherMembershipSubject.teacher_membership)
        .selectinload(TeacherMembership.teacher_account),
    )


class SubjectRepository:
    @staticmethod
    async def create_subject(db: AsyncSession, subject: Subject) -> Subject:
        db.add(subject)
        await db.flush()
        await db.refresh(subject)
        return subject

    @staticmethod
    async def create_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
        teacher_ids: list[UUID],
    ) -> list[TeacherMembershipSubject]:
        links = [
            TeacherMembershipSubject(
                tenant_id=tenant_id,
                subject_id=subject_id,
                teacher_membership_id=membership_id,
                is_active=True,
            )
            for membership_id in teacher_ids
        ]
        db.add_all(links)
        await db.flush()
        return links

    @staticmethod
    async def delete_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
        teacher_ids: list[UUID],
    ) -> None:
        if not teacher_ids:
            return
        await db.execute(
            delete(TeacherMembershipSubject).where(
                TeacherMembershipSubject.tenant_id == tenant_id,
                TeacherMembershipSubject.subject_id == subject_id,
                TeacherMembershipSubject.teacher_membership_id.in_(teacher_ids),
            )
        )
        await db.flush()

    @staticmethod
    async def get_subject_teacher_ids(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[UUID]:
        result = await db.execute(
            select(TeacherMembershipSubject.teacher_membership_id).where(
                TeacherMembershipSubject.tenant_id == tenant_id,
                TeacherMembershipSubject.subject_id == subject_id,
                TeacherMembershipSubject.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_subject_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
        *,
        lock: bool = False,
    ) -> Subject | None:
        query = (
            select(Subject)
            .options(*_subject_teacher_load_options())
            .where(
                Subject.tenant_id == tenant_id,
                Subject.id == subject_id,
            )
        )
        if lock:
            query = query.with_for_update(of=Subject)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_subject_by_name(
        db: AsyncSession,
        tenant_id: UUID,
        subject_name: str,
    ) -> Subject | None:
        return (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.name == subject_name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_subject_by_normalized_name(
        db: AsyncSession,
        tenant_id: UUID,
        normalized_name: str,
    ) -> Subject | None:
        return (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.normalized_name == normalized_name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_subject_by_code(
        db: AsyncSession,
        tenant_id: UUID,
        subject_code: str,
    ) -> Subject | None:
        return (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.code == subject_code,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_subject_by_normalized_code(
        db: AsyncSession,
        tenant_id: UUID,
        normalized_code: str,
    ) -> Subject | None:
        return (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.normalized_code == normalized_code,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_subjects_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        subject_ids: list[UUID],
    ) -> list[Subject]:
        if not subject_ids:
            return []
        result = await db.execute(
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.id.in_(subject_ids),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_all_subjects(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
        search: str | None = None,
        include_archived: bool = False,
        lifecycle_status: str | None = None,
    ) -> tuple[list[Subject], int]:
        filters = [Subject.tenant_id == tenant_id]
        if lifecycle_status == "active":
            filters.extend([Subject.is_active.is_(True), Subject.archived_at.is_(None)])
        elif lifecycle_status == "inactive":
            filters.extend([Subject.is_active.is_(False), Subject.archived_at.is_(None)])
        elif lifecycle_status == "archived":
            filters.append(Subject.archived_at.is_not(None))
        elif is_active is not None:
            filters.append(Subject.is_active.is_(is_active))
            if is_active:
                filters.append(Subject.archived_at.is_(None))
        if not include_archived and lifecycle_status != "archived":
            filters.append(Subject.archived_at.is_(None))
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Subject.name.ilike(pattern),
                    Subject.code.ilike(pattern),
                    Subject.description.ilike(pattern),
                )
            )
        total = (
            await db.execute(select(func.count()).select_from(Subject).where(*filters))
        ).scalar_one()
        result = await db.execute(
            select(Subject)
            .options(*_subject_teacher_load_options())
            .where(*filters)
            .order_by(Subject.name.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    @staticmethod
    async def list_subjects_for_teacher(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> tuple[list[Subject], int]:
        filters = [
            Subject.tenant_id == tenant_id,
            Subject.is_active.is_(True),
            Subject.archived_at.is_(None),
            TeacherMembershipSubject.tenant_id == tenant_id,
            TeacherMembershipSubject.teacher_membership_id == teacher_id,
            TeacherMembershipSubject.is_active.is_(True),
        ]
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Subject.name.ilike(pattern),
                    Subject.code.ilike(pattern),
                    Subject.description.ilike(pattern),
                )
            )
        joined = (
            select(Subject)
            .join(
                TeacherMembershipSubject,
                TeacherMembershipSubject.subject_id == Subject.id,
            )
            .where(*filters)
        )
        total = (await db.execute(select(func.count()).select_from(joined.subquery()))).scalar_one()
        result = await db.execute(
            joined.options(*_subject_teacher_load_options())
            .order_by(Subject.name.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), total

    @staticmethod
    async def update_subject(db: AsyncSession, subject: Subject) -> Subject:
        db.add(subject)
        await db.flush()
        await db.refresh(subject)
        return subject

    @staticmethod
    async def delete_subject(db: AsyncSession, subject: Subject) -> None:
        await db.delete(subject)
        await db.flush()

    @staticmethod
    async def count_dependencies(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> dict[str, int]:
        """Return historical and live references to one subject in one query."""

        from app.modules.report_cards.models import ReportCard, ReportCardSubjectLine
        from app.modules.student_academics.curriculum_models import CurriculumSubject
        from app.modules.student_academics.models import (
            AcademicTerm,
            AcademicTermStatus,
            StudentSubjectResult,
            TeacherAssignment,
        )

        live_term_statuses = (
            AcademicTermStatus.DRAFT,
            AcademicTermStatus.OPEN,
            AcademicTermStatus.CLOSING,
        )

        def count_subquery(model, *conditions):
            return select(func.count()).select_from(model).where(*conditions).scalar_subquery()

        curriculum_subjects_total = count_subquery(
            CurriculumSubject,
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.subject_id == subject_id,
        )
        curriculum_subjects_live = count_subquery(
            CurriculumSubject,
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.subject_id == subject_id,
            CurriculumSubject.is_active.is_(True),
        )
        teacher_links_total = count_subquery(
            TeacherMembershipSubject,
            TeacherMembershipSubject.tenant_id == tenant_id,
            TeacherMembershipSubject.subject_id == subject_id,
        )
        teacher_links_live = count_subquery(
            TeacherMembershipSubject,
            TeacherMembershipSubject.tenant_id == tenant_id,
            TeacherMembershipSubject.subject_id == subject_id,
            TeacherMembershipSubject.is_active.is_(True),
        )
        teacher_assignments_total = (
            select(func.count())
            .select_from(TeacherAssignment)
            .join(CurriculumSubject, CurriculumSubject.id == TeacherAssignment.curriculum_subject_id)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.subject_id == subject_id,
            )
            .scalar_subquery()
        )
        teacher_assignments_live = (
            select(func.count())
            .select_from(TeacherAssignment)
            .join(CurriculumSubject, CurriculumSubject.id == TeacherAssignment.curriculum_subject_id)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.effective_to.is_(None),
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.subject_id == subject_id,
            )
            .scalar_subquery()
        )
        results_total = count_subquery(
            StudentSubjectResult,
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.subject_id == subject_id,
        )
        results_live = (
            select(func.count())
            .select_from(StudentSubjectResult)
            .join(AcademicTerm, AcademicTerm.id == StudentSubjectResult.academic_term_id)
            .where(
                StudentSubjectResult.tenant_id == tenant_id,
                StudentSubjectResult.subject_id == subject_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(live_term_statuses),
            )
            .scalar_subquery()
        )
        report_card_lines_total = count_subquery(
            ReportCardSubjectLine,
            ReportCardSubjectLine.tenant_id == tenant_id,
            ReportCardSubjectLine.subject_id == subject_id,
        )
        report_card_lines_live = (
            select(func.count())
            .select_from(ReportCardSubjectLine)
            .join(ReportCard, ReportCard.id == ReportCardSubjectLine.report_card_id)
            .join(AcademicTerm, AcademicTerm.id == ReportCard.academic_term_id)
            .where(
                ReportCardSubjectLine.tenant_id == tenant_id,
                ReportCardSubjectLine.subject_id == subject_id,
                ReportCard.tenant_id == tenant_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(live_term_statuses),
            )
            .scalar_subquery()
        )

        row = (
            await db.execute(
                select(
                    curriculum_subjects_total.label("curriculum_subjects_total"),
                    curriculum_subjects_live.label("curriculum_subjects_live"),
                    teacher_links_total.label("teacher_links_total"),
                    teacher_links_live.label("teacher_links_live"),
                    teacher_assignments_total.label("teacher_assignments_total"),
                    teacher_assignments_live.label("teacher_assignments_live"),
                    results_total.label("results_total"),
                    results_live.label("results_live"),
                    report_card_lines_total.label("report_card_lines_total"),
                    report_card_lines_live.label("report_card_lines_live"),
                )
            )
        ).one()
        return {
            "curriculum_subjects_total": int(row.curriculum_subjects_total),
            "curriculum_subjects_live": int(row.curriculum_subjects_live),
            "teacher_links_total": int(row.teacher_links_total),
            "teacher_links_live": int(row.teacher_links_live),
            "teacher_assignments_total": int(row.teacher_assignments_total),
            "teacher_assignments_live": int(row.teacher_assignments_live),
            "results_total": int(row.results_total),
            "results_live": int(row.results_live),
            "report_card_lines_total": int(row.report_card_lines_total),
            "report_card_lines_live": int(row.report_card_lines_live),
        }

    @staticmethod
    async def count_total_dependencies_for_subjects(
        db: AsyncSession,
        tenant_id: UUID,
        subject_ids: list[UUID],
    ) -> dict[UUID, dict[str, int]]:
        """Batch total dependency counts for admin list delete-eligibility."""

        from app.modules.report_cards.models import ReportCardSubjectLine
        from app.modules.student_academics.curriculum_models import CurriculumSubject
        from app.modules.student_academics.models import StudentSubjectResult, TeacherAssignment

        if not subject_ids:
            return {}

        keys = (
            "curriculum_subjects_total",
            "teacher_links_total",
            "teacher_assignments_total",
            "results_total",
            "report_card_lines_total",
        )
        counts: dict[UUID, dict[str, int]] = {
            subject_id: {key: 0 for key in keys} for subject_id in subject_ids
        }

        async def apply_grouped(query, key: str) -> None:
            for subject_id, count in (await db.execute(query)).all():
                if subject_id in counts:
                    counts[subject_id][key] = int(count)

        await apply_grouped(
            select(CurriculumSubject.subject_id, func.count())
            .where(
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.subject_id.in_(subject_ids),
            )
            .group_by(CurriculumSubject.subject_id),
            "curriculum_subjects_total",
        )
        await apply_grouped(
            select(TeacherMembershipSubject.subject_id, func.count())
            .where(
                TeacherMembershipSubject.tenant_id == tenant_id,
                TeacherMembershipSubject.subject_id.in_(subject_ids),
            )
            .group_by(TeacherMembershipSubject.subject_id),
            "teacher_links_total",
        )
        await apply_grouped(
            select(CurriculumSubject.subject_id, func.count())
            .select_from(TeacherAssignment)
            .join(CurriculumSubject, CurriculumSubject.id == TeacherAssignment.curriculum_subject_id)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.subject_id.in_(subject_ids),
            )
            .group_by(CurriculumSubject.subject_id),
            "teacher_assignments_total",
        )
        await apply_grouped(
            select(StudentSubjectResult.subject_id, func.count())
            .where(
                StudentSubjectResult.tenant_id == tenant_id,
                StudentSubjectResult.subject_id.in_(subject_ids),
            )
            .group_by(StudentSubjectResult.subject_id),
            "results_total",
        )
        await apply_grouped(
            select(ReportCardSubjectLine.subject_id, func.count())
            .where(
                ReportCardSubjectLine.tenant_id == tenant_id,
                ReportCardSubjectLine.subject_id.in_(subject_ids),
            )
            .group_by(ReportCardSubjectLine.subject_id),
            "report_card_lines_total",
        )
        return counts
