from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.sync.models import (
    CBTSyncChange,
    CBTSyncTenantState,
)
from app.modules.cbt.sync.schemas import CBTSyncMutation


class CBTSyncRepository:
    """Persistence operations for the durable CBT synchronization log."""

    @staticmethod
    async def allocate_cursor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> int:
        """
        Allocate the next tenant-scoped sync cursor.

        The tenant state row is locked until the surrounding transaction
        commits or rolls back.
        """

        # Safely create the state row if this is the tenant's first sync event.
        stmt = (
            insert(CBTSyncTenantState)
            .values(
                tenant_id=tenant_id,
                last_cursor=0,
            )
            .on_conflict_do_nothing(index_elements=[CBTSyncTenantState.tenant_id])
        )

        await db.execute(stmt)

        # Serialize cursor allocation for this tenant only.
        result = await db.execute(
            select(CBTSyncTenantState)
            .where(CBTSyncTenantState.tenant_id == tenant_id)
            .with_for_update()
        )

        state = result.scalar_one()

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
        """Insert one durable CBT synchronization change."""

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
    async def get_change_by_id(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        change_id: uuid.UUID,
    ) -> CBTSyncChange | None:
        """
        Fetch one durable sync change belonging to a tenant.

        This will be used by the live-sync dispatcher after receiving
        a PostgreSQL NOTIFY containing the change ID.
        """

        result = await db.execute(
            select(CBTSyncChange).where(
                CBTSyncChange.id == change_id,
                CBTSyncChange.tenant_id == tenant_id,
            )
        )

        return result.scalar_one_or_none()

    @staticmethod
    async def get_changes_after(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        after_cursor: int,
        limit: int,
    ) -> list[CBTSyncChange]:
        """
        Return ordered CBT synchronization changes after a cursor.

        One extra row is fetched so the service layer can determine
        whether another recovery page exists.
        """

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
    async def get_latest_cursor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
    ) -> int:
        """
        Return the latest allocated synchronization cursor for a tenant.

        A tenant that has never produced a CBT sync event is at cursor 0.
        """

        result = await db.execute(
            select(CBTSyncTenantState.last_cursor).where(CBTSyncTenantState.tenant_id == tenant_id)
        )

        cursor = result.scalar_one_or_none()

        return cursor or 0
