from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from app.main import API_V1_PREFIX, app
from app.modules.cbt.ai.router import router as ai_router
from app.modules.cbt.auth.router import (
    refresh_staff_authorization,
    router as auth_router,
)
from app.modules.cbt.auth.schemas import (
    AuthenticatedCBTServer,
    CBTActorRefreshRequest,
    CBTActorTokenPair,
)
from app.modules.cbt.auth.service import CBTActorAuthorizationService
from app.modules.cbt.enums import CBTServerStatus


def _route_keys(router) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_ai_router_exposes_only_ai_group_routes() -> None:
    routes = _route_keys(ai_router)

    expected = {
        ("POST", "/ai/questions/generate"),
        ("POST", "/ai/questions/regenerate"),
        ("GET", "/ai/quota"),
        ("POST", "/ai/quota/requests"),
        ("GET", "/ai/quota/requests"),
        ("POST", "/ai/quota/requests/{request_id}/cancel"),
        ("GET", "/ai/admin/quota/summary"),
        ("GET", "/ai/admin/quota/actors"),
        ("GET", "/ai/admin/quota/requests"),
        ("POST", "/ai/admin/quota/requests/{request_id}/approve"),
        ("POST", "/ai/admin/quota/requests/{request_id}/reject"),
        ("POST", "/ai/admin/quota/allocations"),
        ("GET", "/ai/admin/quota/allocations"),
        ("POST", "/ai/admin/quota/purchases/quote"),
        ("POST", "/ai/admin/quota/purchases/checkout"),
        ("POST", "/ai/admin/quota/purchases/{reference}/verify"),
        ("GET", "/ai/admin/quota/purchases"),
        ("GET", "/ai/admin/quota/purchases/{purchase_id}"),
    }

    assert expected.issubset(routes)
    assert all(path.startswith("/ai/") or path == "/ai/quota" for _, path in routes)
    assert not any("/auth/" in path for _, path in routes)


def test_auth_router_owns_login_and_refresh_routes() -> None:
    routes = _route_keys(auth_router)

    assert ("POST", "/auth/staff/login") in routes
    assert ("POST", "/auth/staff/refresh") in routes
    assert not any(path.startswith("/ai/") for _, path in routes)


def test_main_mounts_ai_and_auth_under_cbt_prefix() -> None:
    paths = {getattr(route, "path", None) for route in app.routes}

    assert f"{API_V1_PREFIX}/cbt/auth/staff/login" in paths
    assert f"{API_V1_PREFIX}/cbt/auth/staff/refresh" in paths
    assert f"{API_V1_PREFIX}/cbt/ai/questions/generate" in paths
    assert f"{API_V1_PREFIX}/cbt/ai/quota" in paths


@pytest.mark.asyncio
async def test_refresh_route_delegates_to_cbt_auth_service(monkeypatch) -> None:
    server = AuthenticatedCBTServer(
        server_id=uuid4(),
        credential_id=uuid4(),
        tenant_id=uuid4(),
        server_name="School CBT",
        status=CBTServerStatus.ACTIVE,
    )
    token_pair = CBTActorTokenPair(
        access_token="wcbt_acc_new",
        access_token_expires_at="2026-09-30T22:00:00Z",
        refresh_token="wcbt_ref_new",
        refresh_token_expires_at="2026-10-01T09:00:00Z",
    )
    refresh = AsyncMock(return_value=token_pair)
    monkeypatch.setattr(
        CBTActorAuthorizationService,
        "refresh_actor_authorization",
        refresh,
    )

    result = await refresh_staff_authorization(
        CBTActorRefreshRequest(refresh_token="x" * 64),
        AsyncMock(),
        server,
    )

    assert result == token_pair
    refresh.assert_awaited_once()
    assert refresh.await_args.kwargs["current_server"] == server
    assert refresh.await_args.kwargs["refresh_token"] == "x" * 64
