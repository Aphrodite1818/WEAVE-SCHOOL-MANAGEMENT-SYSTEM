"""Regression tests for login actor orchestration."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedException
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import LoginRequest


@pytest.mark.asyncio
async def test_tenant_identity_authentication_skips_superadmin_lookup(monkeypatch) -> None:
    tenant_actor = SimpleNamespace(actor_type="teacher")
    superadmin_calls = 0

    async def authenticate_tenant(*_args, **_kwargs):
        return tenant_actor

    async def authenticate_superadmin(*_args, **_kwargs):
        nonlocal superadmin_calls
        superadmin_calls += 1
        return None

    monkeypatch.setattr(auth_service, "_authenticate_tenant_actor", authenticate_tenant)
    monkeypatch.setattr(auth_service, "_authenticate_superadmin", authenticate_superadmin)

    result = await auth_service.AuthService.authenticate_actor(
        object(),
        LoginRequest(email="Teacher@Example.com", password="secret"),
    )

    assert result is tenant_actor
    assert superadmin_calls == 0


@pytest.mark.asyncio
async def test_missing_tenant_identity_falls_back_to_superadmin(monkeypatch) -> None:
    calls: list[str] = []
    superadmin_id = uuid4()
    superadmin = SimpleNamespace(
        id=superadmin_id,
        email="superadmin@example.com",
    )

    async def authenticate_tenant(*_args, **_kwargs):
        calls.append("tenant_identity")
        return None

    async def authenticate_superadmin(*_args, **_kwargs):
        calls.append("superadmin")
        return superadmin

    monkeypatch.setattr(auth_service, "_authenticate_tenant_actor", authenticate_tenant)
    monkeypatch.setattr(auth_service, "_authenticate_superadmin", authenticate_superadmin)

    result = await auth_service.AuthService.authenticate_actor(
        object(),
        LoginRequest(email="SUPERADMIN@example.com", password="secret"),
    )

    assert calls == ["tenant_identity", "superadmin"]
    assert result.actor_id == superadmin_id
    assert result.email == "superadmin@example.com"
    assert result.actor_type == "superadmin"


@pytest.mark.asyncio
async def test_tenant_authentication_failure_does_not_probe_superadmin(monkeypatch) -> None:
    superadmin_calls = 0

    async def authenticate_tenant(*_args, **_kwargs):
        raise UnauthorizedException("Invalid credentials")

    async def authenticate_superadmin(*_args, **_kwargs):
        nonlocal superadmin_calls
        superadmin_calls += 1
        return None

    monkeypatch.setattr(auth_service, "_authenticate_tenant_actor", authenticate_tenant)
    monkeypatch.setattr(auth_service, "_authenticate_superadmin", authenticate_superadmin)

    with pytest.raises(UnauthorizedException, match="Invalid credentials"):
        await auth_service.AuthService.authenticate_actor(
            object(),
            LoginRequest(email="teacher@example.com", password="wrong"),
        )

    assert superadmin_calls == 0


@pytest.mark.asyncio
async def test_admission_number_never_probes_superadmin(monkeypatch) -> None:
    superadmin_calls = 0

    async def authenticate_tenant(*_args, **_kwargs):
        return None

    async def authenticate_superadmin(*_args, **_kwargs):
        nonlocal superadmin_calls
        superadmin_calls += 1
        return None

    monkeypatch.setattr(auth_service, "_authenticate_tenant_actor", authenticate_tenant)
    monkeypatch.setattr(auth_service, "_authenticate_superadmin", authenticate_superadmin)

    with pytest.raises(UnauthorizedException, match="Invalid email or password"):
        await auth_service.AuthService.authenticate_actor(
            object(),
            LoginRequest(email="STUDENT-001", password="wrong"),
        )

    assert superadmin_calls == 0
