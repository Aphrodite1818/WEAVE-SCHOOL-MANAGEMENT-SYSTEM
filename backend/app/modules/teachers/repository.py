# ====================================== #
#          teachers/repository.py        #
# ====================================== #

"""Teacher data access layer."""

from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.teachers.models import Teacher, TeacherStatus, TeacherSubject


class TeacherRepository:
    """Low-level database queries for teachers."""

    @staticmethod
    async def create_teacher(
        db: AsyncSession,
        teacher: Teacher,
    ) -> Teacher:
        """Create a teacher record."""

        db.add(teacher)
        await db.flush()
        await db.refresh(teacher)
        return teacher

    @staticmethod
    async def get_teacher_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
    ) -> Teacher | None:
        """Fetch teacher by ID within a tenant."""

        result = await db.execute(
            select(Teacher)
            .options(
                selectinload(Teacher.subjects),
                selectinload(Teacher.subject_links).selectinload(
                    TeacherSubject.subject
                ),
            )
            .where(
                Teacher.tenant_id == tenant_id,
                Teacher.id == teacher_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        teacher_id: UUID,
        *,
        lock: bool = False,
    ) -> Teacher | None:
        """Fetch teacher by ID globally."""

        query = (
            select(Teacher)
            .options(
                selectinload(Teacher.subjects),
                selectinload(Teacher.subject_links).selectinload(
                    TeacherSubject.subject
                ),
            )
            .where(Teacher.id == teacher_id)
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_id(
        db: AsyncSession,
        teacher_id: UUID,
    ) -> Teacher | None:
        """Fetch active teacher by ID globally."""

        result = await db.execute(
            select(Teacher)
            .options(
                selectinload(Teacher.subjects),
                selectinload(Teacher.subject_links).selectinload(
                    TeacherSubject.subject
                ),
            )
            .where(
                Teacher.id == teacher_id,
                Teacher.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(
        db: AsyncSession,
        email: str,
    ) -> Teacher | None:
        """Fetch teacher by globally unique email."""

        result = await db.execute(
            select(Teacher).where(
                func.lower(Teacher.email) == email.strip().lower(),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_email(
        db: AsyncSession,
        email: str,
    ) -> Teacher | None:
        """Fetch active teacher by globally unique email."""

        result = await db.execute(
            select(Teacher).where(
                func.lower(Teacher.email) == email.strip().lower(),
                Teacher.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def email_exists(
        db: AsyncSession,
        email: str,
        exclude_teacher_id: UUID | None = None,
    ) -> bool:
        """Return True if a teacher email already exists."""

        query = select(Teacher.id).where(
            func.lower(Teacher.email) == email.strip().lower(),
        )

        if exclude_teacher_id is not None:
            query = query.where(Teacher.id != exclude_teacher_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_teacher_by_staff_id(
        db: AsyncSession,
        tenant_id: UUID,
        staff_id: str,
    ) -> Teacher | None:
        """Fetch teacher by staff ID within a tenant."""

        result = await db.execute(
            select(Teacher).where(
                Teacher.tenant_id == tenant_id,
                Teacher.staff_id == staff_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def staff_id_exists(
        db: AsyncSession,
        tenant_id: UUID,
        staff_id: str,
        exclude_teacher_id: UUID | None = None,
    ) -> bool:
        """Return True if staff ID already exists within tenant."""

        query = select(Teacher.id).where(
            Teacher.tenant_id == tenant_id,
            func.lower(Teacher.staff_id) == staff_id.strip().lower(),
        )

        if exclude_teacher_id is not None:
            query = query.where(Teacher.id != exclude_teacher_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def get_teachers_by_ids(
        db: AsyncSession,
        teacher_ids: list[UUID],
        tenant_id: UUID,
        status: TeacherStatus | None = None,
    ) -> list[Teacher]:
        """Return multiple teachers by IDs within a tenant."""

        if not teacher_ids:
            return []

        filters = [
            Teacher.tenant_id == tenant_id,
            Teacher.id.in_(teacher_ids),
        ]

        if status is not None:
            filters.append(Teacher.status == status)

        result = await db.execute(
            select(Teacher)
            .options(
                selectinload(Teacher.subjects),
                selectinload(Teacher.subject_links).selectinload(
                    TeacherSubject.subject
                ),
            )
            .where(*filters)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_all_teachers(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[list[Teacher], int]:
        """Return paginated teachers for a tenant."""

        filters = [Teacher.tenant_id == tenant_id]

        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Teacher.email.ilike(search_pattern),
                    Teacher.first_name.ilike(search_pattern),
                    Teacher.last_name.ilike(search_pattern),
                    Teacher.staff_id.ilike(search_pattern),
                    Teacher.qualification.ilike(search_pattern),
                    Teacher.specialization.ilike(search_pattern),
                )
            )

        total_result = await db.execute(
            select(func.count()).select_from(Teacher).where(*filters)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Teacher)
            .options(
                selectinload(Teacher.subjects),
                selectinload(Teacher.subject_links).selectinload(
                    TeacherSubject.subject
                ),
            )
            .where(*filters)
            .order_by(Teacher.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        return list(result.scalars().all()), total

    @staticmethod
    async def save(
        db: AsyncSession,
        teacher: Teacher,
    ) -> Teacher:
        """Persist teacher changes."""

        db.add(teacher)
        await db.flush()
        await db.refresh(teacher)
        return teacher

    @staticmethod
    async def create_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
        subject_ids: list[UUID],
    ) -> list[TeacherSubject]:
        """Create teacher-subject links."""

        if not subject_ids:
            return []

        teacher_subject_links = [
            TeacherSubject(
                tenant_id=tenant_id,
                teacher_id=teacher_id,
                subject_id=subject_id,
            )
            for subject_id in subject_ids
        ]

        db.add_all(teacher_subject_links)
        await db.flush()
        return teacher_subject_links

    @staticmethod
    async def delete_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
        subject_ids: list[UUID],
    ) -> None:
        """Delete selected teacher-subject links."""

        if not subject_ids:
            return

        await db.execute(
            delete(TeacherSubject).where(
                TeacherSubject.tenant_id == tenant_id,
                TeacherSubject.teacher_id == teacher_id,
                TeacherSubject.subject_id.in_(subject_ids),
            )
        )
        await db.flush()

    @staticmethod
    async def delete_all_teacher_subject_links(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
    ) -> None:
        """Delete all subject links for a teacher."""

        await db.execute(
            delete(TeacherSubject).where(
                TeacherSubject.tenant_id == tenant_id,
                TeacherSubject.teacher_id == teacher_id,
            )
        )
        await db.flush()

    @staticmethod
    async def get_teacher_subject_ids(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_id: UUID,
    ) -> list[UUID]:
        """Return subject IDs assigned to a teacher."""

        result = await db.execute(
            select(TeacherSubject.subject_id).where(
                TeacherSubject.tenant_id == tenant_id,
                TeacherSubject.teacher_id == teacher_id,
            )
        )

        return list(result.scalars().all())
