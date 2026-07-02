from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.subjects.models import Subject
from app.modules.teachers.models import TeacherSubject


class SubjectRepository:
    """Low-level database queries for the subjects table."""

    @staticmethod
    async def create_subject(db: AsyncSession, subject: Subject) -> Subject:
        """Create subject."""

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
    ) -> list[TeacherSubject]:
        """Create teacher subject links."""

        teacher_subject_links = [
            TeacherSubject(
                tenant_id=tenant_id,
                subject_id=subject_id,
                teacher_id=teacher_id,
            )
            for teacher_id in teacher_ids
        ]

        db.add_all(teacher_subject_links)
        await db.flush()
        return teacher_subject_links

    @staticmethod
    async def delete_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
        teacher_ids: list[UUID],
    ) -> None:
        """Delete selected teacher subject links for a subject."""

        await db.execute(
            delete(TeacherSubject).where(
                TeacherSubject.tenant_id == tenant_id,
                TeacherSubject.subject_id == subject_id,
                TeacherSubject.teacher_id.in_(teacher_ids),
            )
        )
        await db.flush()

    @staticmethod
    async def get_subject_teacher_ids(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> list[UUID]:
        """Return teacher ids assigned to a subject."""

        result = await db.execute(
            select(TeacherSubject.teacher_id).where(
                TeacherSubject.tenant_id == tenant_id,
                TeacherSubject.subject_id == subject_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_subject_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        subject_id: UUID,
    ) -> Subject | None:
        """Return subject by id."""

        result = await db.execute(
            select(Subject)
            .options(
                selectinload(Subject.teachers),
                selectinload(Subject.teacher_links).selectinload(TeacherSubject.teacher),
            )
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
        """Return subject by display name."""

        result = await db.execute(
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.name == subject_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subject_by_normalized_name(
        db: AsyncSession,
        tenant_id: UUID,
        normalized_name: str,
    ) -> Subject | None:
        """Return subject by normalized display name."""

        result = await db.execute(
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.normalized_name == normalized_name,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subject_by_code(
        db: AsyncSession,
        tenant_id: UUID,
        subject_code: str,
    ) -> Subject | None:
        """Return subject by code."""

        result = await db.execute(
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.code == subject_code,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subject_by_normalized_code(
        db: AsyncSession,
        tenant_id: UUID,
        normalized_code: str,
    ) -> Subject | None:
        """Return subject by normalized code."""

        result = await db.execute(
            select(Subject).where(
                Subject.tenant_id == tenant_id,
                Subject.normalized_code == normalized_code,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_subjects_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        subject_ids: list[UUID],
    ) -> list[Subject]:
        """Return subjects by id."""

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
    ) -> tuple[list[Subject], int]:
        """List all subjects."""

        filters = [Subject.tenant_id == tenant_id]

        if is_active is not None:
            filters.append(Subject.is_active == is_active)

        if search:
            filters.append(Subject.name.ilike(f"%{search}%"))

        total_result = await db.execute(
            select(func.count()).select_from(Subject).where(*filters)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Subject)
            .options(
                selectinload(Subject.teachers),
                selectinload(Subject.teacher_links).selectinload(TeacherSubject.teacher),
            )
            .where(*filters)
            .order_by(Subject.name.asc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all()), total

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
        """List only subjects explicitly assigned to a teacher."""

        filters = [
            Subject.tenant_id == tenant_id,
            TeacherSubject.tenant_id == tenant_id,
            TeacherSubject.teacher_id == teacher_id,
        ]

        if is_active is not None:
            filters.append(Subject.is_active == is_active)

        if search:
            filters.append(Subject.name.ilike(f"%{search}%"))

        total_result = await db.execute(
            select(func.count(func.distinct(Subject.id)))
            .select_from(Subject)
            .join(TeacherSubject, TeacherSubject.subject_id == Subject.id)
            .where(*filters)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Subject)
            .join(TeacherSubject, TeacherSubject.subject_id == Subject.id)
            .options(
                selectinload(Subject.teachers),
                selectinload(Subject.teacher_links).selectinload(TeacherSubject.teacher),
            )
            .where(*filters)
            .order_by(Subject.name.asc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().unique().all()), total

    @staticmethod
    async def update_subject(
        db: AsyncSession,
        subject: Subject,
    ) -> Subject:
        """Persist subject changes."""

        await db.flush()
        await db.refresh(subject)
        return subject

    @staticmethod
    async def delete_subject(db: AsyncSession, subject: Subject) -> None:
        """Delete subject."""

        await db.delete(subject)
        await db.flush()
