"""Batched read-model queries for student list endpoints."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ForbiddenException
from app.modules.classes.models import AcademicLevel, ClassRoom
from app.modules.parents.models import ParentMembership
from app.modules.student_academics.models import AcademicSession
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import (
    AcademicStatus,
    StudentEnrollment,
    StudentParentLinkStatus,
)
from app.modules.students.repository import StudentParentLinkRepository, StudentRepository
from app.modules.students.schemas import StudentDetailResponse, StudentResponse


class StudentReadService:
    """Build student list responses with bounded tenant-scoped batch reads."""

    @staticmethod
    async def list_students(
        db: AsyncSession,
        actor: ParentMembership | object,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple[list[StudentDetailResponse], int]:
        tenant_id = getattr(actor, "tenant_id", None)
        if tenant_id is None:
            raise ForbiddenException("Actor has no tenant context.")

        students, total = await StudentRepository.list_for_tenant(
            db,
            tenant_id,
            search=search,
            class_id=class_id,
            status=status,
            offset=skip,
            limit=min(limit, 100),
        )
        if isinstance(actor, ParentMembership):
            links = await StudentParentLinkRepository.list_for_membership(
                db,
                tenant_id,
                actor.id,
                statuses=[
                    StudentParentLinkStatus.ACTIVE,
                    StudentParentLinkStatus.READ_ONLY,
                    StudentParentLinkStatus.ALUMNI_READ_ONLY,
                ],
            )
            allowed = {link.student_id for link in links}
            students = [student for student in students if student.id in allowed]
            total = len(students)

        if not students:
            return [], total

        student_ids = {student.id for student in students}
        enrollments = list(
            (
                await db.execute(
                    select(StudentEnrollment).where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.student_id.in_(student_ids),
                        StudentEnrollment.is_current.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        enrollment_by_student = {row.student_id: row for row in enrollments}

        class_ids = {row.class_id for row in enrollments if row.class_id is not None}
        classrooms = (
            list(
                (
                    await db.execute(
                        select(ClassRoom)
                        .options(
                            joinedload(ClassRoom.academic_level),
                            joinedload(ClassRoom.arm_label_ref),
                        )
                        .where(
                            ClassRoom.tenant_id == tenant_id,
                            ClassRoom.id.in_(class_ids),
                        )
                    )
                )
                .scalars()
                .unique()
                .all()
            )
            if class_ids
            else []
        )
        classroom_by_id = {row.id: row for row in classrooms}

        level_ids = {row.academic_level_id for row in enrollments}
        levels = (
            list(
                (
                    await db.execute(
                        select(AcademicLevel).where(
                            AcademicLevel.tenant_id == tenant_id,
                            AcademicLevel.id.in_(level_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if level_ids
            else []
        )
        level_by_id = {row.id: row for row in levels}

        session_ids = {row.academic_session_id for row in enrollments}
        sessions = (
            list(
                (
                    await db.execute(
                        select(AcademicSession).where(
                            AcademicSession.tenant_id == tenant_id,
                            AcademicSession.id.in_(session_ids),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if session_ids
            else []
        )
        session_by_id = {row.id: row for row in sessions}
        fallback_session = await StudentAcademicRepository.get_current_academic_session(
            db,
            tenant_id,
        )
        current_term = await StudentAcademicRepository.get_current_term(db, tenant_id)

        items: list[StudentDetailResponse] = []
        for student in students:
            enrollment = enrollment_by_student.get(student.id)
            classroom = (
                classroom_by_id.get(enrollment.class_id)
                if enrollment is not None and enrollment.class_id is not None
                else None
            )
            level = (
                level_by_id.get(enrollment.academic_level_id)
                if enrollment is not None
                else None
            )
            session = (
                session_by_id.get(enrollment.academic_session_id)
                if enrollment is not None
                else None
            ) or fallback_session

            student_data = StudentResponse.model_validate(student).model_dump()
            student_data["class_id"] = enrollment.class_id if enrollment else None
            student_data["academic_level_id"] = (
                enrollment.academic_level_id if enrollment else None
            )
            items.append(
                StudentDetailResponse(
                    **student_data,
                    class_name=classroom.academic_level_name if classroom else None,
                    class_arm=classroom.arm if classroom else None,
                    academic_level_name=level.name if level else None,
                    current_enrollment_id=enrollment.id if enrollment else None,
                    current_academic_session_id=session.id if session else None,
                    current_academic_session_name=session.name if session else None,
                    current_academic_term_id=current_term.id if current_term else None,
                    current_academic_term_name=(
                        current_term.name.value
                        if current_term and current_term.name
                        else None
                    ),
                )
            )

        return items, total