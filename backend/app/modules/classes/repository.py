import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
from app.modules.classes.models import ClassRoom


class ClassRoomRepository:
    """Database layer for classroom records."""

    @staticmethod
    async def create_classroom(
        db: AsyncSession,
        class_room: ClassRoom,
    ) -> ClassRoom:
        """Create classroom within tenant scope."""

        db.add(class_room)
        await db.flush()
        await db.refresh(class_room)
        return class_room

    @staticmethod
    async def get_classroom_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> ClassRoom | None:
        """Get classroom by id within tenant scope."""

        result = await db.execute(
            select(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.id == class_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_classroom_by_normalized_name_and_arm(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_name: str,
        class_arm: str | None = None,
    ) -> ClassRoom | None:
        """Get a classroom by canonical name and optional arm within tenant scope."""

        normalized_name = normalized_class_name_key(class_name)
        normalized_arm = normalized_class_arm_key(class_arm)

        if normalized_name is None:
            return None

        result = await db.execute(
            select(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.normalized_name == normalized_name,
                ClassRoom.normalized_arm == normalized_arm,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_classroom_by_name_and_arm(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_name: str,
        class_arm: str | None = None,
    ) -> ClassRoom | None:
        """Compatibility wrapper for normalized classroom lookup."""

        return await ClassRoomRepository.get_classroom_by_normalized_name_and_arm(
            db=db,
            tenant_id=tenant_id,
            class_name=class_name,
            class_arm=class_arm,
        )

    @staticmethod
    async def get_all_classrooms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        limit: int = 100,
        skip: int = 0,
    ) -> list[ClassRoom]:
        """Get all classrooms within tenant scope."""

        result = await db.execute(
            select(ClassRoom)
            .where(ClassRoom.tenant_id == tenant_id)
            .order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_active_classrooms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        limit: int = 100,
        skip: int = 0,
    ) -> list[ClassRoom]:
        """Get active classrooms within tenant scope."""

        result = await db.execute(
            select(ClassRoom)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.is_active.is_(True),
            )
            .order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_classrooms_by_teacher_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
        *,
        limit: int = 100,
        skip: int = 0,
    ) -> list[ClassRoom]:
        """Get classrooms assigned to a specific teacher."""

        result = await db.execute(
            select(ClassRoom)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.teacher_id == teacher_id,
            )
            .order_by(ClassRoom.normalized_name.asc(), ClassRoom.normalized_arm.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_classrooms_by_ids(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_ids: list[uuid.UUID],
    ) -> list[ClassRoom]:
        """Get classrooms by IDs within tenant scope."""

        if not class_ids:
            return []

        result = await db.execute(
            select(ClassRoom).where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.id.in_(class_ids),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def update_classroom(
        db: AsyncSession,
        classroom: ClassRoom,
    ) -> ClassRoom:
        """Persist classroom updates."""

        db.add(classroom)
        await db.flush()
        await db.refresh(classroom)
        return classroom

    @staticmethod
    async def deactivate_classroom(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
    ) -> ClassRoom | None:
        """Soft-delete classroom by setting is_active to False."""

        classroom = await ClassRoomRepository.get_classroom_by_id(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            return None

        classroom.is_active = False
        await db.flush()
        await db.refresh(classroom)
        return classroom

    @staticmethod
    async def classroom_exists_by_name_and_arm(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_name: str,
        class_arm: str | None = None,
    ) -> bool:
        """Check whether classroom already exists by canonical name and arm."""

        classroom = await ClassRoomRepository.get_classroom_by_normalized_name_and_arm(
            db=db,
            tenant_id=tenant_id,
            class_name=class_name,
            class_arm=class_arm,
        )
        return classroom is not None
