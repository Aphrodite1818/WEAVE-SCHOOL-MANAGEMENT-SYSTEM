from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import UnauthorizedException
from app.modules.auth.models import AuthSessionActorType
from app.modules.cbt.auth.schemas import (
    AuthenticatedCBTServer,
    CBTActorTokenPair,
    CBTStaffIdentity,
    CBTStaffLoginRequest,
)
from app.modules.cbt.auth.security import hash_actor_token
from app.modules.cbt.auth.service import (
    CBT_ACTOR_ACCESS_TOKEN_TTL,
    CBT_ACTOR_AUTHORIZATION_TTL,
    CBTActorAuthorizationService,
    CBTStaffAuthService,
)
from app.modules.cbt.enums import CBTServerStatus
from app.modules.teachers.models import TeacherAccountStatus, TeacherMembershipStatus


def _server(*, tenant_id=None) -> AuthenticatedCBTServer:
    return AuthenticatedCBTServer(
        server_id=uuid4(),
        credential_id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        server_name="School CBT",
        status=CBTServerStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_issue_for_teacher_returns_raw_pair_but_persists_only_hashes(monkeypatch) -> None:
    tenant_id = uuid4()
    account_id = uuid4()
    membership_id = uuid4()
    authorization_id = uuid4()
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    identity = CBTStaffIdentity(
        actor_id=account_id,
        membership_id=membership_id,
        tenant_id=tenant_id,
        role="teacher",
        email="teacher@example.com",
        first_name="Teacher",
        last_name="One",
    )

    async def create_authorization(_db, authorization):
        authorization.id = authorization_id
        return authorization

    created_refresh = []

    async def create_refresh(_db, token):
        created_refresh.append(token)
        return token

    monkeypatch.setattr(
        "app.modules.cbt.auth.service.generate_actor_access_token",
        lambda: "wcbt_acc_raw-access",
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.generate_actor_refresh_token",
        lambda: "wcbt_ref_raw-refresh",
    )
    authorization_create = AsyncMock(side_effect=create_authorization)
    refresh_create = AsyncMock(side_effect=create_refresh)
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.create",
        authorization_create,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.create",
        refresh_create,
    )

    result = await CBTActorAuthorizationService.issue_for_identity(
        AsyncMock(),
        identity=identity,
        now=now,
    )

    assert result.access_token == "wcbt_acc_raw-access"
    assert result.refresh_token == "wcbt_ref_raw-refresh"
    assert result.access_token_expires_at == now + CBT_ACTOR_ACCESS_TOKEN_TTL
    assert result.refresh_token_expires_at == now + CBT_ACTOR_AUTHORIZATION_TTL

    stored_authorization = authorization_create.await_args.args[1]
    assert stored_authorization.tenant_id == tenant_id
    assert stored_authorization.teacher_account_id == account_id
    assert stored_authorization.teacher_membership_id == membership_id
    assert stored_authorization.tenant_admin_id is None
    assert stored_authorization.access_token_hash == hash_actor_token("wcbt_acc_raw-access")
    assert stored_authorization.access_token_hash != result.access_token

    assert len(created_refresh) == 1
    stored_refresh = created_refresh[0]
    assert stored_refresh.authorization_id == authorization_id
    assert stored_refresh.token_hash == hash_actor_token("wcbt_ref_raw-refresh")
    assert stored_refresh.token_hash != result.refresh_token
    assert stored_refresh.expires_at == result.refresh_token_expires_at


@pytest.mark.asyncio
async def test_refresh_rotates_both_tokens_without_extending_absolute_lifetime(monkeypatch) -> None:
    now = datetime(2026, 9, 30, 13, 0, tzinfo=timezone.utc)
    hard_expiry = now + timedelta(hours=4)
    tenant_id = uuid4()
    authorization_id = uuid4()
    old_refresh_id = uuid4()
    replacement_id = uuid4()
    server = _server(tenant_id=tenant_id)

    authorization = SimpleNamespace(
        id=authorization_id,
        tenant_id=tenant_id,
        role="teacher",
        teacher_account_id=uuid4(),
        teacher_membership_id=uuid4(),
        tenant_admin_id=None,
        access_token_hash="old-access-hash",
        access_token_expires_at=now + timedelta(minutes=5),
        absolute_expires_at=hard_expiry,
        revoked_at=None,
        revocation_reason=None,
    )
    stored_refresh = SimpleNamespace(
        id=old_refresh_id,
        authorization_id=authorization_id,
        expires_at=hard_expiry,
        consumed_at=None,
        revoked_at=None,
        reuse_detected_at=None,
        replaced_by_token_id=None,
    )

    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.get_by_hash",
        AsyncMock(side_effect=[stored_refresh, stored_refresh]),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.get_by_id",
        AsyncMock(return_value=authorization),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationService._assert_actor_still_eligible",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.generate_actor_access_token",
        lambda: "wcbt_acc_new-access",
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.generate_actor_refresh_token",
        lambda: "wcbt_ref_new-refresh",
    )

    async def create_replacement(_db, replacement):
        replacement.id = replacement_id
        return replacement

    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.create",
        AsyncMock(side_effect=create_replacement),
    )
    refresh_save = AsyncMock()
    authorization_save = AsyncMock()
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.save",
        refresh_save,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.save",
        authorization_save,
    )

    result = await CBTActorAuthorizationService.refresh_actor_authorization(
        AsyncMock(),
        current_server=server,
        refresh_token="wcbt_ref_old-refresh",
        now=now,
    )

    assert result.access_token == "wcbt_acc_new-access"
    assert result.refresh_token == "wcbt_ref_new-refresh"
    assert result.access_token_expires_at == now + CBT_ACTOR_ACCESS_TOKEN_TTL
    assert result.refresh_token_expires_at == hard_expiry
    assert stored_refresh.consumed_at == now
    assert stored_refresh.replaced_by_token_id == replacement_id
    assert authorization.access_token_hash == hash_actor_token("wcbt_acc_new-access")
    assert authorization.absolute_expires_at == hard_expiry
    refresh_save.assert_awaited_once_with(pytest.ANY if False else refresh_save.call_args.args[0], stored_refresh)
    authorization_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_token_reuse_revokes_entire_family_before_raising(monkeypatch) -> None:
    now = datetime(2026, 9, 30, 14, 0, tzinfo=timezone.utc)
    tenant_id = uuid4()
    authorization_id = uuid4()
    server = _server(tenant_id=tenant_id)
    authorization = SimpleNamespace(
        id=authorization_id,
        tenant_id=tenant_id,
        absolute_expires_at=now + timedelta(hours=5),
        revoked_at=None,
        revocation_reason=None,
    )
    stored_refresh = SimpleNamespace(
        authorization_id=authorization_id,
        expires_at=now + timedelta(hours=5),
        consumed_at=now - timedelta(minutes=1),
        revoked_at=None,
        reuse_detected_at=None,
    )
    db = SimpleNamespace(commit=AsyncMock())

    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.get_by_hash",
        AsyncMock(side_effect=[stored_refresh, stored_refresh]),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.get_by_id",
        AsyncMock(return_value=authorization),
    )
    refresh_save = AsyncMock()
    authorization_save = AsyncMock()
    revoke_children = AsyncMock(return_value=1)
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.save",
        refresh_save,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.save",
        authorization_save,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorRefreshTokenRepository.revoke_active_for_authorization",
        revoke_children,
    )

    with pytest.raises(UnauthorizedException):
        await CBTActorAuthorizationService.refresh_actor_authorization(
            db,
            current_server=server,
            refresh_token="wcbt_ref_reused",
            now=now,
        )

    assert stored_refresh.reuse_detected_at == now
    assert authorization.revoked_at == now
    assert authorization.revocation_reason == "refresh_token_reuse"
    revoke_children.assert_awaited_once_with(
        db,
        authorization_id=authorization_id,
        revoked_at=now,
    )
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_actor_returns_trusted_context(monkeypatch) -> None:
    now = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)
    tenant_id = uuid4()
    account_id = uuid4()
    membership_id = uuid4()
    authorization_id = uuid4()
    server = _server(tenant_id=tenant_id)
    authorization = SimpleNamespace(
        id=authorization_id,
        tenant_id=tenant_id,
        role="teacher",
        teacher_account_id=account_id,
        teacher_membership_id=membership_id,
        tenant_admin_id=None,
        access_token_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=6),
        revoked_at=None,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.get_by_access_token_hash",
        AsyncMock(return_value=authorization),
    )
    eligibility = AsyncMock()
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationService._assert_actor_still_eligible",
        eligibility,
    )

    result = await CBTActorAuthorizationService.authenticate_actor(
        AsyncMock(),
        current_server=server,
        access_token="wcbt_acc_valid",
        now=now,
    )

    assert result.authorization_id == authorization_id
    assert result.tenant_id == tenant_id
    assert result.actor_id == account_id
    assert result.membership_id == membership_id
    assert result.role == "teacher"
    eligibility.assert_awaited_once()


@pytest.mark.asyncio
async def test_authenticate_actor_rejects_cross_tenant_token_before_eligibility(monkeypatch) -> None:
    now = datetime(2026, 9, 30, 15, 0, tzinfo=timezone.utc)
    server = _server()
    authorization = SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        role="admin",
        tenant_admin_id=uuid4(),
        access_token_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(hours=6),
        revoked_at=None,
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationRepository.get_by_access_token_hash",
        AsyncMock(return_value=authorization),
    )
    eligibility = AsyncMock()
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationService._assert_actor_still_eligible",
        eligibility,
    )

    with pytest.raises(UnauthorizedException):
        await CBTActorAuthorizationService.authenticate_actor(
            AsyncMock(),
            current_server=server,
            access_token="wcbt_acc_cross-tenant",
            now=now,
        )

    eligibility.assert_not_awaited()


@pytest.mark.asyncio
async def test_staff_login_response_includes_cloud_actor_token_pair(monkeypatch) -> None:
    server = _server()
    actor_id = uuid4()
    actor = SimpleNamespace(
        actor_type=AuthSessionActorType.TENANT_ADMIN.value,
        actor_id=actor_id,
        tenant_id=server.tenant_id,
        email="admin@example.com",
        user=SimpleNamespace(first_name="School", last_name="Admin"),
    )
    token_pair = CBTActorTokenPair(
        access_token="wcbt_acc_login",
        access_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        refresh_token="wcbt_ref_login",
        refresh_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )

    monkeypatch.setattr(
        "app.modules.cbt.auth.service.AuthService.authenticate_actor",
        AsyncMock(return_value=actor),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.SecurityResponseService.enforce_actor_ip_allowed",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.PlatformControlService.enforce_actor_allowed",
        AsyncMock(),
    )
    issue = AsyncMock(return_value=token_pair)
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.CBTActorAuthorizationService.issue_for_identity",
        issue,
    )

    response = await CBTStaffAuthService.authenticate_staff(
        AsyncMock(),
        payload=CBTStaffLoginRequest(
            email="admin@example.com",
            password="StrongPass123!",
        ),
        current_server=server,
        client_ip="127.0.0.1",
    )

    assert response.actor_id == actor_id
    assert response.tenant_id == server.tenant_id
    assert response.role == "admin"
    assert response.access_token == token_pair.access_token
    assert response.refresh_token == token_pair.refresh_token
    issue.assert_awaited_once()


@pytest.mark.asyncio
async def test_defensive_eligibility_rejects_suspended_teacher_membership(monkeypatch) -> None:
    authorization = SimpleNamespace(
        role="teacher",
        tenant_id=uuid4(),
        teacher_account_id=uuid4(),
        teacher_membership_id=uuid4(),
    )
    membership = SimpleNamespace(
        status=TeacherMembershipStatus.SUSPENDED,
        teacher_account_id=authorization.teacher_account_id,
        teacher_account=SimpleNamespace(
            is_active=True,
            is_verified=True,
            account_status=TeacherAccountStatus.ACTIVE,
        ),
    )
    monkeypatch.setattr(
        "app.modules.cbt.auth.service.TeacherMembershipRepository.get_by_id",
        AsyncMock(return_value=membership),
    )

    with pytest.raises(UnauthorizedException):
        await CBTActorAuthorizationService._assert_actor_still_eligible(
            AsyncMock(),
            authorization=authorization,
        )
