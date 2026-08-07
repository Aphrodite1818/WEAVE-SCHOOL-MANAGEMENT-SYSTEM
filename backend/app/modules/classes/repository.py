"""Tenant-scoped classroom repository."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.normalization import (
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.modules.classes.models import ClassRoom

if TYPE_CHECKING:
    from app.modules.students.models import AcademicStatus


class ClassRoomRepository:
    @staticmethod
    async def add(db: AsyncSession, classroom: ClassRoom) -> ClassRoom:
        db.add(classroom)
        await db.flush()
        return classroom

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ClassRoom | None:
        query = select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.id == class_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_name_and_arm(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_name: str,
        class_arm: str | None = None,
    ) -> ClassRoom | None:
        normalized_name = normalized_class_name_key(class_name)
        if normalized_name is None:
            return None
        result = await db.execute(
            select(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.normalized_name == normalized_name,
                ClassRoom.normalized_arm == normalized_class_arm_key(class_arm),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
        offset: int = 0,
        limit: int = 100,
        include_archived: bool = False,
    ) -> list[ClassRoom]:
        query = select(ClassRoom).where(ClassRoom.tenant_id == tenant_id)
        if active_only:
            query = query.where(
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )

        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
        result = await db.execute(
            query.order_by(
                ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc()
            )
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_by_teacher_membership(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> list[ClassRoom]:
        query = (
            select(ClassRoom)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.teacher_membership_id == teacher_membership_id,
            )
            .order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
        )
        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_by_ids(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_ids: list[uuid.UUID],
        *,
        lock: bool = False,
        include_archived: bool = False,
    ) -> list[ClassRoom]:
        if not class_ids:
            return []
        query = select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.id.in_(class_ids),
        )
        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_progression_chain_rows(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> list[ClassRoom]:
        query = (
            select(ClassRoom)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )
            .order_by(ClassRoom.id)
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_current_students(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> int:
        from app.modules.students.models import Student

        result = await db.execute(
            select(func.count())
            .select_from(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.is_archived.is_(False),
            )
        )
        return result.scalar_one()

    @staticmethod
    async def count_assigned_students_by_status(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        status: "AcademicStatus",
    ) -> int:
        from app.modules.students.models import Student

        result = await db.execute(
            select(func.count())
            .select_from(Student)
            .where(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.status == status,
                Student.is_archived.is_(False),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_current_enrollments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> int:
        from app.modules.students.models import StudentEnrollment

        result = await db.execute(
            select(func.count())
            .select_from(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.class_id == class_id,
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.ended_on.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_active_class_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> int:
        from app.modules.student_academics.models import ClassSubject

        result = await db.execute(
            select(func.count())
            .select_from(ClassSubject)
            .where(
                ClassSubject.tenant_id == tenant_id,
                ClassSubject.class_id == class_id,
                ClassSubject.is_active.is_(True),
                ClassSubject.archived_at.is_(None),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_active_teacher_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> int:
        from app.modules.student_academics.models import ClassSubject, TeacherAssignment

        result = await db.execute(
            select(func.count())
            .select_from(TeacherAssignment)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.effective_to.is_(None),
                TeacherAssignment.class_subject_id.in_(
                    select(ClassSubject.id).where(
                        ClassSubject.tenant_id == tenant_id,
                        ClassSubject.class_id == class_id,
                    )
                ),
            )
        )
        return int(result.scalar_one() or 0)

    @staticmethod
    async def count_class_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> dict[str, int]:
        from app.modules.attendance.models import (
            StudentAttendanceSheet,
            TemporaryAttendanceAssignment,
        )
        from app.modules.communications.models import AnnouncementAudience
        from app.modules.report_cards.models import ReportCard
        from app.modules.student_academics.models import (
            ClassSubject,
            StudentProgressionItem,
            StudentSubjectResult,
            TeacherAssignment,
        )
        from app.modules.students.models import Student, StudentEnrollment

        student_count = (
            await db.execute(
                select(func.count())
                .select_from(Student)
                .where(
                    Student.tenant_id == tenant_id,
                    Student.class_id == class_id,
                )
            )
        ).scalar_one()
        enrollment_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentEnrollment)
                .where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.class_id == class_id,
                )
            )
        ).scalar_one()
        teacher_assignment_count = (
            await db.execute(
                select(func.count())
                .select_from(TeacherAssignment)
                .join(
                    ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id
                )
                .where(
                    TeacherAssignment.tenant_id == tenant_id,
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                )
            )
        ).scalar_one()
        result_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentSubjectResult)
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.class_id == class_id,
                )
            )
        ).scalar_one()
        report_card_count = (
            await db.execute(
                select(func.count())
                .select_from(ReportCard)
                .where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.class_id == class_id,
                )
            )
        ).scalar_one()
        progression_item_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentProgressionItem)
                .where(
                    StudentProgressionItem.tenant_id == tenant_id,
                    or_(
                        StudentProgressionItem.from_class_id == class_id,
                        StudentProgressionItem.to_class_id == class_id,
                    ),
                )
            )
        ).scalar_one()
        attendance_sheet_count = (
            await db.execute(
                select(func.count())
                .select_from(StudentAttendanceSheet)
                .where(
                    StudentAttendanceSheet.tenant_id == tenant_id,
                    StudentAttendanceSheet.class_id == class_id,
                )
            )
        ).scalar_one()
        temporary_assignment_count = (
            await db.execute(
                select(func.count())
                .select_from(TemporaryAttendanceAssignment)
                .where(
                    TemporaryAttendanceAssignment.tenant_id == tenant_id,
                    TemporaryAttendanceAssignment.class_id == class_id,
                )
            )
        ).scalar_one()
        announcement_audience_count = (
            await db.execute(
                select(func.count())
                .select_from(AnnouncementAudience)
                .where(
                    AnnouncementAudience.tenant_id == tenant_id,
                    AnnouncementAudience.class_id == class_id,
                )
            )
        ).scalar_one()
        return {
            "students": int(student_count),
            "enrollments": int(enrollment_count),
            "teacher_assignments": int(teacher_assignment_count),
            "results": int(result_count),
            "report_cards": int(report_card_count),
            "progression_items": int(progression_item_count),
            "attendance_sheets": int(attendance_sheet_count),
            "temporary_attendance_assignments": int(temporary_assignment_count),
            "announcement_audiences": int(announcement_audience_count),
        }

    @staticmethod
    async def clear_next_class_references(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> None:
        await db.execute(
            update(ClassRoom)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.next_class_id == class_id,
            )
            .values(next_class_id=None, is_terminal=False)
        )
        await db.flush()

    @staticmethod
    async def save(db: AsyncSession, classroom: ClassRoom) -> ClassRoom:
        db.add(classroom)
        await db.flush()
        return classroom

    @staticmethod
    async def delete_classroom(db: AsyncSession, classroom: ClassRoom) -> None:
        await db.delete(classroom)
        await db.flush()
