"""Durable CBT synchronization change recorder."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.modules.cbt.sync.models import CBTSyncChange, CBTSyncTenantState
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.cbt.sync.schemas import CBTSyncMutation, CBTSyncNotification

CBT_SYNC_NOTIFY_CHANNEL = "weave_cbt_sync"


class CBTSyncRecorder:
    """Record CBT-visible mutations inside the caller's business transaction.

    Neither entry point commits. ``record`` serves ordinary async application code;
    ``record_sync`` serves SQLAlchemy's synchronous Session event bridge used to
    capture domain mutations from both API and worker transactions.
    """

    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        mutation: CBTSyncMutation,
    ) -> CBTSyncChange:
        cursor = await CBTSyncRepository.allocate_cursor(db, tenant_id=tenant_id)
        change = await CBTSyncRepository.create_change(
            db,
            tenant_id=tenant_id,
            cursor=cursor,
            mutation=mutation,
        )
        notification = CBTSyncNotification(
            change_id=change.id,
            tenant_id=tenant_id,
            cursor=cursor,
        ).model_dump_json()
        await db.execute(select(func.pg_notify(CBT_SYNC_NOTIFY_CHANNEL, notification)))
        return change

    @staticmethod
    def record_sync(
        db: Session,
        *,
        tenant_id: uuid.UUID,
        mutation: CBTSyncMutation,
    ) -> tuple[uuid.UUID, int]:
        """Synchronous equivalent used from SQLAlchemy Session events.

        PostgreSQL row locking keeps each tenant cursor strictly ordered even when
        API and worker processes commit academic mutations concurrently.
        """

        connection = db.connection()
        if connection.dialect.name != "postgresql":
            raise RuntimeError("Durable CBT sync recording requires PostgreSQL.")

        state_table = CBTSyncTenantState.__table__
        change_table = CBTSyncChange.__table__
        connection.execute(
            pg_insert(state_table)
            .values(tenant_id=tenant_id, last_cursor=0)
            .on_conflict_do_nothing(index_elements=[state_table.c.tenant_id])
        )
        previous_cursor = connection.execute(
            select(state_table.c.last_cursor)
            .where(state_table.c.tenant_id == tenant_id)
            .with_for_update()
        ).scalar_one()
        cursor = int(previous_cursor) + 1
        change_id = uuid.uuid4()
        connection.execute(
            change_table.insert().values(
                id=change_id,
                tenant_id=tenant_id,
                cursor=cursor,
                entity_type=mutation.entity_type.value,
                entity_id=mutation.entity_id,
                operation=mutation.operation.value,
                schema_version=mutation.schema_version,
                payload=mutation.payload,
                created_at=func.now(),
                updated_at=func.now(),
            )
        )
        connection.execute(
            update(state_table)
            .where(state_table.c.tenant_id == tenant_id)
            .values(last_cursor=cursor, updated_at=func.now())
        )
        notification = CBTSyncNotification(
            change_id=change_id,
            tenant_id=tenant_id,
            cursor=cursor,
        ).model_dump_json()
        connection.execute(select(func.pg_notify(CBT_SYNC_NOTIFY_CHANNEL, notification)))
        return change_id, cursor
