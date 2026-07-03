"""Authentication and authorization dependencies for tenant actors and superadmins."""

import uuid
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
from app.modules.auth_identity.models import ActorType
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.parents.repository import ParentRepository
from app.modules.students.models import Student, StudentAccountStatus
from app.modules.students.repository import StudentRepository
from app.modules.superadmin.models import SuperAdmin
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.teachers.models import Teacher, TeacherAccountStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
TokenDependency: TypeAlias = Annotated[str, Depends(oauth2_scheme)]
DbDependency: TypeAlias = Annotated[AsyncSession, Depends(get_db)]

TenantActor: TypeAlias = TenantAdmin | Teacher | Parent | Student
CurrentActor: TypeAlias = TenantActor | SuperAdmin


async def _ensure_active_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
) -> None:
    """Ensure the tenant attached to the actor is active and usable."""

    if tenant_id is None:
        raise ForbiddenException("Actor is not attached to a tenant")

    cache_key = build_cache_key(tenant_prefix(str(tenant_id)), "auth", "active-tenant")

    async def fetch_tenant_state() -> dict[str, str | bool]:
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None or tenant.is_deleted:
            return {"allowed": False, "reason": "Inactive tenant"}
        if tenant.verification_status != TenantVerificationStatus.ACTIVE:
            return {"allowed": False, "reason": "Tenant is not verified"}
        if tenant.status not in (TenantStatus.ACTIVE, TenantStatus.TRIAL):
            return {"allowed": False, "reason": "Inactive tenant"}
        return {"allowed": True, "reason": ""}

    tenant_state = await CacheManager.get_or_set(
        key=cache_key,
        fetcher=fetch_tenant_state,
        ttl=settings.CACHE_SHORT_TTL_SECONDS,
    )

    if not tenant_state.get("allowed"):
        raise ForbiddenException(str(tenant_state.get("reason") or "Inactive tenant"))


async def get_current_actor(
    token: TokenDependency,
    db: DbDependency,
) -> CurrentActor:
    """Return the authenticated actor from the JWT."""

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        actor_id_str: str | None = payload.get("sub")
        actor_type: str | None = payload.get("actor_type")
        account_type: str | None = payload.get("account_type")
        if actor_id_str is None:
            raise UnauthorizedException("Could not validate credentials")

        actor_id = uuid.UUID(actor_id_str)
        if actor_type is None and account_type is None:
            account_type = "superadmin" if payload.get("role") == "superadmin" else None
    except (JWTError, ValueError):
        raise UnauthorizedException("Could not validate credentials")

    if actor_type == ActorType.TENANT_ADMIN.value:
        actor = await TenantAdminRepository.get_by_id(db, actor_id)
        if actor is None:
            raise UnauthorizedException("Tenant admin not found")
        return actor

    if actor_type == ActorType.TEACHER.value:
        actor = await TeacherRepository.get_by_id(db, actor_id)
        if actor is None:
            raise UnauthorizedException("Teacher not found")
        return actor

    if actor_type == ActorType.PARENT.value:
        actor = await ParentRepository.get_by_id(db, actor_id)
        if actor is None:
            raise UnauthorizedException("Parent not found")
        return actor

    if actor_type == ActorType.STUDENT.value:
        actor = await StudentRepository.get_by_id(db, actor_id)
        if actor is None:
            raise UnauthorizedException("Student not found")
        return actor

    if account_type == "superadmin":
        actor = await SuperAdminRepository.get_by_id(db, actor_id)
        if actor is None:
            raise UnauthorizedException("Superadmin not found")
        return actor

    raise UnauthorizedException("Legacy user tokens are no longer supported")


async def get_current_tenant_admin(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> TenantAdmin:
    """Return the current tenant admin actor."""

    if isinstance(actor, SuperAdmin):
        raise ForbiddenException("Tenant admin credentials are required for this operation")
    if not isinstance(actor, TenantAdmin):
        raise ForbiddenException("Tenant admin credentials are required for this operation")
    if not actor.is_active or not actor.is_verified:
        raise ForbiddenException("Inactive account")
    if actor.account_status != TenantAdminStatus.ACTIVE:
        raise ForbiddenException("Inactive account")

    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_teacher(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Teacher:
    """Return the current teacher actor."""

    if not isinstance(actor, Teacher):
        raise ForbiddenException("Teacher credentials are required for this operation")
    if not actor.is_active or not actor.is_verified:
        raise ForbiddenException("Inactive account")
    if actor.account_status != TeacherAccountStatus.ACTIVE:
        raise ForbiddenException("Inactive account")

    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_parent(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Parent:
    """Return the current parent actor."""

    if not isinstance(actor, Parent):
        raise ForbiddenException("Parent credentials are required for this operation")
    if not actor.is_active or not actor.is_verified:
        raise ForbiddenException("Inactive account")
    if actor.account_status != ParentAccountStatus.ACTIVE:
        raise ForbiddenException("Inactive account")

    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_student(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Student:
    """Return the current student actor."""

    if not isinstance(actor, Student):
        raise ForbiddenException("Student credentials are required for this operation")
    if not actor.is_active or not actor.is_verified:
        raise ForbiddenException("Inactive account")
    if actor.account_status != StudentAccountStatus.ACTIVE:
        raise ForbiddenException("Inactive account")

    await _ensure_active_tenant(db, actor.tenant_id)
    return actor


async def get_current_onboarded_student(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> Student:
    """Return the current student only after the default password has been changed."""

    student = await get_current_student(actor, db)

    if student.password_reset_required:
        raise ForbiddenException(
            "You must change your default password before accessing student dashboard resources."
        )

    return student


async def get_current_tenant_member(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
    db: DbDependency,
) -> TenantActor:
    """Return the current tenant actor in the new actor-based architecture."""

    if isinstance(actor, SuperAdmin):
        raise ForbiddenException("Tenant credentials are required for this operation")

    if isinstance(actor, TenantAdmin):
        return await get_current_tenant_admin(actor, db)
    if isinstance(actor, Teacher):
        return await get_current_teacher(actor, db)
    if isinstance(actor, Parent):
        return await get_current_parent(actor, db)
    if isinstance(actor, Student):
        return await get_current_onboarded_student(actor, db)

    raise ForbiddenException("Actor-based tenant credentials are required for this operation")


async def get_current_superadmin(
    actor: Annotated[CurrentActor, Depends(get_current_actor)],
) -> SuperAdmin:
    """Return current superadmin."""

    if isinstance(actor, (TenantAdmin, Teacher, Parent, Student)):
        raise ForbiddenException("Superadmin credentials are required for this operation")
    if not actor.is_active:
        raise ForbiddenException("Inactive superadmin account")
    return actor


async def require_superadmin(
    current_superadmin: Annotated[SuperAdmin, Depends(get_current_superadmin)],
) -> SuperAdmin:
    """Return a dependency that requires superadmin."""

    return current_superadmin
