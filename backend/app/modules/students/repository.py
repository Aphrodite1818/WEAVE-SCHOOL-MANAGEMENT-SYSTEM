#==========================#
# student repository.py#
#==========================#
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccessCode,
    StudentLinkCode,
    StudentParentLink,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
)


class StudentRepository:
    """Database operations for student actors."""

    @staticmethod
    async def create_student(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        """Create a student record."""

        db.add(student)
        await db.flush()
        await db.refresh(student)
        return student

    @staticmethod
    async def get_student_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> Student | None:
        """Get a student by ID within a tenant."""

        result = await db.execute(
            select(Student).where(
                Student.id == student_id,
                Student.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> Student | None:
        """Get a student by global ID."""

        query = select(Student).where(Student.id == student_id)

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_id(
        db: AsyncSession,
        student_id: UUID,
    ) -> Student | None:
        """Get an active student by global ID."""

        result = await db.execute(
            select(Student).where(
                Student.id == student_id,
                Student.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_admission_number(
        db: AsyncSession,
        tenant_id: UUID,
        admission_number: str,
    ) -> Student | None:
        """Get a student by admission number within a tenant."""

        result = await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                func.lower(Student.admission_number) == admission_number.strip().lower(),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_admission_number(
        db: AsyncSession,
        tenant_id: UUID,
        admission_number: str,
    ) -> Student | None:
        """Get an active student by admission number within a tenant."""

        result = await db.execute(
            select(Student).where(
                Student.tenant_id == tenant_id,
                func.lower(Student.admission_number) == admission_number.strip().lower(),
                Student.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def admission_number_exists(
        db: AsyncSession,
        tenant_id: UUID,
        admission_number: str,
        exclude_student_id: UUID | None = None,
    ) -> bool:
        """Return True if an admission number already exists."""

        query = select(Student.id).where(
            Student.tenant_id == tenant_id,
            func.lower(Student.admission_number) == admission_number.strip().lower(),
        )

        if exclude_student_id is not None:
            query = query.where(Student.id != exclude_student_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _build_student_list_query(
        tenant_id: UUID,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple:
        """Build the base query for filtered student listing."""

        conditions = [Student.tenant_id == tenant_id]

        if class_id is not None:
            conditions.append(Student.class_id == class_id)

        if status is not None:
            conditions.append(Student.status == status)

        if search:
            search_term = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Student.first_name.ilike(search_term),
                    Student.last_name.ilike(search_term),
                    Student.admission_number.ilike(search_term),
                )
            )

        query = select(Student).where(*conditions)
        return query, conditions

    @staticmethod
    async def list_all_students(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple[list[Student], int]:
        """List students with optional filters."""

        base_query, conditions = StudentRepository._build_student_list_query(
            tenant_id=tenant_id,
            search=search,
            class_id=class_id,
            status=status,
        )

        result = await db.execute(
            base_query
            .order_by(Student.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        students = list(result.scalars().all())

        total_result = await db.execute(
            select(func.count()).select_from(Student).where(*conditions)
        )
        total = total_result.scalar_one()

        return students, total

    @staticmethod
    async def list_students(
        db: AsyncSession,
        tenant_id: UUID,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple[list[Student], int]:
        """Compatibility wrapper for listing students."""

        return await StudentRepository.list_all_students(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            search=search,
            class_id=class_id,
            status=status,
        )

    @staticmethod
    async def get_all_students_by_class_id(
        db: AsyncSession,
        tenant_id: UUID,
        class_id: UUID,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Student]:
        """Get all students by class id within a tenant."""

        result = await db.execute(
            select(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
            )
            .offset(skip)
            .limit(limit)
            .order_by(Student.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        """Persist student changes."""

        db.add(student)
        await db.flush()
        await db.refresh(student)
        return student

    @staticmethod
    async def update_student(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        """Compatibility wrapper for persisting student changes."""

        return await StudentRepository.save(db=db, student=student)

    @staticmethod
    async def delete_student(
        db: AsyncSession,
        student: Student,
    ) -> None:
        """Delete a student profile."""

        await db.delete(student)
        await db.flush()


class StudentParentLinkRepository:
    """Database operations for student-parent links."""

    @staticmethod
    async def create_student_parent_link(
        db: AsyncSession,
        link: StudentParentLink,
    ) -> StudentParentLink:
        """Create a student-parent link."""

        db.add(link)
        await db.flush()
        await db.refresh(link)
        return link

    @staticmethod
    async def get_parent_student_link_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        link_id: UUID,
    ) -> StudentParentLink | None:
        """Get a student-parent link by id within a tenant."""

        result = await db.execute(
            select(StudentParentLink).where(
                StudentParentLink.id == link_id,
                StudentParentLink.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_student_and_parent(
        db: AsyncSession,
        student_id: UUID,
        tenant_id: UUID,
        parent_id: UUID,
    ) -> StudentParentLink | None:
        """Get a student-parent link by student and parent."""

        result = await db.execute(
            select(StudentParentLink).where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.parent_id == parent_id,
                StudentParentLink.student_id == student_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_student_id(
        db: AsyncSession,
        student_id: UUID,
        tenant_id: UUID,
    ) -> list[StudentParentLink]:
        """Get all parent links for a student."""

        result = await db.execute(
            select(StudentParentLink)
            .options(selectinload(StudentParentLink.parent))
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.student_id == student_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_by_parent_id(
        db: AsyncSession,
        tenant_id: UUID,
        parent_id: UUID,
    ) -> list[StudentParentLink]:
        """Get all student links for a parent."""

        result = await db.execute(
            select(StudentParentLink)
            .options(
                selectinload(StudentParentLink.student),
                joinedload(StudentParentLink.parent),
            )
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.parent_id == parent_id,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_student_parent_link(
        db: AsyncSession,
        link: StudentParentLink,
    ) -> StudentParentLink:
        """Persist student-parent link updates."""

        await db.flush()
        await db.refresh(link)
        return link

    @staticmethod
    async def delete_student_parent_link(
        db: AsyncSession,
        link: StudentParentLink,
    ) -> None:
        """Delete a student-parent link."""

        await db.delete(link)
        await db.flush()


class StudentLinkCodeRepository:
    """Database operations for student link codes."""

    @staticmethod
    async def create(
        db: AsyncSession,
        link_code: StudentLinkCode,
    ) -> StudentLinkCode:
        """Create a student link code."""

        db.add(link_code)
        await db.flush()
        await db.refresh(link_code)
        return link_code

    @staticmethod
    async def get_code_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        link_code_id: UUID,
    ) -> StudentLinkCode | None:
        """Get a student link code by id within a tenant."""

        result = await db.execute(
            select(StudentLinkCode).where(
                StudentLinkCode.tenant_id == tenant_id,
                StudentLinkCode.id == link_code_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_code(
        db: AsyncSession,
        tenant_id: UUID,
        code: str,
    ) -> StudentLinkCode | None:
        """Get a student link code by code within a tenant."""

        result = await db.execute(
            select(StudentLinkCode).where(
                StudentLinkCode.tenant_id == tenant_id,
                StudentLinkCode.code == code,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_student_id(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentLinkCode]:
        """Get all link codes generated for a student."""

        result = await db.execute(
            select(StudentLinkCode)
            .where(
                StudentLinkCode.tenant_id == tenant_id,
                StudentLinkCode.student_id == student_id,
            )
            .order_by(StudentLinkCode.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        link_code: StudentLinkCode,
    ) -> StudentLinkCode:
        """Persist student link code updates."""

        await db.flush()
        await db.refresh(link_code)
        return link_code

    @staticmethod
    async def delete(
        db: AsyncSession,
        link_code: StudentLinkCode,
    ) -> None:
        """Delete a student link code."""

        await db.delete(link_code)
        await db.flush()


class StudentParentLinkRequestRepository:
    """Database operations for parent-student link requests."""

    @staticmethod
    async def create(
        db: AsyncSession,
        link_request: StudentParentLinkRequest,
    ) -> StudentParentLinkRequest:
        """Create a parent-student link request."""

        db.add(link_request)
        await db.flush()
        await db.refresh(link_request)
        return link_request

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        request_id: UUID,
        lock: bool = False,
    ) -> StudentParentLinkRequest | None:
        """Return a link request by ID within a tenant."""

        query = select(StudentParentLinkRequest).where(
            StudentParentLinkRequest.tenant_id == tenant_id,
            StudentParentLinkRequest.id == request_id,
        )

        if lock:
            query = query.with_for_update()
        else:
            query = query.options(
                joinedload(StudentParentLinkRequest.parent),
                joinedload(StudentParentLinkRequest.student),
            )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_pending_by_parent_and_student(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        parent_id: UUID,
        student_id: UUID,
    ) -> StudentParentLinkRequest | None:
        """Return an existing pending request for the parent/student pair."""

        result = await db.execute(
            select(StudentParentLinkRequest).where(
                StudentParentLinkRequest.tenant_id == tenant_id,
                StudentParentLinkRequest.parent_id == parent_id,
                StudentParentLinkRequest.student_id == student_id,
                StudentParentLinkRequest.status == StudentParentLinkRequestStatus.PENDING,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_parent_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        parent_id: UUID,
    ) -> list[StudentParentLinkRequest]:
        """Return link requests submitted by a parent."""

        result = await db.execute(
            select(StudentParentLinkRequest)
            .options(joinedload(StudentParentLinkRequest.student))
            .where(
                StudentParentLinkRequest.tenant_id == tenant_id,
                StudentParentLinkRequest.parent_id == parent_id,
            )
            .order_by(StudentParentLinkRequest.requested_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_by_student_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        status: StudentParentLinkRequestStatus | None = None,
    ) -> list[StudentParentLinkRequest]:
        """Return link requests addressed to a student."""

        query = (
            select(StudentParentLinkRequest)
            .options(joinedload(StudentParentLinkRequest.parent))
            .where(
                StudentParentLinkRequest.tenant_id == tenant_id,
                StudentParentLinkRequest.student_id == student_id,
            )
            .order_by(StudentParentLinkRequest.requested_at.desc())
        )

        if status is not None:
            query = query.where(StudentParentLinkRequest.status == status)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def save(
        db: AsyncSession,
        link_request: StudentParentLinkRequest,
    ) -> StudentParentLinkRequest:
        """Persist a link request update."""

        db.add(link_request)
        await db.flush()
        await db.refresh(link_request)
        return link_request


class StudentAccessCodeRepository:
    """Database operations for temporary student access codes."""

    @staticmethod
    async def invalidate_active_codes(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> None:
        """Invalidate all active access codes for a student."""

        now = datetime.now(timezone.utc)

        await db.execute(
            update(StudentAccessCode)
            .where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
                StudentAccessCode.is_used.is_(False),
            )
            .values(
                is_used=True,
                used_at=now,
            )
        )

    @staticmethod
    async def create_access_code(
        db: AsyncSession,
        *,
        access_code: StudentAccessCode,
    ) -> StudentAccessCode:
        """Create an access code record for a student."""

        db.add(access_code)
        await db.flush()
        await db.refresh(access_code)
        return access_code

    @staticmethod
    async def get_active_code_by_digest(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        code_digest: str,
    ) -> StudentAccessCode | None:
        """Fetch an active access code by its stored digest."""

        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(StudentAccessCode)
            .where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
                StudentAccessCode.code_digest == code_digest,
                StudentAccessCode.is_used.is_(False),
                StudentAccessCode.expires_at > now,
            )
            .order_by(StudentAccessCode.created_at.desc())
            .limit(1)
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def mark_all_codes_used(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> None:
        """Mark all active access codes for a student as used."""

        now = datetime.now(timezone.utc)

        await db.execute(
            update(StudentAccessCode)
            .where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
                StudentAccessCode.is_used.is_(False),
            )
            .values(
                is_used=True,
                used_at=now,
            )
        )
