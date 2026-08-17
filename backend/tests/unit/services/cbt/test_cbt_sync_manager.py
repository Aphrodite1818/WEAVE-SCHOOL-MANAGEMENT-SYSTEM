from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.cbt.sync.manager import CBTConnectionManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.send_json = AsyncMock()
        self.close = AsyncMock()


@pytest.mark.asyncio
async def test_new_machine_session_replaces_old_socket_without_stale_unregister() -> None:
    manager = CBTConnectionManager()
    manager.ensure_authorized = AsyncMock(return_value=True)
    tenant_id = uuid4()
    server_id = uuid4()
    old_socket = FakeWebSocket()
    new_socket = FakeWebSocket()

    await manager.register(
        server_id=server_id,
        credential_id=uuid4(),
        tenant_id=tenant_id,
        websocket=old_socket,
    )
    await manager.register(
        server_id=server_id,
        credential_id=uuid4(),
        tenant_id=tenant_id,
        websocket=new_socket,
    )

    old_socket.close.assert_awaited_once()
    await manager.unregister(server_id=server_id, websocket=old_socket)

    assert await manager.has_tenant_connections(tenant_id) is True
    delivered = await manager.send_to_server(
        server_id=server_id,
        message={"type": "cbt.sync.change", "cursor": 7},
    )
    assert delivered is True
    new_socket.send_json.assert_awaited_once_with(
        {"type": "cbt.sync.change", "cursor": 7}
    )


@pytest.mark.asyncio
async def test_send_to_tenant_fans_out_only_to_that_tenants_servers() -> None:
    manager = CBTConnectionManager()
    manager.ensure_authorized = AsyncMock(return_value=True)
    tenant_a = uuid4()
    tenant_b = uuid4()
    socket_a1 = FakeWebSocket()
    socket_a2 = FakeWebSocket()
    socket_b = FakeWebSocket()

    await manager.register(
        server_id=uuid4(), credential_id=uuid4(), tenant_id=tenant_a, websocket=socket_a1
    )
    await manager.register(
        server_id=uuid4(), credential_id=uuid4(), tenant_id=tenant_a, websocket=socket_a2
    )
    await manager.register(
        server_id=uuid4(), credential_id=uuid4(), tenant_id=tenant_b, websocket=socket_b
    )

    delivered = await manager.send_to_tenant(
        tenant_id=tenant_a,
        message={"type": "cbt.sync.reconcile"},
    )

    assert delivered == 2
    socket_a1.send_json.assert_awaited_once()
    socket_a2.send_json.assert_awaited_once()
    socket_b.send_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_authorization_prevents_machine_delivery() -> None:
    manager = CBTConnectionManager()
    manager.ensure_authorized = AsyncMock(return_value=False)
    tenant_id = uuid4()
    server_id = uuid4()
    socket = FakeWebSocket()

    await manager.register(
        server_id=server_id,
        credential_id=uuid4(),
        tenant_id=tenant_id,
        websocket=socket,
    )

    delivered = await manager.send_to_server(
        server_id=server_id,
        message={"type": "cbt.sync.change"},
    )

    assert delivered is False
    socket.send_json.assert_not_awaited()
