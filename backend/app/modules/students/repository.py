"""Repositories for students, enrollments, access codes, and parent links."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.parents.models import ParentMembership
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccessCode,
    StudentEnrollment,
    StudentParentLink,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentParentLinkStatus,
)


class StudentRepository:
    @staticmethod
    async def add(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        db.add(student)
        await db.flush()
        return student

    @staticmethod
    async def create_student(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        return await StudentRepository.add(db, student)

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_or_student_id: UUID,
        student_id: UUID | None = None,
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> Student | None:
        """Load a student using a scoped or session-bound primary key."""

        tenant_id = tenant_or_student_id if student_id is not None else None
        resolved_student_id = student_id or tenant_or_student_id
        filters = [Student.id == resolved_student_id]
        if tenant_id is not None:
            filters.append(Student.tenant_id == tenant_id)
        if not include_archived:
            filters.append(Student.is_archived.is_(False))

        query = select(Student).where(*filters)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_student_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> Student | None:
        return await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            lock=lock,
            include_archived=include_archived,
        )

    @staticmethod
    async def get_by_admission_number(
        db: AsyncSession,
        tenant_id: UUID,
        admission_number: str,
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> Student | None:
        filters = [
            Student.tenant_id == tenant_id,
            Student.admission_number == admission_number.strip().upper(),
        ]
        if not include_archived:
            filters.append(Student.is_archived.is_(False))
        query = select(Student).where(*filters)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def admission_number_exists(
        db: AsyncSession,
        tenant_id: UUID,
        admission_number: str,
    ) -> bool:
        result = await db.execute(
            select(Student.id).where(
                Student.tenant_id == tenant_id,
                Student.admission_number == admission_number.strip().upper(),
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
        include_archived: bool = False,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Student], int]:
        filters = [Student.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Student.is_archived.is_(False))
        if class_id is not None:
            filters.append(Student.class_id == class_id)
        if status is not None:
            filters.append(Student.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Student.first_name.ilike(pattern),
                    Student.last_name.ilike(pattern),
                    Student.admission_number.ilike(pattern),
                )
            )

        total = (
            await db.execute(select(func.count()).select_from(Student).where(*filters))
        ).scalar_one()
        result = await db.execute(
            select(Student)
            .where(*filters)
            .order_by(Student.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

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
        return await StudentRepository.list_for_tenant(
            db,
            tenant_id,
            search=search,
            class_id=class_id,
            status=status,
            offset=skip,
            limit=limit,
        )

    @staticmethod
    async def list_progression_candidates(
        db: AsyncSession,
        tenant_id: UUID,
        class_id: UUID,
        *,
        lock: bool = False,
    ) -> list[Student]:
        query = (
            select(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.status.in_([AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED]),
                Student.promotion_hold.is_(False),
                Student.is_archived.is_(False),
            )
            .order_by(Student.id)
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def save(
        db: AsyncSession,
        student: Student,
    ) -> Student:
        db.add(student)
        await db.flush()
        return student

    @staticmethod
    async def hard_delete(
        db: AsyncSession,
        student: Student,
    ) -> None:
        await db.delete(student)
        await db.flush()


class StudentEnrollmentRepository:
    @staticmethod
    async def add(
        db: AsyncSession,
        enrollment: StudentEnrollment,
    ) -> StudentEnrollment:
        db.add(enrollment)
        await db.flush()
        return enrollment

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        enrollment_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(
            StudentEnrollment.tenant_id == tenant_id,
            StudentEnrollment.id == enrollment_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_current(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentEnrollment | None:
        query = select(StudentEnrollment).where(
            StudentEnrollment.tenant_id == tenant_id,
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.is_current.is_(True),
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentEnrollment]:
        result = await db.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.student_id == student_id,
            )
            .order_by(
                StudentEnrollment.started_on.asc(),
                StudentEnrollment.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_current_for_class_session(
        db: AsyncSession,
        tenant_id: UUID,
        class_id: UUID,
        academic_session_id: UUID,
        *,
        lock: bool = False,
    ) -> list[StudentEnrollment]:
        query = (
            select(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.class_id == class_id,
                StudentEnrollment.academic_session_id == academic_session_id,
                StudentEnrollment.is_current.is_(True),
            )
            .order_by(StudentEnrollment.student_id)
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def count_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.student_id == student_id,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def save(
        db: AsyncSession,
        enrollment: StudentEnrollment,
    ) -> StudentEnrollment:
        db.add(enrollment)
        await db.flush()
        return enrollment


class StudentAccessCodeRepository:
    @staticmethod
    async def add(
        db: AsyncSession,
        access_code: StudentAccessCode,
    ) -> StudentAccessCode:
        db.add(access_code)
        await db.flush()
        return access_code

    @staticmethod
    async def list_active_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> list[StudentAccessCode]:
        now = datetime.now(timezone.utc)
        query = (
            select(StudentAccessCode)
            .where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
                StudentAccessCode.is_used.is_(False),
                StudentAccessCode.expires_at > now,
            )
            .order_by(StudentAccessCode.created_at.desc())
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def get_by_digest(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        code_digest: str,
        *,
        lock: bool = False,
        require_active: bool = True,
    ) -> StudentAccessCode | None:
        filters = [
            StudentAccessCode.tenant_id == tenant_id,
            StudentAccessCode.student_id == student_id,
            StudentAccessCode.code_digest == code_digest,
        ]
        if require_active:
            filters.extend(
                [
                    StudentAccessCode.is_used.is_(False),
                    StudentAccessCode.expires_at > datetime.now(timezone.utc),
                ]
            )
        query = select(StudentAccessCode).where(*filters)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_active_code_by_digest(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        code_digest: str,
    ) -> StudentAccessCode | None:
        return await StudentAccessCodeRepository.get_by_digest(
            db,
            tenant_id,
            student_id,
            code_digest,
            require_active=True,
        )

    @staticmethod
    async def mark_all_codes_used(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        codes = await StudentAccessCodeRepository.list_active_for_student(
            db,
            tenant_id,
            student_id,
            lock=True,
        )
        now = datetime.now(timezone.utc)
        for code in codes:
            code.is_used = True
            code.used_at = now
            db.add(code)
        await db.flush()
        return len(codes)

    @staticmethod
    async def count_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(StudentAccessCode)
            .where(
                StudentAccessCode.tenant_id == tenant_id,
                StudentAccessCode.student_id == student_id,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def save(
        db: AsyncSession,
        access_code: StudentAccessCode,
    ) -> StudentAccessCode:
        db.add(access_code)
        await db.flush()
        return access_code


class StudentParentLinkRepository:
    @staticmethod
    async def add(
        db: AsyncSession,
        link: StudentParentLink,
    ) -> StudentParentLink:
        db.add(link)
        await db.flush()
        return link

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        link_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentParentLink | None:
        query = select(StudentParentLink).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.id == link_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_student_and_membership(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        membership_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentParentLink | None:
        query = select(StudentParentLink).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.student_id == student_id,
            StudentParentLink.parent_membership_id == membership_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        *,
        statuses: list[StudentParentLinkStatus] | None = None,
        lock: bool = False,
    ) -> list[StudentParentLink]:
        query = select(StudentParentLink).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.student_id == student_id,
        )
        if statuses:
            query = query.where(StudentParentLink.status.in_(statuses))
        query = query.options(
            joinedload(
                StudentParentLink.parent_membership,
            ).joinedload(ParentMembership.parent_account)
        ).order_by(StudentParentLink.created_at.asc())
        if lock:
            query = query.with_for_update(of=StudentParentLink)
        return list((await db.execute(query)).scalars().unique().all())

    @staticmethod
    async def list_for_membership(
        db: AsyncSession,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        statuses: list[StudentParentLinkStatus] | None = None,
        lock: bool = False,
    ) -> list[StudentParentLink]:
        query = select(StudentParentLink).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.parent_membership_id == membership_id,
        )
        if statuses:
            query = query.where(StudentParentLink.status.in_(statuses))
        query = query.options(joinedload(StudentParentLink.student)).order_by(
            StudentParentLink.created_at.asc()
        )
        if lock:
            query = query.with_for_update(of=StudentParentLink)
        return list((await db.execute(query)).scalars().unique().all())

    @staticmethod
    async def get_by_parent_id(
        db: AsyncSession,
        tenant_id: UUID,
        parent_id: UUID,
    ) -> list[StudentParentLink]:
        return await StudentParentLinkRepository.list_for_membership(
            db,
            tenant_id,
            parent_id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
            ],
        )

    @staticmethod
    async def count_usable_guardians(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(StudentParentLink)
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.student_id == student_id,
                StudentParentLink.status.in_(
                    [
                        StudentParentLinkStatus.ACTIVE,
                        StudentParentLinkStatus.READ_ONLY,
                        StudentParentLinkStatus.ALUMNI_READ_ONLY,
                    ]
                ),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(StudentParentLink)
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.student_id == student_id,
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def save(
        db: AsyncSession,
        link: StudentParentLink,
    ) -> StudentParentLink:
        db.add(link)
        await db.flush()
        return link


class StudentParentLinkRequestRepository:
    @staticmethod
    async def add(
        db: AsyncSession,
        request: StudentParentLinkRequest,
    ) -> StudentParentLinkRequest:
        db.add(request)
        await db.flush()
        await db.refresh(request)
        return request

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        request_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentParentLinkRequest | None:
        query = select(StudentParentLinkRequest).where(
            StudentParentLinkRequest.tenant_id == tenant_id,
            StudentParentLinkRequest.id == request_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_invitation(
        db: AsyncSession,
        invitation_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentParentLinkRequest | None:
        query = select(StudentParentLinkRequest).where(
            StudentParentLinkRequest.invitation_id == invitation_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_pending_for_student(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentParentLinkRequest]:
        result = await db.execute(
            select(StudentParentLinkRequest)
            .options(joinedload(StudentParentLinkRequest.parent_membership))
            .where(
                StudentParentLinkRequest.tenant_id == tenant_id,
                StudentParentLinkRequest.student_id == student_id,
                StudentParentLinkRequest.status
                == StudentParentLinkRequestStatus.PENDING,
            )
            .order_by(StudentParentLinkRequest.requested_at.asc())
        )
        return list(result.scalars().unique().all())

    @staticmethod
    async def list_pending_for_tenant(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[StudentParentLinkRequest], int]:
        filters = [
            StudentParentLinkRequest.tenant_id == tenant_id,
            StudentParentLinkRequest.status == StudentParentLinkRequestStatus.PENDING,
        ]
        total = (
            await db.execute(
                select(func.count())
                .select_from(StudentParentLinkRequest)
                .where(*filters)
            )
        ).scalar_one()
        result = await db.execute(
            select(StudentParentLinkRequest)
            .where(*filters)
            .order_by(StudentParentLinkRequest.requested_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def save(
        db: AsyncSession,
        request: StudentParentLinkRequest,
    ) -> StudentParentLinkRequest:
        db.add(request)
        await db.flush()
        await db.refresh(request)
        return request
