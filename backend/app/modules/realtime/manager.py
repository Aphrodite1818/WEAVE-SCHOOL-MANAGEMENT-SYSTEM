# ===========================#
# modules.realtime.manager.py
# ===========================#


"""Process-local WebSocket connection manager."""

from __future__ import annotations

from datetime import datetime
import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import WebSocket

from app.modules.realtime.authentication import RealtimeIdentity
from app.modules.realtime.schemas import RealtimeAudience, RealtimeEvent


@dataclass
class RealtimeConnection:
    """
    Represents one authenticated WebSocket connection

    One actor may have multiple active connections
    """

    connection_id: UUID
    websocket: WebSocket
    actor_type: str
    actor_id: UUID
    tenant_id: UUID | None
    token_expires_at: datetime


class RealtimeConnectionManager:
    """
    Track Websocket connections owned by this API process.

    This manager does not handle:
    -authentication
    -Redis
    -domain events
    -persistence
    It  only knows which sockets are currently connected locally
    """

    def __init__(self):
        self._connections: dict[UUID, RealtimeConnection] = {}

        self._actor_connections: dict[tuple[str, UUID], set[UUID]] = {}

        self._tenant_connections: dict[UUID, set[UUID]] = {}

        self._lock = asyncio.Lock()

    async def register(
        self, websocket: WebSocket, *, identity: RealtimeIdentity
    ) -> RealtimeConnection:
        """
        Register one authenticated WebSocket connection
        """

        connection = RealtimeConnection(
            connection_id=uuid4(),
            websocket=websocket,
            actor_type=identity.actor_type,
            actor_id=identity.actor_id,
            tenant_id=identity.tenant_id,
            token_expires_at=identity.token_expires_at,
        )

        async with self._lock:
            self._connections[connection.connection_id] = connection

            actor_key = (connection.actor_type, connection.actor_id)

            self._actor_connections.setdefault(actor_key, set()).add(connection.connection_id)

            if connection.tenant_id is not None:
                self._tenant_connections.setdefault(connection.tenant_id, set()).add(
                    connection.connection_id
                )

        return connection

    async def unregister(self, connection_id: UUID) -> None:
        """
        Remove a Websocket connection from all indexes
        """

        async with self._lock:
            connection = self._connections.pop(connection_id, None)

            if connection is None:
                return

            actor_key = (connection.actor_type, connection.actor_id)

            actor_connections = self._actor_connections.get(actor_key)

            if actor_connections is not None:
                actor_connections.discard(connection_id)

                if not actor_connections:
                    self._actor_connections.pop(actor_key, None)

            if connection.tenant_id is not None:
                tenant_connections = self._tenant_connections.get(connection.tenant_id)

                if tenant_connections is not None:
                    tenant_connections.discard(connection_id)

                    if not tenant_connections:
                        self._tenant_connections.pop(connection.tenant_id, None)

    async def get_actor_connections(
        self, *, actor_type: str, actor_id: UUID
    ) -> list[RealtimeConnection]:
        """
        Return all local sockets belonging to one actor
        """

        async with self._lock:
            connection_ids = set(self._actor_connections.get((actor_type, actor_id), set()))

            return [
                self._connections[connection_id]
                for connection_id in connection_ids
                if connection_id in self._connections
            ]

    async def get_tenant_connections(self, *, tenant_id: UUID) -> list[RealtimeConnection]:
        """
        Return all local sockets belonging to one tenant
        """

        async with self._lock:
            connection_ids = set(self._tenant_connections.get(tenant_id, set()))

            return [
                self._connections[connection_id]
                for connection_id in connection_ids
                if connection_id in self._connections
            ]

    async def get_all_connections(
        self,
    ) -> list[RealtimeConnection]:
        """
        Return all sockets connected to this API process.
        """

        async with self._lock:
            return list(self._connections.values())

    async def dispatch(self, *, event: RealtimeEvent, audience: RealtimeAudience) -> None:
        """
        Deliver an event to matching sockets owned by this API process
        """

        if audience.kind == "actor":
            connections = await self.get_actor_connections(
                actor_type=audience.actor_type, actor_id=audience.actor_id
            )

        elif audience.kind == "tenant":
            connections = await self.get_tenant_connections(tenant_id=audience.tenant_id)

        else:
            connections = await self.get_all_connections()
        await self._send_to_connections(connections, event=event)

    async def _send_to_connections(
        self, connections: list[RealtimeConnection], *, event: RealtimeEvent
    ) -> None:
        """
        send one event to a collection of local connections.
        Failed / dead sockets are removed from the connection registry
        """

        if not connections:
            return

        payload = {
            "type": event.type,
            "event_id": str(event.event_id),
            "occurred_at": event.occurred_at.isoformat(),
            "data": event.data,
        }

        results = await asyncio.gather(
            *[connection.websocket.send_json(payload) for connection in connections],
            return_exceptions=True,
        )

        dead_connection_ids = [
            connection.connection_id
            for connection, result in zip(connections, results, strict=True)
            if isinstance(result, BaseException)
        ]
        await asyncio.gather(
            *(self.unregister(connection_id) for connection_id in dead_connection_ids)
        )

    async def refresh_identity(
        self,
        connection_id: UUID,
        *,
        identity: RealtimeIdentity,
    ) -> bool:
        """
        Refresh the authentication state of an existing connection.

        The refreshed token must belong to the exact same actor
        and tenant as the original WebSocket connection.
        """

        async with self._lock:
            connection = self._connections.get(connection_id)

            if connection is None:
                return False

            if (
                connection.actor_type != identity.actor_type
                or connection.actor_id != identity.actor_id
                or connection.tenant_id != identity.tenant_id
            ):
                return False

            connection.token_expires_at = identity.token_expires_at

            return True


realtime_manager = RealtimeConnectionManager()
