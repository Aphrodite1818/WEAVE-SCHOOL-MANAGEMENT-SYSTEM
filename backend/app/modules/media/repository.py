# ============================ #
#     media/repository.py      #
# ============================ #

"""Data access layer for media asset metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
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


_PENDING_MEDIA_REPLACEMENTS_KEY = "media_pending_replacements"


class MediaAssetRepository:
    """Database operations for media asset metadata.

    This repository only manages database rows. It does not upload objects,
    delete storage objects, generate signed URLs, or validate files.
    """

    @staticmethod
    def _queue_pending_replacement(
        db: AsyncSession,
        *,
        replacement_id: UUID,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
    ) -> None:
        """Queue a replacement link until the replacement row has been flushed."""

        pending: dict[str, dict[str, Any]] = db.info.setdefault(
            _PENDING_MEDIA_REPLACEMENTS_KEY,
            {},
        )
        pending[str(replacement_id)] = {
            "tenant_id": tenant_id,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "purpose": purpose,
        }

    @staticmethod
    async def _apply_pending_replacement(
        db: AsyncSession,
        *,
        replacement_asset: MediaAsset,
    ) -> None:
        """Link replaced rows after the replacement asset exists in PostgreSQL."""

        pending: dict[str, dict[str, Any]] | None = db.info.get(
            _PENDING_MEDIA_REPLACEMENTS_KEY
        )
        if not pending:
            return

        context = pending.pop(str(replacement_asset.id), None)
        if context is None:
            return

        await db.execute(
            update(MediaAsset)
            .where(
                MediaAsset.tenant_id == context["tenant_id"],
                MediaAsset.owner_type == context["owner_type"],
                MediaAsset.owner_id == context["owner_id"],
                MediaAsset.purpose == context["purpose"],
                MediaAsset.status == MediaStatus.REPLACED,
                MediaAsset.is_current.is_(False),
                MediaAsset.replaced_by_media_asset_id.is_(None),
                MediaAsset.id != replacement_asset.id,
            )
            .values(replaced_by_media_asset_id=replacement_asset.id)
        )
        await db.flush()

        if not pending:
            db.info.pop(_PENDING_MEDIA_REPLACEMENTS_KEY, None)

    @staticmethod
    async def create_asset(
        db: AsyncSession,
        *,
        asset_data: MediaCreateData,
    ) -> MediaAsset:
        """Create and flush a media asset metadata row."""

        create_data = asset_data.model_dump(exclude_unset=True)

        # signed_url is response-only. It should not be persisted.
        create_data.pop("signed_url", None)

        media_asset = MediaAsset(**create_data)
        db.add(media_asset)
        await db.flush()

        # The service may mark the previous asset as replaced before this row is
        # inserted. Apply the self-referential FK only now, after this row exists.
        await MediaAssetRepository._apply_pending_replacement(
            db,
            replacement_asset=media_asset,
        )

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
        """Get a media asset by its storage object key within a tenant."""

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
        """Mark current active media assets as replaced.

        If the replacement row already exists, the self-referential foreign key
        is written immediately. If it does not exist yet, the relationship is
        queued and applied by ``create_asset`` after the replacement row has
        been inserted and flushed in the same session.
        """

        values: dict[str, object] = {
            "status": MediaStatus.REPLACED,
            "is_current": False,
        }

        if replaced_by_media_asset_id is not None:
            replacement_exists = await db.scalar(
                select(MediaAsset.id).where(
                    MediaAsset.id == replaced_by_media_asset_id,
                    MediaAsset.tenant_id == tenant_id,
                )
            )

            if replacement_exists is not None:
                values["replaced_by_media_asset_id"] = replaced_by_media_asset_id
            else:
                MediaAssetRepository._queue_pending_replacement(
                    db,
                    replacement_id=replaced_by_media_asset_id,
                    tenant_id=tenant_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    purpose=purpose,
                )

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

        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def soft_delete_asset(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> MediaAsset:
        """Soft-delete a media asset row."""

        media_asset.status = MediaStatus.DELETED
        media_asset.is_current = False
        media_asset.deleted_at = datetime.now(timezone.utc)

        await db.flush()
        await db.refresh(media_asset)
        return media_asset

    @staticmethod
    async def save(
        db: AsyncSession,
        *,
        media_asset: MediaAsset,
    ) -> MediaAsset:
        """Flush changes to an existing media asset."""

        await db.flush()
        await db.refresh(media_asset)
        return media_asset
