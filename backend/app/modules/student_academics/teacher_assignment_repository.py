"""Repositories for class-head and class-subject teacher membership assignments."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import ClassRoom
from app.modules.student_academics.models import ClassSubjectTeacher, TeacherAssignment


class TeacherAssignmentRepository:
    @staticmethod
    async def add(db: AsyncSession, assignment: TeacherAssignment) -> TeacherAssignment:
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def get_active_for_class_subject(
        db: AsyncSession,
        tenant_id: UUID,
        class_subject_id: UUID,
        *,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        query = select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
            TeacherAssignment.is_active.is_(True),
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_active_for_membership(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_membership_id: UUID,
        *,
        lock: bool = False,
    ) -> list[TeacherAssignment]:
        query = select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.teacher_membership_id == teacher_membership_id,
            TeacherAssignment.is_active.is_(True),
        ).order_by(TeacherAssignment.created_at.asc())
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_active_for_membership(db: AsyncSession, tenant_id: UUID, teacher_membership_id: UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(TeacherAssignment).where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.teacher_membership_id == teacher_membership_id,
                TeacherAssignment.is_active.is_(True),
            )
        )
        return result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, assignment: TeacherAssignment) -> TeacherAssignment:
        db.add(assignment)
        await db.flush()
        return assignment


class ClassSubjectTeacherRepository:
    @staticmethod
    async def add(db: AsyncSession, assignment: ClassSubjectTeacher) -> ClassSubjectTeacher:
        db.add(assignment)
        await db.flush()
        return assignment

    @staticmethod
    async def get_by_class_subject(
        db: AsyncSession,
        tenant_id: UUID,
        class_id: UUID,
        subject_id: UUID,
        *,
        lock: bool = False,
    ) -> ClassSubjectTeacher | None:
        query = select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.tenant_id == tenant_id,
            ClassSubjectTeacher.class_id == class_id,
            ClassSubjectTeacher.subject_id == subject_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_active_for_membership(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_membership_id: UUID,
        *,
        lock: bool = False,
    ) -> list[ClassSubjectTeacher]:
        query = select(ClassSubjectTeacher).where(
            ClassSubjectTeacher.tenant_id == tenant_id,
            ClassSubjectTeacher.teacher_membership_id == teacher_membership_id,
            ClassSubjectTeacher.is_active.is_(True),
        ).order_by(ClassSubjectTeacher.created_at.asc())
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_active_for_membership(db: AsyncSession, tenant_id: UUID, teacher_membership_id: UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(ClassSubjectTeacher).where(
                ClassSubjectTeacher.tenant_id == tenant_id,
                ClassSubjectTeacher.teacher_membership_id == teacher_membership_id,
                ClassSubjectTeacher.is_active.is_(True),
            )
        )
        return result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, assignment: ClassSubjectTeacher) -> ClassSubjectTeacher:
        db.add(assignment)
        await db.flush()
        return assignment


class ClassHeadAssignmentRepository:
    @staticmethod
    async def list_active_for_membership(
        db: AsyncSession,
        tenant_id: UUID,
        teacher_membership_id: UUID,
        *,
        lock: bool = False,
    ) -> list[ClassRoom]:
        query = select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.teacher_membership_id == teacher_membership_id,
            ClassRoom.is_active.is_(True),
        ).order_by(ClassRoom.id)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_active_for_membership(db: AsyncSession, tenant_id: UUID, teacher_membership_id: UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.teacher_membership_id == teacher_membership_id,
                ClassRoom.is_active.is_(True),
            )
        )
        return result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, classroom: ClassRoom) -> ClassRoom:
        db.add(classroom)
        await db.flush()
        return classroom
