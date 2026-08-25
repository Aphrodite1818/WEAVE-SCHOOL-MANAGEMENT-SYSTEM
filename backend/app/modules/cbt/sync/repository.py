from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.sync.models import CBTSyncChange, CBTSyncTenantState


class CBTSyncRepository:
    """Read/recovery/retention operations for the durable CBT synchronization log."""

    @staticmethod
    async def get_changes_after(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        after_cursor: int,
        limit: int,
    ) -> list[CBTSyncChange]:
        result = await db.execute(
            select(CBTSyncChange)
            .where(
                CBTSyncChange.tenant_id == tenant_id,
                CBTSyncChange.cursor > after_cursor,
            )
            .order_by(CBTSyncChange.cursor.asc())
            .limit(limit + 1)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_latest_cursor(db: AsyncSession, *, tenant_id: uuid.UUID) -> int:
        result = await db.execute(
            select(CBTSyncTenantState.last_cursor).where(CBTSyncTenantState.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none() or 0

    @staticmethod
    async def get_earliest_cursor(db: AsyncSession, *, tenant_id: uuid.UUID) -> int | None:
        return await db.scalar(
            select(func.min(CBTSyncChange.cursor)).where(CBTSyncChange.tenant_id == tenant_id)
        )

    @staticmethod
    async def prune_before(db: AsyncSession, *, cutoff: datetime) -> int:
        result = await db.execute(delete(CBTSyncChange).where(CBTSyncChange.created_at < cutoff))
        return int(result.rowcount or 0)
