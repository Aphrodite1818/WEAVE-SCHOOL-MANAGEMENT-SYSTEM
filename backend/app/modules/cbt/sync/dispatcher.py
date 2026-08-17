# ======================================#
# backend.app.modules.cbt.sync.dispatcher
# ======================================#

from __future__ import annotations

import uuid

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.modules.cbt.sync.manager import cbt_connection_manager
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.cbt.sync.service import CBTSyncService


logger = get_logger(__name__)


class CBTSyncDispatcher:
    """
    Dispatch committed CBT sync changes to CBT machines connected
    to this API process.

    Durable recovery remains PostgreSQL-backed. Failure to deliver
    a live WebSocket event does not delete or alter the sync change.
    """

    @staticmethod
    async def dispatch(
        *,
        tenant_id: uuid.UUID,
        change_id: uuid.UUID,
    ) -> int:
        """
        Deliver one committed sync change to currently connected
        CBT servers for the tenant.

        Returns the number of successful live deliveries.
        """

        # Avoid a database lookup if this API instance does not own
        # any CBT machine socket for this tenant.
        has_connections = await cbt_connection_manager.has_tenant_connections(tenant_id)

        if not has_connections:
            return 0

        # Use a short-lived database session only to load the
        # committed durable change.
        async with AsyncSessionLocal() as db:
            change = await CBTSyncRepository.get_change_by_id(
                db,
                tenant_id=tenant_id,
                change_id=change_id,
            )

        if change is None:
            logger.warning(
                "CBT sync change %s for tenant %s was not found.",
                change_id,
                tenant_id,
            )
            return 0

        serialized = CBTSyncService.serialize_change(change)

        message = {
            "type": "cbt.sync.change",
            "change": serialized.model_dump(mode="json"),
        }

        delivered = await cbt_connection_manager.send_to_tenant(
            tenant_id=tenant_id,
            message=message,
        )

        return delivered
