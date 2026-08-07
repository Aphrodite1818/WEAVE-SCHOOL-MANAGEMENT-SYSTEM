"""Unified email-account login and tenant membership selection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password, verify_auth_secret, verify_password
from app.core.exceptions import (
    AccountNotVerifiedException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.modules.auth.models import (
    AuthPurpose,
    AuthRecord,
    AuthSession,
    AuthSessionActorType,
)
from app.modules.auth.schemas import LoginRequest, LoginSessionUser, UpdatePassword
from app.modules.auth.session_service import AuthenticatedActor
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import IdentityResolution
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.parents.models import (
    ParentAccount,
    ParentAccountStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.parents.repository import (
    ParentAccountRepository,
    ParentMembershipRepository,
)
from app.modules.superadmin.models import SuperAdmin
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import (
    TeacherAccountRepository,
    TeacherMembershipRepository,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_email(value: str) -> str:
    return value.strip().casefold()


def _tenant_allows_login(tenant: Tenant | None) -> bool:
    return bool(
        tenant
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.ACTIVE
        and tenant.status in {TenantStatus.ACTIVE, TenantStatus.TRIAL}
    )


def _verification_required_exception(
    *,
    detail: str,
    email: str,
) -> AccountNotVerifiedException:
    return AccountNotVerifiedException(
        detail=detail,
        payload={
            "verification_required": True,
            "email": email,
            "purpose": AuthPurpose.VERIFICATION.value,
            "redirect_to": "/verify-otp",
            "resend_otp_available": True,
        },
    )


class AuthService:
    """Authenticate canonical account owners and select tenant memberships."""

    @staticmethod
    async def _tenant_summary(
        db: AsyncSession,
        membership: ParentMembership | TeacherMembership,
    ) -> dict[str, str | None]:
        tenant = await TenantRepository.get_by_id(db, membership.tenant_id)
        return {
            "membership_id": str(membership.id),
            "tenant_id": str(membership.tenant_id),
            "tenant_name": tenant.school_name if tenant else "School",
            "tenant_logo_url": tenant.logo_url if tenant else None,
            "membership_status": membership.status.value,
        }

    @staticmethod
    async def _parent_membership_actor(
        db: AsyncSession,
        account: ParentAccount,
        membership: ParentMembership,
    ) -> AuthenticatedActor:
        tenant = await TenantRepository.get_by_id(db, membership.tenant_id)
        if not _tenant_allows_login(tenant):
            raise ForbiddenException("The selected school is not active.")
        if membership.status not in {
            ParentMembershipStatus.ACTIVE,
            ParentMembershipStatus.READ_ONLY,
        }:
            raise ForbiddenException("The selected parent membership is inactive.")
        return AuthenticatedActor(
            actor_type=AuthSessionActorType.PARENT.value,
            account_type=AuthSessionActorType.PARENT_ACCOUNT.value,
            actor_id=membership.id,
            email=account.email,
            role="parent",
            tenant_id=membership.tenant_id,
            user=LoginSessionUser(
                id=str(membership.id),
                tenant_id=str(membership.tenant_id),
                school_name=tenant.school_name if tenant else None,
                email=account.email,
                first_name=account.first_name,
                last_name=account.last_name,
                actor_type=AuthSessionActorType.PARENT.value,
                account_type=AuthSessionActorType.PARENT_ACCOUNT.value,
                role="parent",
                tenant_logo_url=tenant.logo_url if tenant else None,
                meta={
                    "parent_account_id": str(account.id),
                    "membership_status": membership.status.value,
                    "profile_completed": account.profile_completed,
                    "onboarding_required": not account.profile_completed,
                },
            ),
        )

    @staticmethod
    async def _teacher_membership_actor(
        db: AsyncSession,
        account: TeacherAccount,
        membership: TeacherMembership,
    ) -> AuthenticatedActor:
        tenant = await TenantRepository.get_by_id(db, membership.tenant_id)
        if not _tenant_allows_login(tenant):
            raise ForbiddenException("The selected school is not active.")
        if membership.status != TeacherMembershipStatus.ACTIVE:
            raise ForbiddenException("The selected teacher membership is inactive.")
        return AuthenticatedActor(
            actor_type=AuthSessionActorType.TEACHER.value,
            account_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
            actor_id=membership.id,
            email=account.email,
            role="teacher",
            tenant_id=membership.tenant_id,
            user=LoginSessionUser(
                id=str(membership.id),
                tenant_id=str(membership.tenant_id),
                school_name=tenant.school_name if tenant else None,
                email=account.email,
                first_name=account.first_name,
                last_name=account.last_name,
                actor_type=AuthSessionActorType.TEACHER.value,
                account_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
                role="teacher",
                passport_photo_url=account.passport_photo_url,
                tenant_logo_url=tenant.logo_url if tenant else None,
                meta={
                    "teacher_account_id": str(account.id),
                    "membership_status": membership.status.value,
                    "profile_completed": account.profile_completed,
                    "onboarding_required": not account.profile_completed,
                },
            ),
        )

    @staticmethod
    async def _parent_account_actor(
        db: AsyncSession,
        account: ParentAccount,
    ) -> AuthenticatedActor:
        memberships = await ParentMembershipRepository.list_usable_for_account(db, account.id)
        if len(memberships) == 1:
            return await AuthService._parent_membership_actor(db, account, memberships[0])
        summaries = [await AuthService._tenant_summary(db, item) for item in memberships]
        return AuthenticatedActor(
            actor_type=AuthSessionActorType.PARENT_ACCOUNT.value,
            account_type=AuthSessionActorType.PARENT_ACCOUNT.value,
            actor_id=account.id,
            email=account.email,
            role="parent",
            user=LoginSessionUser(
                id=str(account.id),
                email=account.email,
                first_name=account.first_name,
                last_name=account.last_name,
                actor_type=AuthSessionActorType.PARENT_ACCOUNT.value,
                account_type=AuthSessionActorType.PARENT_ACCOUNT.value,
                role="parent",
                meta={
                    "profile_completed": account.profile_completed,
                    "onboarding_required": not account.profile_completed,
                    "membership_selection_required": len(memberships) > 1,
                    "memberships": summaries,
                },
            ),
        )

    @staticmethod
    async def _teacher_account_actor(
        db: AsyncSession,
        account: TeacherAccount,
    ) -> AuthenticatedActor:
        memberships = await TeacherMembershipRepository.list_usable_for_account(db, account.id)
        active_memberships = [
            item for item in memberships if item.status == TeacherMembershipStatus.ACTIVE
        ]
        if len(active_memberships) == 1:
            return await AuthService._teacher_membership_actor(db, account, active_memberships[0])
        summaries = [await AuthService._tenant_summary(db, item) for item in active_memberships]
        return AuthenticatedActor(
            actor_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
            account_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
            actor_id=account.id,
            email=account.email,
            role="teacher",
            user=LoginSessionUser(
                id=str(account.id),
                email=account.email,
                first_name=account.first_name,
                last_name=account.last_name,
                actor_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
                account_type=AuthSessionActorType.TEACHER_ACCOUNT.value,
                role="teacher",
                passport_photo_url=account.passport_photo_url,
                meta={
                    "profile_completed": account.profile_completed,
                    "onboarding_required": not account.profile_completed,
                    "membership_selection_required": len(active_memberships) > 1,
                    "memberships": summaries,
                },
            ),
        )

    @staticmethod
    async def authenticate_actor(
        db: AsyncSession,
        payload: LoginRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> AuthenticatedActor:
        identifier = payload.identifier.strip()
        if "@" not in identifier:
            raise UnauthorizedException("Invalid email or password.")
        email = _normalize_email(identifier)

        superadmin = await SuperAdminRepository.get_by_email(db, email)
        if superadmin is not None:
            if not verify_password(payload.password, superadmin.password_hash):
                raise UnauthorizedException("Invalid email or password.")
            if not superadmin.is_active:
                raise UnauthorizedException("Superadmin account is inactive.")
            superadmin.last_login_at = _utc_now()
            db.add(superadmin)
            await db.flush()
            return AuthenticatedActor(
                actor_type=AuthSessionActorType.SUPERADMIN.value,
                account_type=AuthSessionActorType.SUPERADMIN.value,
                actor_id=superadmin.id,
                email=superadmin.email,
                role="superadmin",
                user=LoginSessionUser(
                    id=str(superadmin.id),
                    email=superadmin.email,
                    first_name=getattr(superadmin, "first_name", None),
                    last_name=getattr(superadmin, "last_name", None),
                    actor_type=AuthSessionActorType.SUPERADMIN.value,
                    account_type=AuthSessionActorType.SUPERADMIN.value,
                    role="superadmin",
                ),
            )

        try:
            resolution = await AuthIdentityService.resolve_identifier(
                db,
                identifier=email,
                identifier_type=IdentifierType.EMAIL,
            )
        except NotFoundException as exc:
            raise UnauthorizedException("Invalid email or password.") from exc

        if resolution.actor_type == ActorType.TENANT_ADMIN:
            admin = await TenantAdminRepository.get_by_id(db, resolution.actor_id)
            if admin is None or admin.tenant_id != resolution.tenant_id:
                raise UnauthorizedException("Invalid email or password.")
            if not verify_password(payload.password, admin.password_hash):
                raise UnauthorizedException("Invalid email or password.")
            if not admin.is_verified or admin.account_status == TenantAdminStatus.PENDING:
                raise _verification_required_exception(
                    detail="Account verification is required before login.",
                    email=admin.email,
                )
            tenant = await TenantRepository.get_by_id(db, admin.tenant_id)
            if (
                not admin.is_active
                or admin.account_status != TenantAdminStatus.ACTIVE
                or not _tenant_allows_login(tenant)
            ):
                raise UnauthorizedException("Account is not active.")
            admin.last_login_at = _utc_now()
            db.add(admin)
            await db.flush()
            return AuthenticatedActor(
                actor_type=AuthSessionActorType.TENANT_ADMIN.value,
                account_type=AuthSessionActorType.TENANT_ADMIN.value,
                actor_id=admin.id,
                email=admin.email,
                role="admin",
                tenant_id=admin.tenant_id,
                user=LoginSessionUser(
                    id=str(admin.id),
                    tenant_id=str(admin.tenant_id),
                    school_name=tenant.school_name if tenant else None,
                    email=admin.email,
                    actor_type=AuthSessionActorType.TENANT_ADMIN.value,
                    account_type=AuthSessionActorType.TENANT_ADMIN.value,
                    role="admin",
                    passport_photo_url=getattr(admin, "passport_photo_url", None),
                    tenant_logo_url=tenant.logo_url if tenant else None,
                ),
            )

        if resolution.actor_type in {ActorType.PARENT_ACCOUNT, ActorType.PARENT}:
            account = await ParentAccountRepository.get_by_id(db, resolution.actor_id)
            if account is None or not verify_password(payload.password, account.password_hash):
                raise UnauthorizedException("Invalid email or password.")
            if not account.is_verified or account.account_status == ParentAccountStatus.PENDING:
                raise _verification_required_exception(
                    detail="Verify the parent account before login.",
                    email=account.email,
                )
            if not account.is_active or account.account_status != ParentAccountStatus.ACTIVE:
                raise UnauthorizedException("Parent account is not active.")
            account.last_login_at = _utc_now()
            db.add(account)
            await db.flush()
            return await AuthService._parent_account_actor(db, account)

        if resolution.actor_type in {ActorType.TEACHER_ACCOUNT, ActorType.TEACHER}:
            account = await TeacherAccountRepository.get_by_id(db, resolution.actor_id)
            if account is None or not verify_password(payload.password, account.password_hash):
                raise UnauthorizedException("Invalid email or password.")
            if not account.is_verified or account.account_status == TeacherAccountStatus.PENDING:
                raise _verification_required_exception(
                    detail="Verify the teacher account before login.",
                    email=account.email,
                )
            if not account.is_active or account.account_status != TeacherAccountStatus.ACTIVE:
                raise UnauthorizedException("Teacher account is not active.")
            account.last_login_at = _utc_now()
            db.add(account)
            await db.flush()
            return await AuthService._teacher_account_actor(db, account)

        raise UnauthorizedException("This identifier cannot use email login.")

    @staticmethod
    async def select_membership(
        db: AsyncSession,
        *,
        account: ParentAccount | TeacherAccount,
        membership_id: uuid.UUID,
    ) -> AuthenticatedActor:
        if isinstance(account, ParentAccount):
            membership = await ParentMembershipRepository.get_by_id(
                db,
                membership_id,
                load_account=True,
            )
            if membership is None or membership.parent_account_id != account.id:
                raise ForbiddenException("Parent membership does not belong to this account.")
            return await AuthService._parent_membership_actor(db, account, membership)

        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            load_account=True,
        )
        if membership is None or membership.teacher_account_id != account.id:
            raise ForbiddenException("Teacher membership does not belong to this account.")
        return await AuthService._teacher_membership_actor(db, account, membership)

    @staticmethod
    async def resolve_email_owner(
        db: AsyncSession,
        *,
        email: str,
        lock: bool = False,
    ) -> tuple[TenantAdmin | ParentAccount | TeacherAccount, IdentityResolution]:
        resolution = await AuthIdentityService.resolve_identifier(
            db,
            identifier=_normalize_email(email),
            identifier_type=IdentifierType.EMAIL,
        )
        if resolution.actor_type == ActorType.TENANT_ADMIN:
            actor = await TenantAdminRepository.get_by_id(db, resolution.actor_id, lock=lock)
        elif resolution.actor_type in {ActorType.PARENT_ACCOUNT, ActorType.PARENT}:
            actor = await ParentAccountRepository.get_by_id(db, resolution.actor_id, lock=lock)
        elif resolution.actor_type in {ActorType.TEACHER_ACCOUNT, ActorType.TEACHER}:
            actor = await TeacherAccountRepository.get_by_id(db, resolution.actor_id, lock=lock)
        else:
            actor = None
        if actor is None:
            raise NotFoundException("Account not found.")
        return actor, resolution

    @staticmethod
    async def reset_password(db: AsyncSession, payload: UpdatePassword) -> None:
        email = _normalize_email(str(payload.email))
        now = _utc_now()
        records = (
            (
                await db.execute(
                    select(AuthRecord)
                    .where(
                        AuthRecord.email == email,
                        AuthRecord.purpose == AuthPurpose.PASSWORD_RESET,
                        AuthRecord.is_used.is_(False),
                        AuthRecord.expires_at > now,
                    )
                    .order_by(AuthRecord.created_at.desc())
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        record = next(
            (
                item
                for item in records
                if verify_auth_secret(payload.reset_token, item.hashed_value)
            ),
            None,
        )
        if record is None:
            raise BadRequestException("Password reset token is invalid or expired.")
        actor, _ = await AuthService.resolve_email_owner(db, email=email, lock=True)
        actor.password_hash = hash_password(payload.new_password)
        record.is_used = True
        db.add(actor)
        db.add(record)

        session_filters = []
        if isinstance(actor, TenantAdmin):
            session_filters.append(
                (AuthSession.actor_type == AuthSessionActorType.TENANT_ADMIN)
                & (AuthSession.actor_id == actor.id)
            )
        elif isinstance(actor, ParentAccount):
            memberships = await ParentAccountRepository.list_memberships(db, actor.id)
            session_filters.append(
                (AuthSession.actor_type == AuthSessionActorType.PARENT_ACCOUNT)
                & (AuthSession.actor_id == actor.id)
            )
            if memberships:
                session_filters.append(
                    (AuthSession.actor_type == AuthSessionActorType.PARENT)
                    & AuthSession.actor_id.in_([item.id for item in memberships])
                )
        else:
            memberships = await TeacherAccountRepository.list_memberships(db, actor.id)
            session_filters.append(
                (AuthSession.actor_type == AuthSessionActorType.TEACHER_ACCOUNT)
                & (AuthSession.actor_id == actor.id)
            )
            if memberships:
                session_filters.append(
                    (AuthSession.actor_type == AuthSessionActorType.TEACHER)
                    & AuthSession.actor_id.in_([item.id for item in memberships])
                )
        if session_filters:
            await db.execute(
                update(AuthSession)
                .where(or_(*session_filters), AuthSession.revoked_at.is_(None))
                .values(revoked_at=now, revoked_reason="password_reset")
            )
        await db.commit()
