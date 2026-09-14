"""Application service for durable CBT incremental synchronization."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.sync.models import CBTSyncChange
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.cbt.sync.schemas import CBTSyncChangeResponse, CBTSyncDeltaResponse


class CBTSyncCursorExpired(RuntimeError):
    """The caller is older than the retained delta window and must bootstrap."""


class CBTSyncService:
    DEFAULT_PAGE_SIZE = 500
    MAX_PAGE_SIZE = 1000

    @staticmethod
    def serialize_change(change: CBTSyncChange) -> CBTSyncChangeResponse:
        return CBTSyncChangeResponse(
            event_id=change.id,
            cursor=change.cursor,
            entity_type=change.entity_type,
            entity_id=change.entity_id,
            operation=change.operation,
            schema_version=change.schema_version,
            payload=change.payload,
            occurred_at=change.created_at,
        )

    @classmethod
    async def get_changes_after(
        cls,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        after_cursor: int,
        limit: int = DEFAULT_PAGE_SIZE,
    ) -> CBTSyncDeltaResponse:
        if after_cursor < 0:
            raise ValueError("after_cursor cannot be negative")
        if limit < 1:
            raise ValueError("limit must be at least 1")

        limit = min(limit, cls.MAX_PAGE_SIZE)
        latest_cursor = await CBTSyncRepository.get_latest_cursor(
            db,
            tenant_id=tenant_id,
        )
        earliest_cursor = await CBTSyncRepository.get_earliest_cursor(
            db,
            tenant_id=tenant_id,
        )
        if latest_cursor > after_cursor and (
            earliest_cursor is None or after_cursor < earliest_cursor - 1
        ):
            raise CBTSyncCursorExpired(
                "CBT synchronization cursor is older than the retained change log."
            )

        rows = await CBTSyncRepository.get_changes_after(
            db,
            tenant_id=tenant_id,
            after_cursor=after_cursor,
            limit=limit,
        )
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        changes = [cls.serialize_change(change) for change in page_rows]
        next_cursor = page_rows[-1].cursor if page_rows else after_cursor

        return CBTSyncDeltaResponse(
            from_cursor=after_cursor,
            next_cursor=next_cursor,
            has_more=has_more,
            changes=changes,
        )

    @staticmethod
    async def get_latest_cursor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> int:
        return await CBTSyncRepository.get_latest_cursor(db, tenant_id=tenant_id)
