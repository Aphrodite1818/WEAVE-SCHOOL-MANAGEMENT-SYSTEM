# ======================================#
# backend.app.modules.cbt.sync.manager.py
# ======================================#

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass(slots=True)
class CBTMachineConnection:
    """Represent one currently connected local CBT server."""

    server_id: uuid.UUID
    tenant_id: uuid.UUID
    websocket: WebSocket

    # Prevent two coroutines from writing to the same socket simultaneously.
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CBTConnectionManager:
    """
    Maintain machine WebSocket connections owned by this API process.

    One CBT server may have only one active machine WebSocket on this
    process at a time.
    """

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, CBTMachineConnection] = {}

        # tenant_id -> connected server IDs
        self._tenant_servers: dict[uuid.UUID, set[uuid.UUID]] = {}

        # Protect modifications to the connection indexes.
        self._lock = asyncio.Lock()


        
    async def register(
        self,
        *,
        server_id: uuid.UUID,
        tenant_id: uuid.UUID,
        websocket: WebSocket,
    ) -> CBTMachineConnection:
        connection = CBTMachineConnection(
            server_id=server_id,
            tenant_id=tenant_id,
            websocket=websocket,
        )

        old_connection: CBTMachineConnection | None = None

        async with self._lock:
            old_connection = self._connections.get(server_id)

            if old_connection is not None:
                old_tenant_servers = self._tenant_servers.get(
                    old_connection.tenant_id
                )

                if old_tenant_servers is not None:
                    old_tenant_servers.discard(server_id)

                    if not old_tenant_servers:
                        self._tenant_servers.pop(
                            old_connection.tenant_id,
                            None,
                        )

            self._connections[server_id] = connection

            self._tenant_servers.setdefault(
                tenant_id,
                set(),
            ).add(server_id)

        # Never perform network I/O while holding the manager lock.
        if (
            old_connection is not None
            and old_connection.websocket is not websocket
        ):
            try:
                await old_connection.websocket.close(
                    code=4001,
                    reason="Connection replaced by a newer CBT session.",
                )
            except Exception:
                pass

        return connection




    async def unregister(
        self,
        *,
        server_id: uuid.UUID,
        websocket: WebSocket | None = None,
    ) -> None:
        """
        Remove a CBT machine connection.

        If websocket is supplied, only remove the connection if that exact
        socket is still the currently registered socket for the server.

        This prevents an old/stale socket from unregistering a newer
        replacement connection.
        """

        async with self._lock:
            connection = self._connections.get(server_id)

            if connection is None:
                return

            if (
                websocket is not None
                and connection.websocket is not websocket
            ):
                return

            self._connections.pop(server_id, None)

            tenant_servers = self._tenant_servers.get(
                connection.tenant_id
            )

            if tenant_servers is not None:
                tenant_servers.discard(server_id)

                if not tenant_servers:
                    self._tenant_servers.pop(
                        connection.tenant_id,
                        None,
                    )

    async def has_tenant_connections(
        self,
        tenant_id: uuid.UUID,
    ) -> bool:
        """Return whether this API process owns any CBT socket for a tenant."""

        async with self._lock:
            return bool(
                self._tenant_servers.get(tenant_id)
            )

    async def send_to_server(
        self,
        *,
        server_id: uuid.UUID,
        message: dict[str, Any],
    ) -> bool:
        """Send one message to a specific connected CBT server."""

        async with self._lock:
            connection = self._connections.get(server_id)

        if connection is None:
            return False

        try:
            async with connection.send_lock:
                await connection.websocket.send_json(message)

            return True

        except Exception:
            await self.unregister(
                server_id=server_id,
                websocket=connection.websocket,
            )
            return False

    async def send_to_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        message: dict[str, Any],
    ) -> int:
        """
        Send a synchronization message to every currently connected
        CBT server belonging to a tenant.

        Return the number of successful deliveries.
        """

        async with self._lock:
            server_ids = tuple(
                self._tenant_servers.get(
                    tenant_id,
                    set(),
                )
            )

        if not server_ids:
            return 0

        results = await asyncio.gather(
            *[
                self.send_to_server(
                    server_id=server_id,
                    message=message,
                )
                for server_id in server_ids
            ]
        )

        return sum(results)



    async def send_to_all(
        self,
        *,
        message: dict[str, object],
    ) -> int:
        """Send a control message to every CBT machine on this API process."""

        async with self._lock:
            server_ids = tuple(self._connections.keys())

        if not server_ids:
            return 0

        results = await asyncio.gather(
            *[
                self.send_to_server(
                    server_id=server_id,
                    message=message,
                )
                for server_id in server_ids
            ]
        )

        return sum(results)


cbt_connection_manager = CBTConnectionManager()