"""Low-latency cursor high-water dispatch for connected CBT machines."""

from __future__ import annotations

import uuid

from app.modules.cbt.sync.manager import cbt_connection_manager


class CBTSyncDispatcher:
    """Wake connected CBT machines without duplicating durable entity payloads."""

    @staticmethod
    async def dispatch(*, tenant_id: uuid.UUID, cursor: int) -> int:
        if not await cbt_connection_manager.has_tenant_connections(tenant_id):
            return 0
        return await cbt_connection_manager.send_to_tenant(
            tenant_id=tenant_id,
            message={"type": "cbt.sync.available", "cursor": cursor},
        )
