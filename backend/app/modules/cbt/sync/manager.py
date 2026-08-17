"""Process-local CBT machine WebSocket connection manager."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket
from sqlalchemy import select

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.modules.cbt.enums import CBTServerStatus
from app.modules.cbt.models import CBTServer, CBTServerCredential

SEND_TIMEOUT_SECONDS = 8.0
AUTHORIZATION_CLOSE_CODE = 4403
logger = get_logger(__name__)


@dataclass(slots=True)
class CBTMachineConnection:
    server_id: uuid.UUID
    credential_id: uuid.UUID
    tenant_id: uuid.UUID
    websocket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class CBTConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, CBTMachineConnection] = {}
        self._tenant_servers: dict[uuid.UUID, set[uuid.UUID]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        server_id: uuid.UUID,
        credential_id: uuid.UUID,
        tenant_id: uuid.UUID,
        websocket: WebSocket,
    ) -> CBTMachineConnection:
        connection = CBTMachineConnection(
            server_id=server_id,
            credential_id=credential_id,
            tenant_id=tenant_id,
            websocket=websocket,
        )
        async with self._lock:
            old = self._connections.get(server_id)
            if old:
                old_ids = self._tenant_servers.get(old.tenant_id)
                if old_ids:
                    old_ids.discard(server_id)
                    if not old_ids:
                        self._tenant_servers.pop(old.tenant_id, None)
            self._connections[server_id] = connection
            self._tenant_servers.setdefault(tenant_id, set()).add(server_id)
        if old and old.websocket is not websocket:
            try:
                await old.websocket.close(
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
        async with self._lock:
            connection = self._connections.get(server_id)
            if not connection or (
                websocket is not None and connection.websocket is not websocket
            ):
                return
            self._connections.pop(server_id, None)
            ids = self._tenant_servers.get(connection.tenant_id)
            if ids:
                ids.discard(server_id)
                if not ids:
                    self._tenant_servers.pop(connection.tenant_id, None)

    async def has_tenant_connections(self, tenant_id: uuid.UUID) -> bool:
        async with self._lock:
            return bool(self._tenant_servers.get(tenant_id))

    @staticmethod
    async def _is_authorized(connection: CBTMachineConnection) -> bool:
        """Fail closed unless the exact credential that opened the socket is still valid."""

        try:
            async with AsyncSessionLocal() as db:
                resolved = (
                    await db.execute(
                        select(CBTServerCredential, CBTServer)
                        .join(CBTServer, CBTServer.id == CBTServerCredential.server_id)
                        .where(
                            CBTServerCredential.id == connection.credential_id,
                            CBTServerCredential.server_id == connection.server_id,
                            CBTServerCredential.revoked_at.is_(None),
                            CBTServer.id == connection.server_id,
                            CBTServer.tenant_id == connection.tenant_id,
                            CBTServer.status == CBTServerStatus.ACTIVE,
                            CBTServer.revoked_at.is_(None),
                        )
                    )
                ).first()
        except Exception:
            logger.exception(
                "Failed to revalidate CBT machine socket authorization.",
                extra={"cbt_server_id": str(connection.server_id)},
            )
            return False

        if resolved is None:
            return False
        credential, _server = resolved
        return credential.expires_at is None or credential.expires_at > datetime.now(timezone.utc)

    async def ensure_authorized(self, connection: CBTMachineConnection) -> bool:
        if await self._is_authorized(connection):
            return True
        await self.disconnect_server(
            connection.server_id,
            code=AUTHORIZATION_CLOSE_CODE,
            reason="CBT server authorization changed.",
        )
        return False

    async def send_to_server(
        self,
        *,
        server_id: uuid.UUID,
        message: dict[str, Any],
    ) -> bool:
        async with self._lock:
            connection = self._connections.get(server_id)
        if connection is None:
            return False
        if not await self.ensure_authorized(connection):
            return False
        try:
            async with connection.send_lock:
                await asyncio.wait_for(
                    connection.websocket.send_json(message),
                    timeout=SEND_TIMEOUT_SECONDS,
                )
            return True
        except Exception:
            await self.unregister(
                server_id=server_id,
                websocket=connection.websocket,
            )
            try:
                await connection.websocket.close(
                    code=1011,
                    reason="CBT sync delivery timed out.",
                )
            except Exception:
                pass
            return False

    async def send_to_tenant(
        self,
        *,
        tenant_id: uuid.UUID,
        message: dict[str, Any],
    ) -> int:
        async with self._lock:
            server_ids = tuple(self._tenant_servers.get(tenant_id, set()))
        if not server_ids:
            return 0
        results = await asyncio.gather(
            *(
                self.send_to_server(server_id=server_id, message=message)
                for server_id in server_ids
            )
        )
        return sum(results)

    async def send_to_all(self, *, message: dict[str, object]) -> int:
        async with self._lock:
            server_ids = tuple(self._connections.keys())
        if not server_ids:
            return 0
        results = await asyncio.gather(
            *(
                self.send_to_server(server_id=server_id, message=message)
                for server_id in server_ids
            )
        )
        return sum(results)

    async def disconnect_server(
        self,
        server_id: uuid.UUID,
        *,
        code: int = AUTHORIZATION_CLOSE_CODE,
        reason: str = "CBT server access changed.",
    ) -> bool:
        async with self._lock:
            connection = self._connections.get(server_id)
        if connection is None:
            return False
        await self.unregister(
            server_id=server_id,
            websocket=connection.websocket,
        )
        try:
            await connection.websocket.close(code=code, reason=reason)
        except Exception:
            pass
        return True


cbt_connection_manager = CBTConnectionManager()
