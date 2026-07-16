"""Session-backed authentication and authorization dependencies."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, TypeAlias

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.base import build_cache_key, tenant_prefix
from app.core.cache.manager import CacheManager
from app.core.dependencies.db import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.repository import AuthSessionRepository
from app.modules.parents.models import (
    Parent,
    ParentAccount,
    ParentAccountStatus,
    ParentMembershipStatus,
)
from app.modules.parents.repository import (
    ParentAccountRepository,
    ParentMembershipRepository,
)
from app.modules.students.models import (
    Student,
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.modules.students.repository import StudentRepository
from app.modules.superadmin.models import SuperAdmin
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.teachers.models import (
    Teacher,
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import (
    TeacherAccountRepository,
    TeacherMembershipRepository,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
TokenDependency: TypeAlias = Annotated[str, Depends(oauth2_scheme)]
DbDependency: TypeAlias = Annotated[AsyncSession, Depends(get_db)]

TenantActor: TypeAlias = TenantAdmin | Teacher | Parent | Student
GlobalAccountActor: TypeAlias = TeacherAccount | ParentAccount
CurrentActor: TypeAlias = TenantActor | GlobalAccountActor | SuperAdmin


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _resolve_session_actor_type(payload: dict) -> AuthSessionActorType:
    raw_type = payload.get("actor_type") or payload.get("account_type")
    if raw_type is None:
        raise UnauthorizedException("Could not validate credentials")
    try:
        return AuthSessionActorType(raw_type)
    except ValueError as exc:
        raise UnauthorizedException("Could not validate credentials") from exc


async def _validate_session(
    db: AsyncSession,
    *,
    payload: dict,
    actor_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
) -> AuthSessionActorType:
    if payload.get("token_type") != "access":
        raise UnauthorizedException("Could not validate credentials")

    session_jti = payload.get("sid")
    if not session_jti:
        raise UnauthorizedException("Session is no longer valid. Please log in again.")

    actor_type = _resolve_session_actor_type(payload)
    session = await AuthSessionRepository.get_session_by_jti(db, session_jti)
    if session is None:
        raise UnauthorizedException("Session is no longer valid. Please log in again.")

    now = datetime.now(timezone.utc)
    if (
        session.revoked_at is not None
        or session.compromised_at is not None
        or _as_aware(session.expires_at) <= now
    ):
        raise UnauthorizedException("Session is no longer valid. Please log in again.")

    if session.actor_id != actor_id or session.actor_type != actor_type:
        raise UnauthorizedException("Could not validate credentials")

    global_actor_types = {
        AuthSessionActorType.SUPERADMIN,
        AuthSessionActorType.TEACHER_ACCOUNT,
        AuthSessionActorType.PARENT_ACCOUNT,
    }
    if actor_type in global_actor_types:
        if session.tenant_id is not None or tenant_id is not None:
            raise UnauthorizedException("Could not validate credentials")
    elif tenant_id is None or session.tenant_id != tenant_id:
        raise UnauthorizedException("Could not validate credentials")

    return actor_type


async def _ensure_active_tenant(db: AsyncSession, tenant_id: uuid.UUID | None) -> None:
    if tenant_id is None:
        raise ForbiddenException("Actor is not attached to a tenant")

    cache_key = build_cache_key(
        tenant_prefix(str(tenant_id)),
        "auth",
        "active-tenant",
    )

    async def fetch_tenant_state() -> dict[str, str | bool]:
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None or tenant.is_deleted:
            return {"allowed": False, "reason": "Inactive tenant"}
        if tenant.verification_status != TenantVerificationStatus.ACTIVE:
            return {"allowed": False, "reason": "Tenant is not verified"}
        if tenant.status not in {TenantStatus.ACTIVE, TenantStatus.TRIAL}:
            return {"allowed": False, "reason": "Inactive tenant"}
        return {"allowed": True, "reason": ""}

    tenant_state = await CacheManager.get_or_set(
        key=cache_key,
        fetcher=fetch_tenant_state,
        ttl=settings.CACHE_SHORT_TTL_SECONDS,
    )
    if not tenant_state.get("allowed"):
        raise ForbiddenException(str(tenant_state.get("reason") or "Inactive tenant"))


async def get_current_actor(token: TokenDependency, db: DbDependency) -> CurrentActor:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        subject = payload.get("sub")
        if subject is None:
            raise UnauthorizedException("Could not validate credentials")

        actor_id = uuid.UUID(subject)
        raw_tenant_id = payload.get("tenant_id")
        tenant_id = uuid.UUID(raw_tenant_id) if raw_tenant_id else None
        actor_type = await _validate_session(
            db,
            payload=payload,
            actor_id=actor_id,
            tenant_id=tenant_id,
        )
    except (JWTError, ValueError, TypeError) as exc:
        raise UnauthorizedException("Could not validate credentials") from exc

    if actor_type == AuthSessionActorType.SUPERADMIN:
        actor = await SuperAdminRepository.get_by_id(db, actor_id)
    elif actor_type == AuthSessionActorType.TENANT_ADMIN:
        actor = await TenantAdminRepository.get_by_id(db, actor_id)
    elif actor_type == AuthSessionActorType.TEACHER_ACCOUNT:
        actor = await TeacherAccountRepository.get_by_id(db, actor_id)
    elif actor_type == AuthSessionActorType.PARENT_ACCOUNT:
        actor = await ParentAccountRepository.get_by_id(db, actor_id)
    elif actor_type == AuthSessionActorType.TEACHER:
        actor = await TeacherMembershipRepository.get_by_id(
            db,
            actor_id,
            tenant_id=tenant_id,
            load_account=True,
            load_subjects=True,
        )
    elif actor_type == AuthSessionActorType.PARENT:
        actor = await ParentMembershipRepository.get_by_id(
            db,
            actor_id,
            tenant_id=tenant_id,
            load_account=True,
        )
    elif actor_type == AuthSessionActorType.STUDENT:
        if tenant_id is None:
            raise UnauthorizedException("Invalid student session")
        actor = await StudentRepository.get_by_id(db, tenant_id, actor_id)
    else:
        actor = None

    if actor is None:
        raise UnauthorizedException("Account not found")
    return actor


async def get_current_superadmin(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
) -> SuperAdmin:
    """Require an active global superadmin session."""
    if not isinstance(actor, SuperAdmin):
        raise ForbiddenException("Superadmin credentials are required.")
    if not actor.is_active:
        raise ForbiddenException("Inactive superadmin account")
    return actor


async def get_current_tenant_admin(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> TenantAdmin:
    if not isinstance(actor, TenantAdmin):
        raise ForbiddenException("Tenant admin credentials are required.")
    if (
        not actor.is_active
        or not actor.is_verified
        or actor.account_status != TenantAdminStatus.ACTIVE
    ):
        raise ForbiddenException("Inactive account")
    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_teacher_account(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
) -> TeacherAccount:
    if not isinstance(actor, TeacherAccount):
        raise ForbiddenException("Teacher account credentials are required.")
    if (
        not actor.is_active
        or not actor.is_verified
        or actor.account_status != TeacherAccountStatus.ACTIVE
    ):
        raise ForbiddenException("Inactive account")
    return actor


async def get_current_parent_account(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
) -> ParentAccount:
    if not isinstance(actor, ParentAccount):
        raise ForbiddenException("Parent account credentials are required.")
    if (
        not actor.is_active
        or not actor.is_verified
        or actor.account_status != ParentAccountStatus.ACTIVE
    ):
        raise ForbiddenException("Inactive account")
    return actor


async def get_current_teacher(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Teacher:
    if not isinstance(actor, Teacher):
        raise ForbiddenException("Teacher membership credentials are required.")
    if (
        not actor.teacher_account.is_active
        or not actor.teacher_account.is_verified
        or actor.teacher_account.account_status != TeacherAccountStatus.ACTIVE
        or actor.status != TeacherMembershipStatus.ACTIVE
    ):
        raise ForbiddenException("Inactive teacher membership")
    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_parent(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Parent:
    if not isinstance(actor, Parent):
        raise ForbiddenException("Parent membership credentials are required.")
    if (
        not actor.parent_account.is_active
        or not actor.parent_account.is_verified
        or actor.parent_account.account_status != ParentAccountStatus.ACTIVE
        or actor.status
        not in {ParentMembershipStatus.ACTIVE, ParentMembershipStatus.READ_ONLY}
    ):
        raise ForbiddenException("Inactive parent membership")
    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_student(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Student:
    if not isinstance(actor, Student):
        raise ForbiddenException("Student credentials are required.")
    if (
        not actor.is_active
        or not actor.is_verified
        or actor.account_status != StudentAccountStatus.ACTIVE
        or actor.is_archived
    ):
        raise ForbiddenException("Inactive account")
    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_onboarded_student(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Student:
    student = await get_current_student(actor, db)
    if student.password_reset_required:
        raise ForbiddenException("Change your temporary password before continuing.")
    if student.profile_status != StudentProfileStatus.COMPLETE:
        raise ForbiddenException("Complete student onboarding before continuing.")
    return student


async def get_current_tenant_member(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> TenantActor:
    if isinstance(actor, TenantAdmin):
        return await get_current_tenant_admin(actor, db)
    if isinstance(actor, Teacher):
        return await get_current_teacher(actor, db)
    if isinstance(actor, Parent):
        return await get_current_parent(actor, db)
    if isinstance(actor, Student):
        return await get_current_student(actor, db)
    raise ForbiddenException("Tenant membership credentials are required.")
