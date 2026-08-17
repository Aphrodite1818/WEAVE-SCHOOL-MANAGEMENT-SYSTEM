"""Authentication services used by paired CBT servers."""

from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.modules.auth.login_service import AuthService
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.schemas import LoginRequest
from app.modules.cbt.auth.schemas import (
    AuthenticatedCBTServer,
    CBTStaffAuthResponse,
    CBTStaffLoginRequest,
)
from app.modules.cbt.enums import CBTServerStatus
from app.modules.cbt.repository import CBTServerCredentialRepository
from app.modules.cbt.security import hash_server_token
from app.modules.superadmin.platform_control_service import PlatformControlService
from app.modules.superadmin.security_response_service import SecurityResponseService
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.repository import TeacherMembershipRepository


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
        now = datetime.now(timezone.utc)

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
            return CBTStaffAuthService._resolve_admin(
                actor=actor,
                current_server=current_server,
            )
        if actor.actor_type in {
            AuthSessionActorType.TEACHER.value,
            AuthSessionActorType.TEACHER_ACCOUNT.value,
        }:
            return await CBTStaffAuthService._resolve_teacher(
                db=db,
                actor=actor,
                current_server=current_server,
            )
        raise ForbiddenException(detail="This account is not authorized to use CBT")

    @staticmethod
    def _resolve_admin(*, actor, current_server: AuthenticatedCBTServer) -> CBTStaffAuthResponse:
        if actor.tenant_id != current_server.tenant_id:
            raise ForbiddenException(detail="This account is not authorized for this CBT server")

        return CBTStaffAuthResponse(
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
    ) -> CBTStaffAuthResponse:
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

        return CBTStaffAuthResponse(
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
