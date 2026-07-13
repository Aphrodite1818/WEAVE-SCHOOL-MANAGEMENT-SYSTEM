import pytest

from app.core.middleware import platform_lockdown
from app.core.middleware.platform_lockdown import PlatformLockdownMiddleware


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _call_middleware(middleware, path, headers=None):
    messages = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
        "server": ("testserver", 80),
    }

    async def send(message):
        messages.append(message)

    await middleware(scope, _receive, send)
    return messages


def _status(messages):
    return next(message["status"] for message in messages if message["type"] == "http.response.start")


@pytest.mark.asyncio
async def test_claim_only_superadmin_token_does_not_bypass_lockdown(monkeypatch):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    async def not_blocked(db, client_ip):
        return {"blocked": False}

    async def active_lockdown(db):
        return {"lockdown_enabled": True, "lockdown_message": "Locked", "lockdown_reason": "test"}

    monkeypatch.setattr(platform_lockdown, "AsyncSessionLocal", lambda: SessionContext())
    monkeypatch.setattr(platform_lockdown.SecurityResponseService, "is_ip_blocked", not_blocked)
    monkeypatch.setattr(platform_lockdown.PlatformControlService, "get_state", active_lockdown)

    middleware = PlatformLockdownMiddleware(app)
    messages = await _call_middleware(
        middleware,
        "/api/v1/tenant-admin/students",
        headers=[(b"authorization", b"Bearer not-a-real-superadmin-token")],
    )

    assert _status(messages) == 503


@pytest.mark.asyncio
async def test_database_failure_keeps_cached_active_lockdown_enforced(monkeypatch):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    async def fail_to_load_state(db, client_ip):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(platform_lockdown, "AsyncSessionLocal", lambda: SessionContext())
    monkeypatch.setattr(platform_lockdown.SecurityResponseService, "is_ip_blocked", fail_to_load_state)

    middleware = PlatformLockdownMiddleware(app)
    PlatformLockdownMiddleware._last_known_lockdown_state = {
        "lockdown_enabled": True,
        "lockdown_message": "Locked",
        "lockdown_reason": "cached",
    }

    messages = await _call_middleware(middleware, "/api/v1/tenant-admin/students")

    assert _status(messages) == 503


@pytest.mark.asyncio
async def test_database_failure_without_cached_state_preserves_availability(monkeypatch):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class SessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    async def fail_to_load_state(db, client_ip):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(platform_lockdown, "AsyncSessionLocal", lambda: SessionContext())
    monkeypatch.setattr(platform_lockdown.SecurityResponseService, "is_ip_blocked", fail_to_load_state)

    middleware = PlatformLockdownMiddleware(app)
    PlatformLockdownMiddleware._last_known_lockdown_state = None

    messages = await _call_middleware(middleware, "/api/v1/tenant-admin/students")

    assert _status(messages) == 204
