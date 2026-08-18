"""Durable, batched CBT synchronization change recorder."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.cbt.sync.models import CBTSyncChange, CBTSyncTenantState
from app.modules.cbt.sync.schemas import CBTSyncMutation, CBTSyncNotification

CBT_SYNC_NOTIFY_CHANNEL = "weave_cbt_sync"


class CBTSyncRecorder:
    """Append one transaction's CBT mutations with one cursor lock and one NOTIFY.

    Business data and sync-log writes share the caller's transaction. A commit
    publishes both; a rollback publishes neither. Cursors are allocated as one
    contiguous range so high-volume worker/admin writes do not repeatedly lock the
    tenant cursor row.
    """

    @staticmethod
    def record_many_sync(
        db: Session,
        *,
        tenant_id: uuid.UUID,
        mutations: Sequence[CBTSyncMutation],
    ) -> tuple[int, int] | None:
        if not mutations:
            return None

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

        first_cursor = int(previous_cursor) + 1
        rows = [
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_id,
                "cursor": first_cursor + index,
                "entity_type": mutation.entity_type.value,
                "entity_id": mutation.entity_id,
                "operation": mutation.operation.value,
                "schema_version": mutation.schema_version,
                "payload": mutation.payload,
            }
            for index, mutation in enumerate(mutations)
        ]

        # created_at/updated_at are intentionally omitted here so PostgreSQL uses
        # the table's timestamp defaults instead of receiving SQL expressions as
        # asyncpg executemany parameter values.
        connection.execute(change_table.insert(), rows)
        last_cursor = first_cursor + len(rows) - 1
        connection.execute(
            update(state_table)
            .where(state_table.c.tenant_id == tenant_id)
            .values(last_cursor=last_cursor, updated_at=func.now())
        )
        notification = CBTSyncNotification(
            tenant_id=tenant_id,
            cursor=last_cursor,
        ).model_dump_json()
        connection.execute(select(func.pg_notify(CBT_SYNC_NOTIFY_CHANNEL, notification)))
        return first_cursor, last_cursor
