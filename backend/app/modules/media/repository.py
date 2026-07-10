#==========================#
#     media.repository     #
#==========================#
"""Data access layer for the media module.

This file will contain the persistence operations for media records so
services do not need to talk to the database directly.
"""






# ============================ #
#     media/repository.py      #
# ============================ #



from  __future__  import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import (
    MediaAsset,
    MediaOwnerType,
    MediaPurpose,
    MediaStatus,
    MediaVisibility,
)
from app.modules.media.schemas import MediaAssetFilter, MediaCreateData


class MediaAssetRepository:
    """Database operations for media asset metadata.

    This repository only manages database rows. It does not upload to R2,
    delete R2 objects, generate signed URLs, or validate files.
    """

    @staticmethod
    async def create_asset(
        db: AsyncSession,
        *,
        asset_data: MediaCreateData,
    ) -> MediaAsset:
        """Create a new media asset metadata row."""

        create_data = asset_data.model_dump(exclude_unset=True)

        # signed_url is response-only. It should not be persisted.
        create_data.pop("signed_url", None)

        media_asset = MediaAsset(**create_data)

        db.add(media_asset)
        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        media_asset_id: UUID,
        include_deleted: bool = False,
        lock: bool = False,
    ) -> MediaAsset | None:
        """Get a media asset by ID within a tenant."""

        conditions = [
            MediaAsset.tenant_id == tenant_id,
            MediaAsset.id == media_asset_id,
        ]

        if not include_deleted:
            conditions.append(MediaAsset.status != MediaStatus.DELETED)
            conditions.append(MediaAsset.deleted_at.is_(None))

        query = select(MediaAsset).where(*conditions)

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_current_for_owner(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
        visibility: MediaVisibility | None = None,
        lock: bool = False,
    ) -> MediaAsset | None:
        """Get the current active media asset for an owner and purpose."""

        conditions = [
            MediaAsset.tenant_id == tenant_id,
            MediaAsset.owner_type == owner_type,
            MediaAsset.owner_id == owner_id,
            MediaAsset.purpose == purpose,
            MediaAsset.status == MediaStatus.ACTIVE,
            MediaAsset.is_current.is_(True),
            MediaAsset.deleted_at.is_(None),
        ]

        if visibility is not None:
            conditions.append(MediaAsset.visibility == visibility)

        query = (
            select(MediaAsset)
            .where(*conditions)
            .order_by(MediaAsset.created_at.desc())
            .limit(1)
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_assets(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filters: MediaAssetFilter | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[MediaAsset], int]:
        """List media assets for a tenant with optional filters."""

        conditions = [MediaAsset.tenant_id == tenant_id]

        if filters is not None:
            if filters.owner_type is not None:
                conditions.append(MediaAsset.owner_type == filters.owner_type)

            if filters.owner_id is not None:
                conditions.append(MediaAsset.owner_id == filters.owner_id)

            if filters.purpose is not None:
                conditions.append(MediaAsset.purpose == filters.purpose)

            if filters.visibility is not None:
                conditions.append(MediaAsset.visibility == filters.visibility)

            if filters.status is not None:
                conditions.append(MediaAsset.status == filters.status)

            if filters.current_only:
                conditions.append(MediaAsset.is_current.is_(True))

        result = await db.execute(
            select(MediaAsset)
            .where(*conditions)
            .order_by(MediaAsset.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(result.scalars().all())

        total_result = await db.execute(
            select(func.count()).select_from(MediaAsset).where(*conditions)
        )
        total = total_result.scalar_one()

        return items, total

    @staticmethod
    async def get_by_object_key(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        object_key: str,
        include_deleted: bool = False,
    ) -> MediaAsset | None:
        """Get a media asset by its R2 object key within a tenant."""

        conditions = [
            MediaAsset.tenant_id == tenant_id,
            MediaAsset.object_key == object_key,
        ]

        if not include_deleted:
            conditions.append(MediaAsset.status != MediaStatus.DELETED)
            conditions.append(MediaAsset.deleted_at.is_(None))

        result = await db.execute(select(MediaAsset).where(*conditions))
        return result.scalar_one_or_none()

    @staticmethod
    async def mark_current_assets_as_replaced(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
        replaced_by_media_asset_id: UUID | None = None,
    ) -> int:
        """Mark current active media assets for an owner/purpose as replaced.

        Use this before or after creating a new current asset, depending on
        the service flow. This keeps historical records without deleting rows.
        """

        values: dict[str, object] = {
            "status": MediaStatus.REPLACED,
            "is_current": False,
        }

        if replaced_by_media_asset_id is not None:
            values["replaced_by_media_asset_id"] = replaced_by_media_asset_id

        result = await db.execute(
            update(MediaAsset)
            .where(
                MediaAsset.tenant_id == tenant_id,
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
                MediaAsset.purpose == purpose,
                MediaAsset.status == MediaStatus.ACTIVE,
                MediaAsset.is_current.is_(True),
                MediaAsset.deleted_at.is_(None),
            )
            .values(**values)
        )

        await db.flush()
        return int(result.rowcount or 0)

    @staticmethod
    async def mark_asset_as_current(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> MediaAsset:
        """Mark a media asset as the active current asset."""

        media_asset.status = MediaStatus.ACTIVE
        media_asset.is_current = True
        media_asset.deleted_at = None

        db.add(media_asset)
        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def soft_delete_asset(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> MediaAsset:
        """Soft-delete a media asset metadata row."""

        media_asset.status = MediaStatus.DELETED
        media_asset.is_current = False
        media_asset.deleted_at = datetime.now(timezone.utc)

        db.add(media_asset)
        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def soft_delete_current_for_owner(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
    ) -> int:
        """Soft-delete the current media asset for an owner and purpose."""

        result = await db.execute(
            update(MediaAsset)
            .where(
                MediaAsset.tenant_id == tenant_id,
                MediaAsset.owner_type == owner_type,
                MediaAsset.owner_id == owner_id,
                MediaAsset.purpose == purpose,
                MediaAsset.status == MediaStatus.ACTIVE,
                MediaAsset.is_current.is_(True),
                MediaAsset.deleted_at.is_(None),
            )
            .values(
                status=MediaStatus.DELETED,
                is_current=False,
                deleted_at=datetime.now(timezone.utc),
            )
        )

        await db.flush()
        return int(result.rowcount or 0)

    @staticmethod
    async def save(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> MediaAsset:
        """Persist changes to a media asset."""

        db.add(media_asset)
        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def hard_delete_asset(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> None:
        """Hard-delete a media asset metadata row.

        Use rarely. Prefer soft_delete_asset so audit/history is preserved.
        This does not delete the physical R2 object.
        """

        await db.delete(media_asset)
        await db.flush()