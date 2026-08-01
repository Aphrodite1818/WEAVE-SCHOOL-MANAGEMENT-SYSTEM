"""Regression tests for login actor orchestration."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import AccountNotVerifiedException, UnauthorizedException
from app.modules.auth import login_service
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.schemas import LoginRequest
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.tenant_admins.models import TenantAdminStatus


@pytest.mark.asyncio
async def test_superadmin_authentication_skips_identity_lookup(monkeypatch) -> None:
    """Superadmin email login is resolved before tenant identity lookup."""

    identity_calls = 0
    superadmin_id = uuid4()
    superadmin = SimpleNamespace(
        id=superadmin_id,
        email="superadmin@example.com",
        password_hash="hashed",
        is_active=True,
        last_login_at=None,
    )

    async def flush() -> None:
        return None

    async def get_superadmin_by_email(_db, email):
        assert email == "superadmin@example.com"
        return superadmin

    async def resolve_identifier(*_args, **_kwargs):
        nonlocal identity_calls
        identity_calls += 1
        return None

    db = SimpleNamespace(add=lambda _actor: None, flush=flush)
    monkeypatch.setattr(
        login_service.SuperAdminRepository,
        "get_by_email",
        get_superadmin_by_email,
    )
    monkeypatch.setattr(login_service, "verify_password", lambda password, hashed: True)
    monkeypatch.setattr(
        login_service.AuthIdentityService,
        "resolve_identifier",
        resolve_identifier,
    )

    result = await login_service.AuthService.authenticate_actor(
        db,
        LoginRequest(identifier="SUPERADMIN@example.com", password="secret"),
    )

    assert result.actor_id == superadmin_id
    assert result.email == "superadmin@example.com"
    assert result.actor_type == AuthSessionActorType.SUPERADMIN.value
    assert identity_calls == 0


@pytest.mark.asyncio
async def test_missing_email_identity_raises_invalid_credentials(monkeypatch) -> None:
    """Unknown email addresses do not leak account-existence details."""

    calls: list[tuple[str, str]] = []

    async def get_superadmin_by_email(_db, email):
        calls.append(("superadmin", email))
        return None

    async def resolve_identifier(_db, *, identifier, identifier_type):
        calls.append(("identity", identifier))
        assert identifier_type == IdentifierType.EMAIL
        raise login_service.NotFoundException("not found")

    monkeypatch.setattr(
        login_service.SuperAdminRepository,
        "get_by_email",
        get_superadmin_by_email,
    )
    monkeypatch.setattr(
        login_service.AuthIdentityService,
        "resolve_identifier",
        resolve_identifier,
    )

    with pytest.raises(UnauthorizedException, match="Invalid email or password"):
        await login_service.AuthService.authenticate_actor(
            object(),
            LoginRequest(identifier="MISSING@example.com", password="secret"),
        )

    assert calls == [
        ("superadmin", "missing@example.com"),
        ("identity", "missing@example.com"),
    ]


@pytest.mark.asyncio
async def test_unverified_tenant_admin_login_returns_verification_metadata(monkeypatch) -> None:
    """Pending registrations must send the login form to OTP verification."""

    tenant_id = uuid4()
    admin_id = uuid4()
    admin = SimpleNamespace(
        id=admin_id,
        tenant_id=tenant_id,
        email="pending@example.com",
        password_hash="hashed",
        is_verified=False,
        account_status=TenantAdminStatus.PENDING,
    )

    async def get_superadmin_by_email(_db, _email):
        return None

    async def resolve_identifier(_db, *, identifier, identifier_type):
        assert identifier == "pending@example.com"
        assert identifier_type == IdentifierType.EMAIL
        return SimpleNamespace(
            actor_type=ActorType.TENANT_ADMIN,
            actor_id=admin_id,
            tenant_id=tenant_id,
        )

    async def get_admin_by_id(_db, actor_id):
        assert actor_id == admin_id
        return admin

    monkeypatch.setattr(
        login_service.SuperAdminRepository,
        "get_by_email",
        get_superadmin_by_email,
    )
    monkeypatch.setattr(
        login_service.AuthIdentityService,
        "resolve_identifier",
        resolve_identifier,
    )
    monkeypatch.setattr(login_service.TenantAdminRepository, "get_by_id", get_admin_by_id)
    monkeypatch.setattr(login_service, "verify_password", lambda password, hashed: True)

    with pytest.raises(AccountNotVerifiedException) as exc_info:
        await login_service.AuthService.authenticate_actor(
            object(),
            LoginRequest(identifier="Pending@example.com", password="secret"),
        )

    assert exc_info.value.payload == {
        "verification_required": True,
        "email": "pending@example.com",
        "purpose": "verification",
        "redirect_to": "/verify-otp",
        "resend_otp_available": True,
    }


@pytest.mark.asyncio
async def test_admission_number_never_probes_identity_or_superadmin(monkeypatch) -> None:
    """Student admission numbers are not part of the email-account login path."""

    async def unexpected_lookup(*_args, **_kwargs):
        raise AssertionError("lookup should not run for non-email identifiers")

    monkeypatch.setattr(
        login_service.SuperAdminRepository,
        "get_by_email",
        unexpected_lookup,
    )
    monkeypatch.setattr(
        login_service.AuthIdentityService,
        "resolve_identifier",
        unexpected_lookup,
    )

    with pytest.raises(UnauthorizedException, match="Invalid email or password"):
        await login_service.AuthService.authenticate_actor(
            object(),
            LoginRequest(identifier="STUDENT-001", password="wrong"),
        )
