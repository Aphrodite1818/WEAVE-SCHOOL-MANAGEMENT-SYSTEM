from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect
from jose import jwt
from pydantic import ValidationError

from app.config.settings import settings
from app.core.dependencies.route_guards import _validate_session
from app.core.exceptions import UnauthorizedException
from app.modules.auth.models import AuthSessionActorType
from app.modules.realtime.authentication import (
    RealtimeIdentity,
    authenticate_realtime_access_token,
)
from app.modules.realtime.broker import REALTIME_CHANNEL, RealtimeRedisBroker
from app.modules.realtime.manager import RealtimeConnectionManager
from app.modules.realtime.publisher import RealtimePublisher
from app.modules.realtime.schemas import (
    RealtimeAudience,
    RealtimeBrokerMessage,
    RealtimeEvent,
)


class FakeWebSocket:
    def __init__(self, frames: list[dict] | None = None, *, fail_send: bool = False):
        self.frames = list(frames or [])
        self.fail_send = fail_send
        self.accepted = False
        self.sent: list[dict] = []
        self.closed: list[tuple[int, str | None]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_json(self) -> dict:
        if not self.frames:
            raise WebSocketDisconnect(code=1000)
        return self.frames.pop(0)

    async def send_json(self, payload: dict) -> None:
        if self.fail_send:
            raise RuntimeError("socket failed")
        self.sent.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed.append((code, reason))


class ConcurrentWriteDetectingSocket(FakeWebSocket):
    def __init__(self):
        super().__init__()
        self.active_writes = 0
        self.max_active_writes = 0

    async def send_json(self, payload: dict) -> None:
        self.active_writes += 1
        self.max_active_writes = max(self.max_active_writes, self.active_writes)
        await asyncio.sleep(0.01)
        self.sent.append(payload)
        self.active_writes -= 1


def identity(
    *,
    actor_id=None,
    tenant_id=None,
    actor_type: str = "teacher",
    expires_in_minutes: int = 5,
) -> RealtimeIdentity:
    return RealtimeIdentity(
        actor_type=actor_type,
        actor_id=actor_id or uuid4(),
        tenant_id=tenant_id,
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes),
    )


def actor_message(*, actor_id=None) -> RealtimeBrokerMessage:
    return RealtimeBrokerMessage(
        event=RealtimeEvent(type="notification.created", data={"id": "notification-1"}),
        audience=RealtimeAudience(
            kind="actor",
            actor_type="teacher",
            actor_id=actor_id or uuid4(),
        ),
    )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"kind": "actor"}, "actor_type and actor_id"),
        ({"kind": "tenant"}, "tenant_id"),
        (
            {"kind": "broadcast", "tenant_id": uuid4()},
            "cannot include actor or tenant routing fields",
        ),
    ],
)
def test_realtime_audience_rejects_incomplete_or_leaking_routes(payload, message):
    with pytest.raises(ValidationError, match=message):
        RealtimeAudience(**payload)


async def test_manager_supports_multiple_actor_connections_and_unregisters_indexes():
    manager = RealtimeConnectionManager()
    actor_id = uuid4()
    tenant_id = uuid4()
    first = await manager.register(
        FakeWebSocket(), identity=identity(actor_id=actor_id, tenant_id=tenant_id)
    )
    second = await manager.register(
        FakeWebSocket(), identity=identity(actor_id=actor_id, tenant_id=tenant_id)
    )

    assert {
        item.connection_id
        for item in await manager.get_actor_connections(actor_type="teacher", actor_id=actor_id)
    } == {
        first.connection_id,
        second.connection_id,
    }

    await manager.unregister(first.connection_id)
    await manager.unregister(second.connection_id)
    assert await manager.get_actor_connections(actor_type="teacher", actor_id=actor_id) == []
    assert await manager.get_tenant_connections(tenant_id=tenant_id) == []
    assert await manager.get_all_connections() == []


async def test_manager_dispatches_to_actor_tenant_and_broadcast_targets_only():
    manager = RealtimeConnectionManager()
    tenant_one, tenant_two = uuid4(), uuid4()
    actor_one, actor_two = uuid4(), uuid4()
    sockets = [FakeWebSocket(), FakeWebSocket(), FakeWebSocket()]
    await manager.register(sockets[0], identity=identity(actor_id=actor_one, tenant_id=tenant_one))
    await manager.register(sockets[1], identity=identity(actor_id=actor_two, tenant_id=tenant_one))
    await manager.register(sockets[2], identity=identity(actor_id=uuid4(), tenant_id=tenant_two))
    event = RealtimeEvent(type="notification.created")

    await manager.dispatch(
        event=event,
        audience=RealtimeAudience(kind="actor", actor_type="teacher", actor_id=actor_one),
    )
    assert [len(socket.sent) for socket in sockets] == [1, 0, 0]

    await manager.dispatch(
        event=event,
        audience=RealtimeAudience(kind="tenant", tenant_id=tenant_one),
    )
    assert [len(socket.sent) for socket in sockets] == [2, 1, 0]

    await manager.dispatch(event=event, audience=RealtimeAudience(kind="broadcast"))
    assert [len(socket.sent) for socket in sockets] == [3, 2, 1]
    assert sockets[0].sent[0]["occurred_at"] == event.occurred_at.isoformat()
    assert "audience" not in sockets[0].sent[0]


async def test_actor_event_with_tenant_context_cannot_cross_tenant_boundary():
    manager = RealtimeConnectionManager()
    actor_id = uuid4()
    tenant_one, tenant_two = uuid4(), uuid4()
    tenant_one_socket, tenant_two_socket = FakeWebSocket(), FakeWebSocket()
    await manager.register(
        tenant_one_socket,
        identity=identity(actor_id=actor_id, tenant_id=tenant_one),
    )
    await manager.register(
        tenant_two_socket,
        identity=identity(actor_id=actor_id, tenant_id=tenant_two),
    )

    await manager.dispatch(
        event=RealtimeEvent(type="notification.created"),
        audience=RealtimeAudience(
            kind="actor",
            actor_type="teacher",
            actor_id=actor_id,
            tenant_id=tenant_one,
        ),
    )

    assert len(tenant_one_socket.sent) == 1
    assert tenant_two_socket.sent == []


async def test_manager_cleans_up_failed_sockets_without_blocking_healthy_sockets():
    manager = RealtimeConnectionManager()
    tenant_id = uuid4()
    healthy, failed = FakeWebSocket(), FakeWebSocket(fail_send=True)
    await manager.register(healthy, identity=identity(tenant_id=tenant_id))
    failed_connection = await manager.register(failed, identity=identity(tenant_id=tenant_id))

    await manager.dispatch(
        event=RealtimeEvent(type="notification.created"),
        audience=RealtimeAudience(kind="tenant", tenant_id=tenant_id),
    )

    assert len(healthy.sent) == 1
    assert failed_connection.connection_id not in {
        item.connection_id for item in await manager.get_all_connections()
    }


async def test_manager_serializes_application_and_control_frames_per_socket():
    manager = RealtimeConnectionManager()
    actor_id = uuid4()
    socket = ConcurrentWriteDetectingSocket()
    connection = await manager.register(socket, identity=identity(actor_id=actor_id))

    await asyncio.gather(
        manager.dispatch(
            event=RealtimeEvent(type="notification.created"),
            audience=RealtimeAudience(kind="actor", actor_type="teacher", actor_id=actor_id),
        ),
        manager.send_json(connection.connection_id, {"type": "pong"}),
    )

    assert socket.max_active_writes == 1
    assert len(socket.sent) == 2


async def test_manager_refresh_rejects_identity_switching():
    manager = RealtimeConnectionManager()
    original = identity(tenant_id=uuid4())
    connection = await manager.register(FakeWebSocket(), identity=original)

    assert not await manager.refresh_identity(
        connection.connection_id,
        identity=identity(actor_id=uuid4(), tenant_id=original.tenant_id),
    )
    refreshed = identity(actor_id=original.actor_id, tenant_id=original.tenant_id)
    assert await manager.refresh_identity(connection.connection_id, identity=refreshed)
    assert connection.token_expires_at == refreshed.token_expires_at


@pytest.mark.parametrize("reason", ["revoked session", "expired session", "compromised session"])
async def test_realtime_authentication_rejects_invalid_persisted_sessions(reason):
    with patch(
        "app.modules.realtime.authentication.get_current_actor",
        new=AsyncMock(side_effect=UnauthorizedException(reason)),
    ):
        with pytest.raises(UnauthorizedException, match=reason):
            await authenticate_realtime_access_token(AsyncMock(), access_token="invalid")


@pytest.mark.parametrize("invalid_state", ["revoked", "compromised", "expired"])
async def test_existing_session_guard_rejects_invalid_realtime_session_state(invalid_state):
    now = datetime.now(timezone.utc)
    actor_id = uuid4()
    tenant_id = uuid4()
    session = SimpleNamespace(
        actor_id=actor_id,
        actor_type=AuthSessionActorType.TEACHER,
        tenant_id=tenant_id,
        revoked_at=now if invalid_state == "revoked" else None,
        compromised_at=now if invalid_state == "compromised" else None,
        expires_at=now - timedelta(seconds=1)
        if invalid_state == "expired"
        else now + timedelta(minutes=5),
    )
    payload = {
        "token_type": "access",
        "sid": "session-id",
        "actor_type": "teacher",
    }
    with patch(
        "app.core.dependencies.route_guards.AuthSessionRepository.get_session_by_jti",
        new=AsyncMock(return_value=session),
    ):
        with pytest.raises(UnauthorizedException, match="Session is no longer valid"):
            await _validate_session(
                AsyncMock(),
                payload=payload,
                actor_id=actor_id,
                tenant_id=tenant_id,
            )


async def test_realtime_authentication_derives_identity_from_backend_actor():
    # Use a real mapped class instance so identity routing cannot be supplied by the client.
    from app.modules.tenant_admins.models import TenantAdmin

    tenant_admin = TenantAdmin()
    tenant_admin.id = uuid4()
    tenant_admin.tenant_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode(
        {"sub": str(tenant_admin.id), "exp": expires_at},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with (
        patch(
            "app.modules.realtime.authentication.get_current_actor",
            new=AsyncMock(return_value=tenant_admin),
        ),
        patch(
            "app.modules.realtime.authentication.get_current_tenant_admin",
            new=AsyncMock(return_value=tenant_admin),
        ),
    ):
        result = await authenticate_realtime_access_token(AsyncMock(), access_token=token)

    assert result.actor_type == "tenant_admin"
    assert result.actor_id == tenant_admin.id
    assert result.tenant_id == tenant_admin.tenant_id


def test_broker_message_round_trips_through_json():
    original = actor_message()
    restored = RealtimeBrokerMessage.model_validate_json(original.model_dump_json())
    assert restored == original


def test_broker_prefers_realtime_redis_url(monkeypatch):
    monkeypatch.setattr(settings, "REALTIME_REDIS_URL", "redis://realtime/0")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://cache/0")
    with patch("app.modules.realtime.broker.Redis.from_url") as from_url:
        RealtimeRedisBroker._create_redis_client()
    assert from_url.call_args.args[0] == "redis://realtime/0"


async def test_broker_publish_failure_is_non_fatal():
    broker = RealtimeRedisBroker()
    broker._publisher = SimpleNamespace(publish=AsyncMock(side_effect=OSError("redis down")))
    assert await broker.publish(actor_message()) is False


async def test_deferred_actor_signal_is_not_published_until_after_commit_boundary():
    db = SimpleNamespace(info={})
    actor_id = uuid4()
    publish = AsyncMock(return_value=True)
    with patch("app.modules.realtime.publisher.realtime_broker.publish", publish):
        RealtimePublisher.defer_to_actor(
            db,
            event_type="notification.created",
            actor_type="teacher",
            actor_id=actor_id,
            data={"notification_id": str(uuid4())},
        )
        publish.assert_not_awaited()
        await RealtimePublisher.publish_deferred_after_commit(db)

    publish.assert_awaited_once()
    assert publish.await_args.args[0].audience.actor_id == actor_id


async def test_discarded_transaction_never_publishes_deferred_signal():
    db = SimpleNamespace(info={})
    RealtimePublisher.defer_to_actor(
        db,
        event_type="notification.created",
        actor_type="teacher",
        actor_id=uuid4(),
        data={},
    )
    RealtimePublisher.discard_deferred(db)
    publish = AsyncMock(return_value=True)
    with patch("app.modules.realtime.publisher.realtime_broker.publish", publish):
        await RealtimePublisher.publish_deferred_after_commit(db)
    publish.assert_not_awaited()


async def test_broker_listener_dispatches_valid_messages_and_ignores_invalid_ones():
    valid = actor_message()

    class PubSub:
        async def listen(self):
            yield {"type": "subscribe", "data": 1}
            yield {"type": "message", "data": valid.model_dump_json()}
            yield {"type": "message", "data": "not-json"}
            raise asyncio.CancelledError

    broker = RealtimeRedisBroker()
    broker._pubsub = PubSub()
    broker._connect_subscriber = AsyncMock()
    dispatch = AsyncMock()
    with patch("app.modules.realtime.broker.realtime_manager.dispatch", dispatch):
        with pytest.raises(asyncio.CancelledError):
            await broker._listen()

    dispatch.assert_awaited_once_with(event=valid.event, audience=valid.audience)


async def test_broker_reconnects_and_resubscribes_after_listener_failure(monkeypatch):
    valid = actor_message()
    recovered = asyncio.Event()

    class BrokenPubSub:
        async def listen(self):
            raise OSError("redis connection lost")
            yield

        async def unsubscribe(self, _channel):
            return None

        async def aclose(self):
            return None

    class RecoveredPubSub(BrokenPubSub):
        async def listen(self):
            yield {"type": "message", "data": valid.model_dump_json()}
            await asyncio.Event().wait()

    class Subscriber:
        async def aclose(self):
            return None

    broker = RealtimeRedisBroker()
    attempts = 0

    async def connect():
        nonlocal attempts
        attempts += 1
        broker._subscriber = Subscriber()
        broker._pubsub = BrokenPubSub() if attempts == 1 else RecoveredPubSub()

    async def dispatch(**_kwargs):
        recovered.set()

    monkeypatch.setattr(broker, "_connect_subscriber", connect)
    monkeypatch.setattr("app.modules.realtime.broker.RECONNECT_INITIAL_DELAY_SECONDS", 0.001)
    monkeypatch.setattr("app.modules.realtime.broker.realtime_manager.dispatch", dispatch)
    task = asyncio.create_task(broker._listen())
    await asyncio.wait_for(recovered.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert attempts == 2


async def test_broker_shutdown_cancels_reconnect_sleep_cleanly(monkeypatch):
    attempted = asyncio.Event()
    broker = RealtimeRedisBroker()

    async def connect():
        attempted.set()
        raise OSError("redis unavailable")

    monkeypatch.setattr(settings, "REALTIME_REDIS_URL", "redis://realtime/0")
    monkeypatch.setattr(broker, "_connect_subscriber", connect)
    assert await broker.start()
    await asyncio.wait_for(attempted.wait(), timeout=1)
    await asyncio.wait_for(broker.stop(), timeout=1)
    assert broker._listener_task is None


async def test_websocket_requires_auth_before_registration(monkeypatch):
    from app.modules.realtime import router as realtime_router_module

    socket = FakeWebSocket([{"type": "ping"}])
    manager = RealtimeConnectionManager()
    monkeypatch.setattr(realtime_router_module, "realtime_manager", manager)
    await realtime_router_module.realtime_stream(socket)

    assert socket.accepted
    assert socket.sent[0]["type"] == "error"
    assert socket.closed[0][0] == 4401
    assert await manager.get_all_connections() == []


async def test_websocket_ready_ping_refresh_and_disconnect_cleanup(monkeypatch):
    from app.modules.realtime import router as realtime_router_module

    original = identity(tenant_id=uuid4())
    refreshed = identity(actor_id=original.actor_id, tenant_id=original.tenant_id)
    authenticate = AsyncMock(side_effect=[original, refreshed])
    manager = RealtimeConnectionManager()
    socket = FakeWebSocket(
        [
            {"type": "auth", "access_token": "token-one"},
            {"type": "ping"},
            {"type": "auth.refresh", "access_token": "token-two"},
        ]
    )
    monkeypatch.setattr(realtime_router_module, "_authenticate", authenticate)
    monkeypatch.setattr(realtime_router_module, "realtime_manager", manager)

    await realtime_router_module.realtime_stream(socket)

    assert [frame["type"] for frame in socket.sent] == [
        "connection.ready",
        "pong",
        "auth.refreshed",
    ]
    assert authenticate.await_count == 2
    assert await manager.get_all_connections() == []


async def test_websocket_refresh_closes_when_identity_changes(monkeypatch):
    from app.modules.realtime import router as realtime_router_module

    original = identity(tenant_id=uuid4())
    switched = identity(tenant_id=original.tenant_id)
    manager = RealtimeConnectionManager()
    socket = FakeWebSocket(
        [
            {"type": "auth", "access_token": "token-one"},
            {"type": "auth.refresh", "access_token": "token-two"},
        ]
    )
    monkeypatch.setattr(
        realtime_router_module,
        "_authenticate",
        AsyncMock(side_effect=[original, switched]),
    )
    monkeypatch.setattr(realtime_router_module, "realtime_manager", manager)

    await realtime_router_module.realtime_stream(socket)

    assert socket.sent[-1]["code"] == "identity_change_rejected"
    assert socket.closed[-1][0] == 4403
    assert await manager.get_all_connections() == []
