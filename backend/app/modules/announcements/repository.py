#==========================#
#  Announcement Repository #
#==========================#

import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.announcements.models import (
    Announcement,
    AnnouncementRead,
    AnnouncementReadStatus,
    AnnouncementRecipientRole,
    AnnouncementStatus,
    AnnouncementTarget,
)


class AnnouncementRepository:
    """Low-level database operations for announcements."""

    @staticmethod
    async def create_announcement(
        db: AsyncSession,
        announcement: Announcement,
    ) -> Announcement:
        db.add(announcement)
        await db.flush()
        return announcement

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        announcement_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Announcement | None:
        query = (
            select(Announcement)
            .options(selectinload(Announcement.targets))
            .where(
                Announcement.tenant_id == tenant_id,
                Announcement.id == announcement_id,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_by_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        status: AnnouncementStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Announcement], int]:
        filters = [Announcement.tenant_id == tenant_id]

        if status is not None:
            filters.append(Announcement.status == status)

        count_stmt = (
            select(func.count())
            .select_from(Announcement)
            .where(*filters)
        )

        query = (
            select(Announcement)
            .options(selectinload(Announcement.targets))
            .where(*filters)
            .order_by(
                Announcement.is_pinned.desc(),
                Announcement.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )

        total_result = await db.execute(count_stmt)
        items_result = await db.execute(query)

        return (
            list(items_result.scalars().unique().all()),
            int(total_result.scalar_one()),
        )

    @staticmethod
    async def save(
        db: AsyncSession,
        announcement: Announcement,
    ) -> Announcement:
        await db.flush()
        await db.refresh(announcement)
        return announcement

    @staticmethod
    async def replace_targets(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        announcement_id: uuid.UUID,
        targets: list[AnnouncementTarget],
    ) -> list[AnnouncementTarget]:
        await db.execute(
            delete(AnnouncementTarget).where(
                AnnouncementTarget.tenant_id == tenant_id,
                AnnouncementTarget.announcement_id == announcement_id,
            )
        )

        for target in targets:
            db.add(target)

        await db.flush()
        return targets

    @staticmethod
    async def delete_announcement(
        db: AsyncSession,
        announcement: Announcement,
    ) -> None:
        await db.delete(announcement)
        await db.flush()


class AnnouncementReadRepository:
    """Low-level database operations for announcement read state."""

    @staticmethod
    async def get_read_state(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        announcement_id: uuid.UUID,
        actor_type: AnnouncementRecipientRole,
        actor_id: uuid.UUID,
    ) -> AnnouncementRead | None:
        stmt = select(AnnouncementRead).where(
            AnnouncementRead.tenant_id == tenant_id,
            AnnouncementRead.announcement_id == announcement_id,
            AnnouncementRead.actor_type == actor_type,
            AnnouncementRead.actor_id == actor_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_read_state(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        announcement_id: uuid.UUID,
        actor_type: AnnouncementRecipientRole,
        actor_id: uuid.UUID,
        status: AnnouncementReadStatus,
    ) -> AnnouncementRead:
        existing = await AnnouncementReadRepository.get_read_state(
            db=db,
            tenant_id=tenant_id,
            announcement_id=announcement_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )

        now = datetime.now(timezone.utc)

        if existing is None:
            existing = AnnouncementRead(
                tenant_id=tenant_id,
                announcement_id=announcement_id,
                actor_type=actor_type,
                actor_id=actor_id,
                status=status,
            )
            db.add(existing)

        existing.status = status

        if status in {
            AnnouncementReadStatus.READ,
            AnnouncementReadStatus.ACKNOWLEDGED,
            AnnouncementReadStatus.DELETED,
        }:
            existing.read_at = existing.read_at or now

        if status == AnnouncementReadStatus.ACKNOWLEDGED:
            existing.acknowledged_at = existing.acknowledged_at or now

        await db.flush()
        await db.refresh(existing)
        return existing
