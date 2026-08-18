from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.sync.models import CBTSyncChange, CBTSyncTenantState
from app.modules.cbt.sync.schemas import CBTSyncMutation


class CBTSyncRepository:
    """Persistence operations for the durable CBT synchronization log."""

    @staticmethod
    async def allocate_cursor(db: AsyncSession, *, tenant_id: uuid.UUID) -> int:
        stmt = (
            insert(CBTSyncTenantState)
            .values(tenant_id=tenant_id, last_cursor=0)
            .on_conflict_do_nothing(index_elements=[CBTSyncTenantState.tenant_id])
        )
        await db.execute(stmt)
        state = (
            await db.execute(
                select(CBTSyncTenantState)
                .where(CBTSyncTenantState.tenant_id == tenant_id)
                .with_for_update()
            )
        ).scalar_one()
        state.last_cursor += 1
        await db.flush()
        return state.last_cursor

    @staticmethod
    async def create_change(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        cursor: int,
        mutation: CBTSyncMutation,
    ) -> CBTSyncChange:
        change = CBTSyncChange(
            tenant_id=tenant_id,
            cursor=cursor,
            entity_type=mutation.entity_type,
            entity_id=mutation.entity_id,
            operation=mutation.operation,
            schema_version=mutation.schema_version,
            payload=mutation.payload,
        )
        db.add(change)
        await db.flush()
        return change

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
            select(CBTSyncTenantState.last_cursor).where(
                CBTSyncTenantState.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none() or 0

    @staticmethod
    async def get_earliest_cursor(db: AsyncSession, *, tenant_id: uuid.UUID) -> int | None:
        return await db.scalar(
            select(func.min(CBTSyncChange.cursor)).where(
                CBTSyncChange.tenant_id == tenant_id
            )
        )

    @staticmethod
    async def prune_before(db: AsyncSession, *, cutoff: datetime) -> int:
        result = await db.execute(
            delete(CBTSyncChange).where(CBTSyncChange.created_at < cutoff)
        )
        return int(result.rowcount or 0)
