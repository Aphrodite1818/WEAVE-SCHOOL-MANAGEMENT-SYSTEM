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
        """Create subject capabilities for teacher membership IDs."""

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
    ) -> Subject | None:
        result = await db.execute(
            select(Subject)
            .options(*_subject_teacher_load_options())
            .where(
                Subject.tenant_id == tenant_id,
                Subject.id == subject_id,
            )
        )
        return result.scalar_one_or_none()

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
            filters.append(Subject.is_active.is_(True))
            filters.append(Subject.archived_at.is_(None))
        elif lifecycle_status == "inactive":
            filters.append(Subject.is_active.is_(False))
            filters.append(Subject.archived_at.is_(None))
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
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Subject], int]:
        filters = [
            Subject.tenant_id == tenant_id,
            Subject.archived_at.is_(None),
            TeacherMembershipSubject.tenant_id == tenant_id,
            TeacherMembershipSubject.teacher_membership_id == teacher_id,
            TeacherMembershipSubject.is_active.is_(True),
        ]
        if is_active is not None:
            filters.append(Subject.is_active.is_(is_active))
            if is_active:
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
    async def count_subject_dependencies(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> dict[str, int]:
        from app.modules.report_cards.models import ReportCardSubjectLine
        from app.modules.student_academics.models import (
            ClassSubject,
            StudentSubjectResult,
            TeacherAssignment,
        )

        class_subject_count = (
            await db.execute(
                select(func.count())
                .select_from(ClassSubject)
                .where(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        ).scalar_one()
        teacher_link_count = (
            await db.execute(
                select(func.count())
                .select_from(TeacherMembershipSubject)
                .where(
                    TeacherMembershipSubject.tenant_id == tenant_id,
                    TeacherMembershipSubject.subject_id == subject_id,
                )
            )
        ).scalar_one()
        teacher_assignment_count = (
            await db.execute(
                select(func.count())
                .select_from(TeacherAssignment)
                .join(ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id)
                .where(
                    TeacherAssignment.tenant_id == tenant_id,
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        ).scalar_one()
        result_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentSubjectResult)
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.subject_id == subject_id,
                )
            )
        ).scalar_one()
        report_card_line_count = (
            await db.execute(
                select(func.count())
                .select_from(ReportCardSubjectLine)
                .where(
                    ReportCardSubjectLine.tenant_id == tenant_id,
                    ReportCardSubjectLine.subject_id == subject_id,
                )
            )
        ).scalar_one()
        return {
            "class_subjects": int(class_subject_count),
            "teacher_links": int(teacher_link_count),
            "teacher_assignments": int(teacher_assignment_count),
            "results": int(result_count),
            "report_card_lines": int(report_card_line_count),
        }

    @staticmethod
    async def count_live_subject_dependencies(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> dict[str, int]:
        from app.modules.student_academics.models import ClassSubject, TeacherAssignment

        active_class_subject_count = (
            await db.execute(
                select(func.count())
                .select_from(ClassSubject)
                .where(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.subject_id == subject_id,
                    ClassSubject.is_active.is_(True),
                    ClassSubject.archived_at.is_(None),
                )
            )
        ).scalar_one()
        active_teacher_link_count = (
            await db.execute(
                select(func.count())
                .select_from(TeacherMembershipSubject)
                .where(
                    TeacherMembershipSubject.tenant_id == tenant_id,
                    TeacherMembershipSubject.subject_id == subject_id,
                    TeacherMembershipSubject.is_active.is_(True),
                )
            )
        ).scalar_one()
        active_teacher_assignment_count = (
            await db.execute(
                select(func.count())
                .select_from(TeacherAssignment)
                .join(ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id)
                .where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.is_active.is_(True),
                    TeacherAssignment.effective_to.is_(None),
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        ).scalar_one()
        return {
            "active_class_subjects": int(active_class_subject_count),
            "active_teacher_links": int(active_teacher_link_count),
            "active_teacher_assignments": int(active_teacher_assignment_count),
        }
