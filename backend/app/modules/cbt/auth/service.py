"""Authentication services used by paired CBT servers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import AppException, ForbiddenException, UnauthorizedException
from app.modules.auth.login_service import AuthService
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.schemas import LoginRequest
from app.modules.cbt.auth.models import (
    CBTActorAuthorization,
    CBTActorRefreshToken,
)
from app.modules.cbt.auth.refresh_recovery import (
    CBTActorRefreshRecoveryService,
    CBTRefreshRecoveryUnavailable,
)
from app.modules.cbt.auth.repository import (
    CBTActorAuthorizationRepository,
    CBTActorRefreshTokenRepository,
)
from app.modules.cbt.auth.schemas import (
    AuthenticatedCBTActor,
    AuthenticatedCBTServer,
    CBTActorTokenPair,
    CBTStaffAuthResponse,
    CBTStaffIdentity,
    CBTStaffLoginRequest,
)
from app.modules.cbt.auth.security import (
    generate_actor_access_token,
    generate_actor_refresh_token,
    hash_actor_token,
)
from app.modules.cbt.enums import CBTServerStatus
from app.modules.cbt.repository import CBTServerCredentialRepository
from app.modules.cbt.security import hash_server_token
from app.modules.superadmin.platform_control_service import PlatformControlService
from app.modules.superadmin.security_response_service import SecurityResponseService
from app.modules.teachers.models import (
    TeacherAccountStatus,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.tenant_admins.models import TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository


CBT_ACTOR_ACCESS_TOKEN_TTL = timedelta(minutes=60)
CBT_ACTOR_PRODUCTION_LIKE_ACCESS_TOKEN_TTL = timedelta(minutes=20)
CBT_ACTOR_AUTHORIZATION_TTL = timedelta(hours=12)
INVALID_CBT_ACTOR_AUTHORIZATION = "Invalid or expired CBT actor authorization"
CBT_REFRESH_RECOVERY_UNAVAILABLE = (
    "CBT cloud authorization refresh is temporarily unavailable. "
    "Retry with the same idempotency key."
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_access_token_ttl() -> timedelta:
    """Return the environment-specific lifetime for CBT actor access tokens."""

    if settings.is_development:
        return CBT_ACTOR_ACCESS_TOKEN_TTL
    return CBT_ACTOR_PRODUCTION_LIKE_ACCESS_TOKEN_TTL


def _refresh_recovery_unavailable(exc: Exception) -> AppException:
    return AppException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=CBT_REFRESH_RECOVERY_UNAVAILABLE,
        headers={"Retry-After": "5"},
        payload={"retryable": True, "same_idempotency_key_required": True},
    )


class CBTMachineAuthService:
    """Authenticate paired CBT server credentials."""

    @staticmethod
    async def authenticate_server(
        db: AsyncSession, *, server_credential: str
    ) -> AuthenticatedCBTServer:
        """Authenticate a machine credential and derive its server and tenant context."""

        credential_hash = hash_server_token(server_credential)
        resolved = await CBTServerCredentialRepository.get_unrevoked_by_hash_with_server(
            db, credential_hash=credential_hash
        )
        if resolved is None:
            raise UnauthorizedException(detail="Invalid CBT server credential")

        credential, server = resolved
        now = _utc_now()

        if credential.expires_at is not None and credential.expires_at <= now:
            raise UnauthorizedException(detail="Invalid CBT server credential")
        if server.status == CBTServerStatus.REVOKED or server.revoked_at is not None:
            raise UnauthorizedException(detail="Invalid CBT server credential")
        if server.status == CBTServerStatus.SUSPENDED:
            raise ForbiddenException(detail="CBT Server is suspended")
        if server.status != CBTServerStatus.ACTIVE:
            raise ForbiddenException(detail="CBT server is not active")

        return AuthenticatedCBTServer(
            server_id=server.id,
            credential_id=credential.id,
            tenant_id=server.tenant_id,
            server_name=server.name,
            status=server.status,
        )


class CBTActorAuthorizationService:
    """Issue, rotate, authenticate, and revoke CBT human-actor credentials.

    The opaque access token is intentionally short-lived and is used on normal
    CBT-cloud actor requests. The opaque refresh token is used only to rotate
    the cloud credentials. The authorization family's absolute expiry never
    moves forward during refresh.
    """

    @staticmethod
    async def issue_for_identity(
        db: AsyncSession,
        *,
        identity: CBTStaffIdentity,
        now: datetime | None = None,
    ) -> CBTActorTokenPair:
        issued_at = now or _utc_now()
        absolute_expires_at = issued_at + CBT_ACTOR_AUTHORIZATION_TTL
        access_expires_at = min(
            issued_at + _actor_access_token_ttl(),
            absolute_expires_at,
        )

        raw_access_token = generate_actor_access_token()
        raw_refresh_token = generate_actor_refresh_token()

        authorization_kwargs: dict[str, object] = {
            "tenant_id": identity.tenant_id,
            "role": identity.role,
            "access_token_hash": hash_actor_token(raw_access_token),
            "access_token_expires_at": access_expires_at,
            "absolute_expires_at": absolute_expires_at,
        }

        if identity.role == "teacher":
            if identity.membership_id is None:
                raise ForbiddenException(detail="This account is not authorized to use CBT")
            authorization_kwargs.update(
                teacher_account_id=identity.actor_id,
                teacher_membership_id=identity.membership_id,
            )
        else:
            authorization_kwargs.update(tenant_admin_id=identity.actor_id)

        authorization = CBTActorAuthorization(**authorization_kwargs)
        authorization = await CBTActorAuthorizationRepository.create(
            db,
            authorization,
        )

        refresh_token = CBTActorRefreshToken(
            authorization_id=authorization.id,
            token_hash=hash_actor_token(raw_refresh_token),
            expires_at=absolute_expires_at,
        )
        await CBTActorRefreshTokenRepository.create(db, refresh_token)

        return CBTActorTokenPair(
            access_token=raw_access_token,
            access_token_expires_at=access_expires_at,
            refresh_token=raw_refresh_token,
            refresh_token_expires_at=absolute_expires_at,
        )

    @staticmethod
    async def refresh_actor_authorization(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
        refresh_token: str,
        idempotency_key: UUID,
        now: datetime | None = None,
    ) -> CBTActorTokenPair:
        """Rotate a CBT actor pair, safely recovering an ambiguous prior response."""

        try:
            refresh_hash = hash_actor_token(refresh_token)
        except ValueError as exc:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION) from exc

        token_hint = await CBTActorRefreshTokenRepository.get_by_hash(
            db,
            refresh_hash,
        )
        if token_hint is None:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        authorization = await CBTActorAuthorizationRepository.get_by_id(
            db,
            token_hint.authorization_id,
            lock=True,
        )
        stored_refresh = await CBTActorRefreshTokenRepository.get_by_hash(
            db,
            refresh_hash,
            lock=True,
        )
        if (
            authorization is None
            or stored_refresh is None
            or stored_refresh.authorization_id != authorization.id
        ):
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        rotated_at = now or _utc_now()

        if authorization.tenant_id != current_server.tenant_id:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        if (
            authorization.revoked_at is not None
            or authorization.absolute_expires_at <= rotated_at
            or stored_refresh.revoked_at is not None
            or stored_refresh.expires_at <= rotated_at
        ):
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        if stored_refresh.consumed_at is not None:
            recovered = await CBTActorAuthorizationService._recover_consumed_refresh(
                db,
                current_server=current_server,
                authorization=authorization,
                stored_refresh=stored_refresh,
                refresh_hash=refresh_hash,
                idempotency_key=idempotency_key,
                now=rotated_at,
            )
            if recovered is not None:
                await CBTActorAuthorizationService._assert_actor_still_eligible(
                    db,
                    authorization=authorization,
                )
                return recovered

            stored_refresh.reuse_detected_at = rotated_at
            await CBTActorRefreshTokenRepository.save(db, stored_refresh)

            authorization.revoked_at = authorization.revoked_at or rotated_at
            authorization.revocation_reason = "refresh_token_reuse"
            await CBTActorAuthorizationRepository.save(db, authorization)
            await CBTActorRefreshTokenRepository.revoke_active_for_authorization(
                db,
                authorization_id=authorization.id,
                revoked_at=rotated_at,
            )

            # Persist the security response before raising. The request-scoped DB
            # dependency rolls back exceptions, so reuse revocation needs its own
            # durable commit.
            await db.commit()
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        await CBTActorAuthorizationService._assert_actor_still_eligible(
            db,
            authorization=authorization,
        )

        raw_access_token = generate_actor_access_token()
        raw_refresh_token = generate_actor_refresh_token()
        access_expires_at = min(
            rotated_at + _actor_access_token_ttl(),
            authorization.absolute_expires_at,
        )
        token_pair = CBTActorTokenPair(
            access_token=raw_access_token,
            access_token_expires_at=access_expires_at,
            refresh_token=raw_refresh_token,
            refresh_token_expires_at=authorization.absolute_expires_at,
        )

        recovery_ttl = max(
            1,
            int((authorization.absolute_expires_at - rotated_at).total_seconds()),
        )
        try:
            # Store the recoverable response before consuming the one-time token.
            # If Redis is unavailable, abort while the old token is still valid.
            await CBTActorRefreshRecoveryService.store(
                server_id=current_server.server_id,
                authorization_id=authorization.id,
                refresh_token_hash=refresh_hash,
                idempotency_key=idempotency_key,
                token_pair=token_pair,
                ttl_seconds=recovery_ttl,
            )
        except CBTRefreshRecoveryUnavailable as exc:
            raise _refresh_recovery_unavailable(exc) from exc

        replacement = CBTActorRefreshToken(
            authorization_id=authorization.id,
            token_hash=hash_actor_token(raw_refresh_token),
            expires_at=authorization.absolute_expires_at,
        )
        replacement = await CBTActorRefreshTokenRepository.create(
            db,
            replacement,
        )

        stored_refresh.consumed_at = rotated_at
        stored_refresh.replaced_by_token_id = replacement.id
        await CBTActorRefreshTokenRepository.save(db, stored_refresh)

        authorization.access_token_hash = hash_actor_token(raw_access_token)
        authorization.access_token_expires_at = access_expires_at
        await CBTActorAuthorizationRepository.save(db, authorization)

        # Commit before the token pair is returned. The Redis receipt was already
        # written, so a lost HTTP response can now be replayed safely.
        await db.commit()
        return token_pair

    @staticmethod
    async def _recover_consumed_refresh(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
        authorization: CBTActorAuthorization,
        stored_refresh: CBTActorRefreshToken,
        refresh_hash: str,
        idempotency_key: UUID,
        now: datetime,
    ) -> CBTActorTokenPair | None:
        """Recover the exact committed rotation associated with a consumed token."""

        try:
            recovered = await CBTActorRefreshRecoveryService.recover(
                server_id=current_server.server_id,
                authorization_id=authorization.id,
                refresh_token_hash=refresh_hash,
                idempotency_key=idempotency_key,
            )
        except CBTRefreshRecoveryUnavailable as exc:
            # Redis unavailability is ambiguous: the receipt may exist but simply
            # be unreadable right now. Never convert that into a reuse revocation.
            raise _refresh_recovery_unavailable(exc) from exc

        if recovered is None:
            return None

        try:
            replacement_hash = hash_actor_token(recovered.refresh_token)
            recovered_access_hash = hash_actor_token(recovered.access_token)
        except ValueError:
            await CBTActorRefreshRecoveryService.delete_best_effort(
                authorization_id=authorization.id
            )
            return None

        replacement = await CBTActorRefreshTokenRepository.get_by_hash(
            db,
            replacement_hash,
            lock=True,
        )
        committed = (
            replacement is not None
            and replacement.authorization_id == authorization.id
            and stored_refresh.replaced_by_token_id == replacement.id
            and replacement.revoked_at is None
            and replacement.consumed_at is None
            and replacement.expires_at > now
            and authorization.access_token_hash == recovered_access_hash
            and authorization.access_token_expires_at == recovered.access_token_expires_at
            and authorization.absolute_expires_at == recovered.refresh_token_expires_at
        )
        if committed:
            return recovered

        # A Redis write can succeed before the SQL transaction later fails. Such
        # a stale receipt must never become an authorization source of truth.
        await CBTActorRefreshRecoveryService.delete_best_effort(authorization_id=authorization.id)
        return None

    @staticmethod
    async def authenticate_actor(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
        access_token: str,
        now: datetime | None = None,
    ) -> AuthenticatedCBTActor:
        """Resolve one opaque actor token into trusted server-side actor context."""

        try:
            access_hash = hash_actor_token(access_token)
        except ValueError as exc:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION) from exc

        authorization = await CBTActorAuthorizationRepository.get_by_access_token_hash(
            db,
            access_hash,
        )
        if authorization is None:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        checked_at = now or _utc_now()
        if (
            authorization.revoked_at is not None
            or authorization.access_token_expires_at <= checked_at
            or authorization.absolute_expires_at <= checked_at
            or authorization.tenant_id != current_server.tenant_id
        ):
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        await CBTActorAuthorizationService._assert_actor_still_eligible(
            db,
            authorization=authorization,
        )

        if authorization.role == "teacher":
            actor_id = authorization.teacher_account_id
            membership_id = authorization.teacher_membership_id
        else:
            actor_id = authorization.tenant_admin_id
            membership_id = None

        if actor_id is None:
            raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

        return AuthenticatedCBTActor(
            authorization_id=authorization.id,
            tenant_id=authorization.tenant_id,
            actor_id=actor_id,
            membership_id=membership_id,
            role=authorization.role,
        )

    @staticmethod
    async def revoke_for_teacher_membership(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        """Revoke every active CBT cloud authorization for one school membership."""

        return await CBTActorAuthorizationRepository.revoke_for_teacher_membership(
            db,
            tenant_id=tenant_id,
            membership_id=membership_id,
            revoked_at=revoked_at or _utc_now(),
            reason=reason,
        )

    @staticmethod
    async def revoke_for_teacher_account(
        db: AsyncSession,
        *,
        teacher_account_id: UUID,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        """Revoke every active CBT cloud authorization owned by a teacher account."""

        return await CBTActorAuthorizationRepository.revoke_for_teacher_account(
            db,
            teacher_account_id=teacher_account_id,
            revoked_at=revoked_at or _utc_now(),
            reason=reason,
        )

    @staticmethod
    async def revoke_for_tenant_admin(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        tenant_admin_id: UUID,
        reason: str,
        revoked_at: datetime | None = None,
    ) -> int:
        """Revoke every active CBT cloud authorization owned by one tenant admin."""

        return await CBTActorAuthorizationRepository.revoke_for_tenant_admin(
            db,
            tenant_id=tenant_id,
            tenant_admin_id=tenant_admin_id,
            revoked_at=revoked_at or _utc_now(),
            reason=reason,
        )

    @staticmethod
    async def _assert_actor_still_eligible(
        db: AsyncSession,
        *,
        authorization: CBTActorAuthorization,
    ) -> None:
        """Defensive eligibility check performed on access and refresh operations."""

        if authorization.role == "teacher":
            membership_id = authorization.teacher_membership_id
            account_id = authorization.teacher_account_id
            if membership_id is None or account_id is None:
                raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

            membership = await TeacherMembershipRepository.get_by_id(
                db,
                membership_id,
                tenant_id=authorization.tenant_id,
                load_account=True,
            )
            account = membership.teacher_account if membership is not None else None
            if (
                membership is None
                or membership.status != TeacherMembershipStatus.ACTIVE
                or membership.teacher_account_id != account_id
                or account is None
                or not account.is_active
                or not account.is_verified
                or account.account_status != TeacherAccountStatus.ACTIVE
            ):
                raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)
            return

        if authorization.role == "admin":
            admin_id = authorization.tenant_admin_id
            if admin_id is None:
                raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)

            admin = await TenantAdminRepository.get_by_tenant_and_id(
                db,
                tenant_id=authorization.tenant_id,
                admin_id=admin_id,
            )
            if (
                admin is None
                or not admin.is_active
                or not admin.is_verified
                or admin.account_status != TenantAdminStatus.ACTIVE
            ):
                raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)
            return

        raise UnauthorizedException(detail=INVALID_CBT_ACTOR_AUTHORIZATION)


class CBTStaffAuthService:
    """Authenticate Weave staff for use on a specific paired CBT server."""

    @staticmethod
    async def authenticate_staff(
        db: AsyncSession,
        *,
        payload: CBTStaffLoginRequest,
        current_server: AuthenticatedCBTServer,
        client_ip: str | None,
        background_tasks: BackgroundTasks | None = None,
    ) -> CBTStaffAuthResponse:
        actor = await AuthService.authenticate_actor(
            db,
            LoginRequest(
                identifier=str(payload.email),
                password=payload.password,
                remember_me=False,
            ),
            background_tasks=background_tasks,
        )

        await SecurityResponseService.enforce_actor_ip_allowed(
            db=db, ip_address=client_ip, actor_type=actor.actor_type
        )
        await PlatformControlService.enforce_actor_allowed(db=db, actor_type=actor.actor_type)

        if actor.actor_type == AuthSessionActorType.TENANT_ADMIN.value:
            identity = CBTStaffAuthService._resolve_admin(
                actor=actor,
                current_server=current_server,
            )
        elif actor.actor_type in {
            AuthSessionActorType.TEACHER.value,
            AuthSessionActorType.TEACHER_ACCOUNT.value,
        }:
            identity = await CBTStaffAuthService._resolve_teacher(
                db=db,
                actor=actor,
                current_server=current_server,
            )
        else:
            raise ForbiddenException(detail="This account is not authorized to use CBT")

        token_pair = await CBTActorAuthorizationService.issue_for_identity(
            db,
            identity=identity,
        )
        return CBTStaffAuthResponse(
            **identity.model_dump(),
            **token_pair.model_dump(),
        )

    @staticmethod
    def _resolve_admin(
        *,
        actor,
        current_server: AuthenticatedCBTServer,
    ) -> CBTStaffIdentity:
        if actor.tenant_id != current_server.tenant_id:
            raise ForbiddenException(detail="This account is not authorized for this CBT server")

        return CBTStaffIdentity(
            actor_id=actor.actor_id,
            membership_id=None,
            tenant_id=current_server.tenant_id,
            role="admin",
            email=actor.email,
            first_name=(actor.user.first_name if actor.user is not None else None),
            last_name=(actor.user.last_name if actor.user is not None else None),
        )

    @staticmethod
    async def _resolve_teacher(
        db: AsyncSession, *, actor, current_server: AuthenticatedCBTServer
    ) -> CBTStaffIdentity:
        account_id = await CBTStaffAuthService._resolve_teacher_account_id(db=db, actor=actor)
        membership = await TeacherMembershipRepository.get_by_account_and_tenant(
            db,
            account_id,
            current_server.tenant_id,
        )
        if membership is None or membership.status != TeacherMembershipStatus.ACTIVE:
            raise ForbiddenException(detail="This account is not authorized for this CBT server")

        account = membership.teacher_account
        if account is None:
            raise ForbiddenException(detail="This account is not authorized for this CBT server")

        return CBTStaffIdentity(
            actor_id=account.id,
            membership_id=membership.id,
            tenant_id=current_server.tenant_id,
            role="teacher",
            email=account.email,
            first_name=account.first_name,
            last_name=account.last_name,
        )

    @staticmethod
    async def _resolve_teacher_account_id(db: AsyncSession, *, actor):
        if actor.actor_type == AuthSessionActorType.TEACHER_ACCOUNT.value:
            return actor.actor_id

        membership = await TeacherMembershipRepository.get_by_id(
            db,
            actor.actor_id,
            load_account=False,
        )
        if membership is None:
            raise ForbiddenException(detail="This account is not authorized to use CBT")
        return membership.teacher_account_id
