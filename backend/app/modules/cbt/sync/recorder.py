# ======================================#
# backend.app.modules.cbt.sync.recorder
# ======================================#

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.sync.models import CBTSyncChange
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.cbt.sync.schemas import CBTSyncMutation, CBTSyncNotification


CBT_SYNC_NOTIFY_CHANNEL = "weave_cbt_sync"


class CBTSyncRecorder:
    """
    Record durable CBT-visible mutations inside an existing
    business transaction.

    This class never commits the transaction.
    """

    @staticmethod
    async def record(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        mutation: CBTSyncMutation,
    ) -> CBTSyncChange:
        # 1. Allocate the next ordered cursor for this tenant.
        cursor = await CBTSyncRepository.allocate_cursor(
            db,
            tenant_id=tenant_id,
        )

        # 2. Persist exactly what changed for CBT synchronization.
        change = await CBTSyncRepository.create_change(
            db,
            tenant_id=tenant_id,
            cursor=cursor,
            mutation=mutation,
        )

        # 3. Build a lightweight wake-up message.
        #
        # This is NOT the actual sync payload sent to the CBT server.
        # The listener will use change_id to load the durable
        # CBTSyncChange row after the transaction commits.
        notification = CBTSyncNotification(
            change_id=change.id,
            tenant_id=tenant_id,
            cursor=cursor,
        ).model_dump_json()

        # 4. Schedule a PostgreSQL NOTIFY.
        #
        # PostgreSQL only delivers this notification if the surrounding
        # transaction commits successfully.
        await db.execute(
            select(
                func.pg_notify(
                    CBT_SYNC_NOTIFY_CHANNEL,
                    notification,
                )
            )
        )

        return change
