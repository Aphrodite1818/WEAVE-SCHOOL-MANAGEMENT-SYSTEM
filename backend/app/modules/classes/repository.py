"""Tenant-scoped classroom repository."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.utils.normalization import (
    normalized_class_arm_key,
    normalized_class_name_key,
)
from app.modules.classes.models import AcademicLevel, ClassRoom, ProgressionSelectionOption

if TYPE_CHECKING:
    from app.modules.students.models import AcademicStatus


class AcademicLevelRepository:
    @staticmethod
    async def add(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicLevel | None:
        query = select(AcademicLevel).where(
            AcademicLevel.tenant_id == tenant_id,
            AcademicLevel.id == academic_level_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_name(
        db: AsyncSession, tenant_id: uuid.UUID, name: str
    ) -> AcademicLevel | None:
        normalized_name = normalized_class_name_key(name)
        if normalized_name is None:
            return None
        return (
            await db.execute(
                select(AcademicLevel).where(
                    AcademicLevel.tenant_id == tenant_id,
                    AcademicLevel.normalized_name == normalized_name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[AcademicLevel]:
        query = select(AcademicLevel).where(AcademicLevel.tenant_id == tenant_id)
        if active_only:
            query = query.where(
                AcademicLevel.is_active.is_(True), AcademicLevel.archived_at.is_(None)
            )
        elif not include_archived:
            query = query.where(AcademicLevel.archived_at.is_(None))
        result = await db.execute(query.order_by(AcademicLevel.normalized_name.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def save(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    @staticmethod
    async def list_progression_options(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        source_level_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> list[ProgressionSelectionOption]:
        query = select(ProgressionSelectionOption).where(
            ProgressionSelectionOption.tenant_id == tenant_id,
            ProgressionSelectionOption.source_level_id == source_level_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query.order_by(ProgressionSelectionOption.created_at.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def list_progression_edges(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Return source-to-level edges for both level and classroom destinations."""

        result = await db.execute(
            select(
                ProgressionSelectionOption.source_level_id,
                ProgressionSelectionOption.target_level_id,
                ClassRoom.academic_level_id,
            )
            .outerjoin(
                ClassRoom,
                (
                    ProgressionSelectionOption.target_classroom_id == ClassRoom.id
                )
                & (ClassRoom.tenant_id == tenant_id),
            )
            .where(ProgressionSelectionOption.tenant_id == tenant_id)
        )
        return [
            (source_id, target_level_id or classroom_level_id)
            for source_id, target_level_id, classroom_level_id in result.all()
            if target_level_id or classroom_level_id
        ]

    @staticmethod
    async def replace_progression_options(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        source_level_id: uuid.UUID,
        options: list[ProgressionSelectionOption],
    ) -> list[ProgressionSelectionOption]:
        await db.execute(
            delete(ProgressionSelectionOption).where(
                ProgressionSelectionOption.tenant_id == tenant_id,
                ProgressionSelectionOption.source_level_id == source_level_id,
            )
        )
        db.add_all(options)
        await db.flush()
        return options

    @staticmethod
    async def count_setup_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
    ) -> dict[str, int]:
        from app.modules.student_academics.models import LevelSubject

        classroom_count = (
            await db.execute(
                select(func.count())
                .select_from(ClassRoom)
                .where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.academic_level_id == academic_level_id,
                )
            )
        ).scalar_one()
        previous_level_count = (
            await db.execute(
                select(func.count())
                .select_from(AcademicLevel)
                .where(
                    AcademicLevel.tenant_id == tenant_id,
                    AcademicLevel.next_level_id == academic_level_id,
                )
            )
        ).scalar_one()
        level_subject_count = (
            await db.execute(
                select(func.count())
                .select_from(LevelSubject)
                .where(
                    LevelSubject.tenant_id == tenant_id,
                    LevelSubject.academic_level_id == academic_level_id,
                )
            )
        ).scalar_one()
        selection_option_count = (
            await db.execute(
                select(func.count())
                .select_from(ProgressionSelectionOption)
                .where(
                    ProgressionSelectionOption.tenant_id == tenant_id,
                    ProgressionSelectionOption.target_level_id == academic_level_id,
                )
            )
        ).scalar_one()
        return {
            "classrooms": int(classroom_count),
            "previous_levels": int(previous_level_count),
            "level_subjects": int(level_subject_count),
            "progression_selection_options": int(selection_option_count),
        }

    @staticmethod
    async def delete(db: AsyncSession, level: AcademicLevel) -> None:
        await db.delete(level)
        await db.flush()


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
        query = (
            select(ClassRoom)
            .options(selectinload(ClassRoom.academic_level))
            .where(ClassRoom.tenant_id == tenant_id, ClassRoom.id == class_id)
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_level_and_arm(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        class_arm: str,
    ) -> ClassRoom | None:
        result = await db.execute(
            select(ClassRoom)
            .options(selectinload(ClassRoom.academic_level))
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.academic_level_id == academic_level_id,
                ClassRoom.normalized_arm == normalized_class_arm_key(class_arm),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_active_for_level(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> list[ClassRoom]:
        query = (
            select(ClassRoom)
            .options(selectinload(ClassRoom.academic_level))
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.academic_level_id == academic_level_id,
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )
            .order_by(ClassRoom.normalized_arm.asc())
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

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
        query = (
            select(ClassRoom)
            .options(selectinload(ClassRoom.academic_level))
            .where(ClassRoom.tenant_id == tenant_id)
        )
        if active_only:
            query = query.where(
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            )

        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
        result = await db.execute(
            query.join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
            .order_by(AcademicLevel.normalized_name.asc(), ClassRoom.normalized_arm.asc())
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
            .options(selectinload(ClassRoom.academic_level))
            .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.teacher_membership_id == teacher_membership_id,
            )
            .order_by(AcademicLevel.normalized_name.asc(), ClassRoom.normalized_arm.asc())
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
        query = (
            select(ClassRoom)
            .options(selectinload(ClassRoom.academic_level))
            .where(ClassRoom.tenant_id == tenant_id, ClassRoom.id.in_(class_ids))
        )
        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
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
    async def count_active_teacher_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> int:
        from app.modules.student_academics.models import TeacherAssignment

        result = await db.execute(
            select(func.count())
            .select_from(TeacherAssignment)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.effective_to.is_(None),
                TeacherAssignment.class_id == class_id,
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
                .where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.class_id == class_id,
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
                        StudentProgressionItem.selected_classroom_id == class_id,
                    ),
                )
            )
        ).scalar_one()
        progression_option_count = (
            await db.execute(
                select(func.count())
                .select_from(ProgressionSelectionOption)
                .where(
                    ProgressionSelectionOption.tenant_id == tenant_id,
                    ProgressionSelectionOption.target_classroom_id == class_id,
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
            "progression_selection_options": int(progression_option_count),
            "attendance_sheets": int(attendance_sheet_count),
            "temporary_attendance_assignments": int(temporary_assignment_count),
            "announcement_audiences": int(announcement_audience_count),
        }

    @staticmethod
    async def save(db: AsyncSession, classroom: ClassRoom) -> ClassRoom:
        db.add(classroom)
        await db.flush()
        return classroom

    @staticmethod
    async def delete_classroom(db: AsyncSession, classroom: ClassRoom) -> None:
        await db.delete(classroom)
        await db.flush()
