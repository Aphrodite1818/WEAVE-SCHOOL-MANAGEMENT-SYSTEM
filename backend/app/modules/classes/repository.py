"""Tenant-scoped classroom repository."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
from app.modules.classes.models import ClassRoom


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
            query.order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
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
        query = select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.teacher_membership_id == teacher_membership_id,
        ).order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
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
        query = select(ClassRoom).where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.is_active.is_(True),
            ClassRoom.archived_at.is_(None),
        ).order_by(ClassRoom.id)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count_current_students(db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID) -> int:
        from app.modules.students.models import Student

        result = await db.execute(
            select(func.count()).select_from(Student).where(
                Student.tenant_id == tenant_id,
                Student.class_id == class_id,
                Student.is_archived.is_(False),
            )
        )
        return result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, classroom: ClassRoom) -> ClassRoom:
        db.add(classroom)
        await db.flush()
        return classroom
