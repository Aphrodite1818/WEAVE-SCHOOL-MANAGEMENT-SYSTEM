# ====================================== #
#            auth/service.py             #
# ====================================== #

"""Authentication, OTP, invite, and persistent-session services."""

from __future__ import annotations

import random
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import (
    create_access_token,
    generate_refresh_token,
    generate_token_jti,
    hash_auth_secret,
    hash_otp,
    hash_password,
    hash_refresh_token,
    verify_otp as verify_otp_hash,
    verify_password,
)
from app.config.settings import settings
from app.core.exceptions import (
    AccountNotVerifiedException,
    BadRequestException,
    NotFoundException,
    TooManyRequestsException,
    UnauthorizedException,
)
from app.core.utils.email import send_email
from app.core.utils.email_templates import (
    get_otp_email_html,
    get_tenant_invite_email_html,
    get_user_invite_email_html,
)
from app.core.utils.otp_rate_limiter import OTPRateLimiter
from app.modules.auth.models import (
    AuthPurpose,
    AuthRecord,
    AuthRefreshToken,
    AuthSession,
    AuthSessionActorType,
)
from app.modules.auth.repository import (
    AuthRefreshTokenRepository,
    AuthSessionRepository,
)
from app.modules.auth.schemas import (
    LoginRequest,
    LoginSessionUser,
    RequestOTP,
    TenantActivationRequest,
    UpdatePassword,
    UserInviteAcceptanceRequest,
    VerifyOTP,
)
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import IdentityResolution
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.parents.repository import ParentRepository
from app.modules.students.models import Student, StudentAccountStatus
from app.modules.students.repository import StudentAccessCodeRepository, StudentRepository
from app.modules.superadmin.models import SuperAdmin
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


EmailActor = TenantAdmin | Teacher | Parent
LAST_LOGIN_UPDATE_INTERVAL = timedelta(minutes=10)


def _normalize_email(email: str) -> str:
    """Normalize the email address."""

    return email.strip().lower()


def _enum_value(value: str | object | None) -> str | None:
    """Return a stable string representation for enum-like values."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "value", str(value))


def _ensure_timezone_aware(value: datetime) -> datetime:
    """Return a timezone-aware datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _last_login_is_due(last_login_at: datetime | None, now: datetime) -> bool:
    """Return whether a login timestamp should be written."""

    if last_login_at is None:
        return True
    return now - _ensure_timezone_aware(last_login_at) >= LAST_LOGIN_UPDATE_INTERVAL


async def _update_last_login_if_due(
    db: AsyncSession,
    actor: SuperAdmin | TenantAdmin | Teacher | Parent | Student,
    now: datetime | None = None,
) -> bool:
    """Update last_login_at only when it meaningfully changes."""

    now = now or datetime.now(timezone.utc)
    if not _last_login_is_due(actor.last_login_at, now):
        return False

    actor.last_login_at = now
    db.add(actor)
    await db.flush()
    return True


async def _get_platform_email_conflicts(
    db: AsyncSession,
    email: str,
) -> tuple[object | None, Tenant | None, SuperAdmin | None]:
    """Return cross-platform email conflicts."""

    normalized_email = _normalize_email(email)
    existing_user = await TenantAdminRepository.get_by_email(db, normalized_email)
    if existing_user is None:
        existing_user = await TeacherRepository.get_by_email(db, normalized_email)
    if existing_user is None:
        existing_user = await ParentRepository.get_by_email(db, normalized_email)

    existing_tenant = await TenantRepository.get_by_email_including_deleted(
        db,
        normalized_email,
    )
    existing_superadmin = await SuperAdminRepository.get_by_email(db, normalized_email)
    return existing_user, existing_tenant, existing_superadmin


async def _authenticate_superadmin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> SuperAdmin | None:
    """Authenticate a superadmin by email/password."""

    superadmin = await SuperAdminRepository.get_by_email(db, email)
    if superadmin is None:
        return None
    if not verify_password(password, superadmin.password_hash):
        raise UnauthorizedException("Invalid email or password")
    if not superadmin.is_active:
        raise UnauthorizedException("Superadmin account is not active")

    await _update_last_login_if_due(db, superadmin)
    return superadmin


async def _authenticate_tenant_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    resolution: IdentityResolution | None = None,
    tenant: Tenant | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> TenantAdmin | None:
    """Authenticate a tenant admin through AuthIdentity."""

    normalized_email = _normalize_email(email)

    if resolution is None:
        try:
            resolution = await AuthIdentityService.resolve_identifier(
                db=db,
                identifier=normalized_email,
                identifier_type=IdentifierType.EMAIL,
            )
        except NotFoundException:
            return None

    if resolution.actor_type != ActorType.TENANT_ADMIN:
        return None

    admin = await TenantAdminRepository.get_by_id(
        db=db,
        admin_id=resolution.actor_id,
    )
    if admin is None or admin.tenant_id != resolution.tenant_id:
        raise UnauthorizedException("Account not found")

    if not verify_password(password, admin.password_hash):
        raise UnauthorizedException("Invalid email or password")

    if tenant is None:
        tenant = await TenantRepository.get_by_id(db, admin.tenant_id)
    if tenant is None:
        raise UnauthorizedException("Account not found")

    if tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION:
        await AuthService._raise_verification_required(
            db,
            email=normalized_email,
            background_tasks=background_tasks,
        )

    if tenant.verification_status == TenantVerificationStatus.REJECTED:
        raise UnauthorizedException("Account has been rejected. Please contact support.")

    if not _tenant_allows_login(tenant):
        raise UnauthorizedException("Account is not active")

    if not admin.is_active or admin.account_status != TenantAdminStatus.ACTIVE:
        raise UnauthorizedException("Account is not active")

    if not admin.is_verified:
        await AuthService._raise_verification_required(
            db,
            email=normalized_email,
            background_tasks=background_tasks,
        )

    await _update_last_login_if_due(db, admin)
    return admin


def _tenant_allows_login(tenant: Tenant | None) -> bool:
    """Return whether a tenant currently allows user login."""

    return (
        tenant is not None
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.ACTIVE
        and tenant.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)
    )


def _tenant_allows_user_invite_completion(tenant: Tenant | None) -> bool:
    """Return whether user invite completion is allowed."""

    return _tenant_allows_login(tenant)


def _tenant_allows_activation_completion(tenant: Tenant | None) -> bool:
    """Return whether tenant activation completion is allowed."""

    return (
        tenant is not None
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION
        and tenant.status == TenantStatus.INACTIVE
    )


def _tenant_allows_otp_verification(tenant: Tenant | None) -> bool:
    """Return whether OTP verification is allowed for a tenant signup."""

    return (
        tenant is not None
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION
        and tenant.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)
    )


def _resolve_identifier_type(identifier: str) -> IdentifierType:
    """Infer the identifier type from the login payload."""

    return IdentifierType.EMAIL if "@" in identifier else IdentifierType.ADMISSION_NUMBER


async def _authenticate_tenant_actor(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    identifier_type: IdentifierType,
    background_tasks: BackgroundTasks | None = None,
) -> "AuthenticatedActor | None":
    """Authenticate a non-superadmin actor via AuthIdentity."""

    try:
        resolution = await AuthIdentityService.resolve_identifier(
            db=db,
            identifier=identifier,
            identifier_type=identifier_type,
        )
    except NotFoundException:
        return None

    tenant = await TenantRepository.get_by_id(db, resolution.tenant_id)
    if tenant is None:
        raise UnauthorizedException("Account not found")

    if resolution.actor_type == ActorType.TENANT_ADMIN:
        tenant_admin = await _authenticate_tenant_admin(
            db,
            email=identifier,
            password=password,
            resolution=resolution,
            tenant=tenant,
            background_tasks=background_tasks,
        )
        if tenant_admin is None:
            return None
        return AuthenticatedActor(
            actor_type=ActorType.TENANT_ADMIN.value,
            account_type=ActorType.TENANT_ADMIN.value,
            actor_id=tenant_admin.id,
            email=tenant_admin.email,
            role="admin",
            tenant_id=tenant_admin.tenant_id,
            user=LoginSessionUser(
                id=str(tenant_admin.id),
                tenant_id=str(tenant_admin.tenant_id),
                school_name=tenant.school_name,
                email=tenant_admin.email,
                actor_type=ActorType.TENANT_ADMIN.value,
                account_type=ActorType.TENANT_ADMIN.value,
                role="admin",
            ),
        )

    if tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION:
        if tenant.status == TenantStatus.INACTIVE:
            raise AccountNotVerifiedException(
                detail="Account not activated. Please use the activation link sent to your email.",
            )
        if identifier_type == IdentifierType.EMAIL:
            await AuthService._raise_verification_required(
                db,
                email=identifier,
                background_tasks=background_tasks,
            )

    if tenant.verification_status == TenantVerificationStatus.REJECTED:
        raise UnauthorizedException("Account has been rejected. Please contact support.")

    if not _tenant_allows_login(tenant):
        raise UnauthorizedException("Account is not active")

    if resolution.actor_type == ActorType.TEACHER:
        teacher = await TeacherRepository.get_by_id(db, resolution.actor_id)
        if teacher is None:
            raise UnauthorizedException("Account not found")
        if not verify_password(password, teacher.password_hash):
            raise UnauthorizedException("Invalid credentials")
        if (
            not teacher.is_active
            or not teacher.is_verified
            or teacher.account_status != TeacherAccountStatus.ACTIVE
            or teacher.status != TeacherStatus.ACTIVE
        ):
            raise UnauthorizedException("Account is not active")

        await _update_last_login_if_due(db, teacher)
        return AuthenticatedActor(
            actor_type=ActorType.TEACHER.value,
            account_type=ActorType.TEACHER.value,
            actor_id=teacher.id,
            email=teacher.email,
            role="teacher",
            tenant_id=teacher.tenant_id,
            user=LoginSessionUser(
                id=str(teacher.id),
                tenant_id=str(teacher.tenant_id),
                school_name=tenant.school_name,
                email=teacher.email,
                first_name=teacher.first_name,
                last_name=teacher.last_name,
                actor_type=ActorType.TEACHER.value,
                account_type=ActorType.TEACHER.value,
                role="teacher",
            ),
        )

    if resolution.actor_type == ActorType.PARENT:
        parent = await ParentRepository.get_by_id(db, resolution.actor_id)
        if parent is None:
            raise UnauthorizedException("Account not found")
        if not verify_password(password, parent.password_hash):
            raise UnauthorizedException("Invalid credentials")
        if (
            not parent.is_active
            or not parent.is_verified
            or parent.account_status != ParentAccountStatus.ACTIVE
        ):
            raise UnauthorizedException("Account is not active")

        await _update_last_login_if_due(db, parent)
        return AuthenticatedActor(
            actor_type=ActorType.PARENT.value,
            account_type=ActorType.PARENT.value,
            actor_id=parent.id,
            email=parent.email,
            role="parent",
            tenant_id=parent.tenant_id,
            user=LoginSessionUser(
                id=str(parent.id),
                tenant_id=str(parent.tenant_id),
                school_name=tenant.school_name,
                email=parent.email,
                first_name=parent.first_name,
                last_name=parent.last_name,
                actor_type=ActorType.PARENT.value,
                account_type=ActorType.PARENT.value,
                role="parent",
            ),
        )

    if resolution.actor_type == ActorType.STUDENT:
        student = await StudentRepository.get_by_id(db, resolution.actor_id)
        if student is None or student.tenant_id != resolution.tenant_id:
            raise UnauthorizedException("Account not found")

        password_matches = (
            student.password_hash is not None
            and verify_password(password, student.password_hash)
        )

        access_code = None
        if not password_matches:
            access_code = await StudentAccessCodeRepository.get_active_code_by_digest(
                db=db,
                tenant_id=student.tenant_id,
                student_id=student.id,
                code_digest=hash_auth_secret(password),
            )

        if not password_matches and access_code is None:
            raise UnauthorizedException("Invalid credentials")

        if access_code is not None:
            student.password_reset_required = True
            db.add(student)
            await db.flush()

        if (
            not student.is_active
            or not student.is_verified
            or student.account_status != StudentAccountStatus.ACTIVE
        ):
            raise UnauthorizedException("Account is not active")

        await _update_last_login_if_due(db, student)
        return AuthenticatedActor(
            actor_type=ActorType.STUDENT.value,
            account_type=ActorType.STUDENT.value,
            actor_id=student.id,
            email=student.admission_number,
            role="student",
            tenant_id=student.tenant_id,
            password_reset_required=student.password_reset_required,
            user=LoginSessionUser(
                id=str(student.id),
                tenant_id=str(student.tenant_id),
                school_name=tenant.school_name,
                email=student.admission_number,
                admission_number=student.admission_number,
                first_name=student.first_name,
                last_name=student.last_name,
                actor_type=ActorType.STUDENT.value,
                account_type=ActorType.STUDENT.value,
                role="student",
                password_reset_required=student.password_reset_required,
                profile_status=_enum_value(student.profile_status),
            ),
        )

    return None


async def _get_email_actor_with_tenant(
    db: AsyncSession,
    email: str,
    *,
    lock: bool = False,
) -> tuple[EmailActor, Tenant, ActorType]:
    """Resolve an email identity to an actor record and its tenant."""

    normalized_email = _normalize_email(email)

    try:
        resolution = await AuthIdentityService.resolve_identifier(
            db=db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )
    except NotFoundException as exc:
        raise NotFoundException("Account with this email not found.") from exc

    if resolution.actor_type == ActorType.TENANT_ADMIN:
        actor = await TenantAdminRepository.get_by_id(
            db,
            admin_id=resolution.actor_id,
            lock=lock,
        )
    elif resolution.actor_type == ActorType.TEACHER:
        actor = await TeacherRepository.get_by_id(
            db,
            teacher_id=resolution.actor_id,
            lock=lock,
        )
    elif resolution.actor_type == ActorType.PARENT:
        actor = await ParentRepository.get_by_id(
            db,
            parent_id=resolution.actor_id,
            lock=lock,
        )
    else:
        raise BadRequestException(
            "This email address is not eligible for this authentication flow."
        )

    if actor is None:
        raise NotFoundException("Account not found.")

    tenant = await TenantRepository.get_by_id(
        db,
        resolution.tenant_id,
        lock=lock,
    )
    if tenant is None:
        raise NotFoundException("Tenant not found.")

    if actor.tenant_id != tenant.id:
        raise BadRequestException("This account is not linked to the resolved tenant.")

    return actor, tenant, resolution.actor_type


def _email_actor_can_reset_password(
    actor: EmailActor | None,
    tenant: Tenant | None,
) -> bool:
    """Return whether an email-based actor can reset password."""

    return (
        actor is not None
        and actor.is_active
        and actor.is_verified
        and _tenant_allows_login(tenant)
        and (
            (
                isinstance(actor, TenantAdmin)
                and actor.account_status == TenantAdminStatus.ACTIVE
            )
            or (
                isinstance(actor, Teacher)
                and actor.account_status == TeacherAccountStatus.ACTIVE
                and actor.status == TeacherStatus.ACTIVE
            )
            or (
                isinstance(actor, Parent)
                and actor.account_status == ParentAccountStatus.ACTIVE
            )
        )
    )


@dataclass
class AuthenticatedActor:
    """Authenticated actor payload shared between login and session creation."""

    actor_type: str
    account_type: str
    actor_id: uuid.UUID
    email: str
    role: str | None = None
    tenant_id: uuid.UUID | None = None
    password_reset_required: bool | None = None
    user: LoginSessionUser | None = None


@dataclass
class AuthSessionTokenPair:
    """Tokens and session metadata returned after login or refresh."""

    access_token: str
    refresh_token: str
    session_id: uuid.UUID
    session_jti: str
    refresh_token_expires_at: datetime


class AuthSessionService:
    """Business logic for persistent auth sessions and refresh-token rotation."""

    DEFAULT_SESSION_DAYS = settings.DEFAULT_SESSION_DAYS
    REMEMBER_ME_SESSION_DAYS = settings.REMEMBER_ME_SESSION_DAYS

    @staticmethod
    def _session_lifetime(*, remember_me: bool) -> timedelta:
        """Return session lifetime."""

        days = (
            AuthSessionService.REMEMBER_ME_SESSION_DAYS
            if remember_me
            else AuthSessionService.DEFAULT_SESSION_DAYS
        )
        return timedelta(days=days)

    @staticmethod
    def _to_session_actor_type(actor_type: str) -> AuthSessionActorType:
        """Convert authenticated actor type into session actor type."""

        try:
            return AuthSessionActorType(actor_type)
        except ValueError as exc:
            raise BadRequestException("Unsupported authenticated actor type.") from exc

    @staticmethod
    def _build_access_token_claims_from_actor(
        actor: AuthenticatedActor,
    ) -> dict[str, str | None]:
        """Build access-token claims from a freshly authenticated actor."""

        claims: dict[str, str | None] = {
            "sub": str(actor.actor_id),
            "email": actor.email,
            "actor_type": actor.actor_type,
            "role": actor.role,
            "account_type": actor.account_type,
        }
        if actor.tenant_id is not None:
            claims["tenant_id"] = str(actor.tenant_id)
        return claims

    @staticmethod
    async def _build_access_token_claims_from_session(
        db: AsyncSession,
        session: AuthSession,
    ) -> dict[str, str]:
        """Rebuild access-token claims from an existing session."""

        if session.actor_type == AuthSessionActorType.SUPERADMIN:
            superadmin = await SuperAdminRepository.get_by_id(db, session.actor_id)
            if superadmin is None or not superadmin.is_active:
                raise UnauthorizedException("Account is not active")
            return {
                "sub": str(superadmin.id),
                "email": superadmin.email,
                "actor_type": AuthSessionActorType.SUPERADMIN.value,
                "role": "superadmin",
                "account_type": AuthSessionActorType.SUPERADMIN.value,
            }

        if session.tenant_id is None:
            raise UnauthorizedException("Invalid session")

        tenant = await TenantRepository.get_by_id(db, session.tenant_id)
        if not _tenant_allows_login(tenant):
            raise UnauthorizedException("Account is not active")

        if session.actor_type == AuthSessionActorType.TENANT_ADMIN:
            admin = await TenantAdminRepository.get_active_by_id(
                db=db,
                admin_id=session.actor_id,
            )
            if (
                admin is None
                or admin.tenant_id != session.tenant_id
                or not admin.is_active
                or not admin.is_verified
                or admin.account_status != TenantAdminStatus.ACTIVE
            ):
                raise UnauthorizedException("Account is not active")
            return {
                "sub": str(admin.id),
                "email": admin.email,
                "actor_type": AuthSessionActorType.TENANT_ADMIN.value,
                "role": "admin",
                "account_type": AuthSessionActorType.TENANT_ADMIN.value,
                "tenant_id": str(admin.tenant_id),
            }

        if session.actor_type == AuthSessionActorType.TEACHER:
            teacher = await TeacherRepository.get_by_id(db, session.actor_id)
            if (
                teacher is None
                or teacher.tenant_id != session.tenant_id
                or not teacher.is_active
                or not teacher.is_verified
                or teacher.account_status != TeacherAccountStatus.ACTIVE
                or teacher.status != TeacherStatus.ACTIVE
            ):
                raise UnauthorizedException("Account is not active")
            return {
                "sub": str(teacher.id),
                "email": teacher.email,
                "actor_type": AuthSessionActorType.TEACHER.value,
                "role": "teacher",
                "account_type": AuthSessionActorType.TEACHER.value,
                "tenant_id": str(teacher.tenant_id),
            }

        if session.actor_type == AuthSessionActorType.PARENT:
            parent = await ParentRepository.get_by_id(db, session.actor_id)
            if (
                parent is None
                or parent.tenant_id != session.tenant_id
                or not parent.is_active
                or not parent.is_verified
                or parent.account_status != ParentAccountStatus.ACTIVE
            ):
                raise UnauthorizedException("Account is not active")
            return {
                "sub": str(parent.id),
                "email": parent.email,
                "actor_type": AuthSessionActorType.PARENT.value,
                "role": "parent",
                "account_type": AuthSessionActorType.PARENT.value,
                "tenant_id": str(parent.tenant_id),
            }

        if session.actor_type == AuthSessionActorType.STUDENT:
            student = await StudentRepository.get_by_id(db, session.actor_id)
            if (
                student is None
                or student.tenant_id != session.tenant_id
                or not student.is_active
                or not student.is_verified
                or student.account_status != StudentAccountStatus.ACTIVE
            ):
                raise UnauthorizedException("Account is not active")
            return {
                "sub": str(student.id),
                "email": student.admission_number,
                "actor_type": AuthSessionActorType.STUDENT.value,
                "role": "student",
                "account_type": AuthSessionActorType.STUDENT.value,
                "tenant_id": str(student.tenant_id),
            }

        raise UnauthorizedException("Invalid session")

    @staticmethod
    async def create_login_session(
        db: AsyncSession,
        *,
        actor: AuthenticatedActor,
        user_agent: str | None = None,
        ip_address: str | None = None,
        remember_me: bool = False,
    ) -> AuthSessionTokenPair:
        """Create a database-backed login session and first refresh token."""

        now = datetime.now(timezone.utc)
        session_expires_at = now + AuthSessionService._session_lifetime(
            remember_me=remember_me,
        )
        session_jti = generate_token_jti()
        raw_refresh_token = generate_refresh_token()

        session = AuthSession(
            tenant_id=actor.tenant_id,
            actor_type=AuthSessionService._to_session_actor_type(actor.actor_type),
            actor_id=actor.actor_id,
            session_jti=session_jti,
            user_agent=user_agent,
            ip_address=ip_address,
            remember_me=remember_me,
            last_used_at=now,
            expires_at=session_expires_at,
        )
        session = await AuthSessionRepository.create_session(db, session)

        refresh_token = AuthRefreshToken(
            session_id=session.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            token_jti=generate_token_jti(),
            issued_ip_address=ip_address,
            issued_user_agent=user_agent,
            expires_at=session_expires_at,
        )
        await AuthRefreshTokenRepository.create_refresh_token(db, refresh_token)

        access_token = create_access_token(
            data=AuthSessionService._build_access_token_claims_from_actor(actor),
            session_jti=session.session_jti,
        )
        await db.commit()

        return AuthSessionTokenPair(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            session_id=session.id,
            session_jti=session.session_jti,
            refresh_token_expires_at=session_expires_at,
        )

    @staticmethod
    async def rotate_refresh_token(
        db: AsyncSession,
        *,
        background_tasks: BackgroundTasks,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> AuthSessionTokenPair:
        """Rotate a refresh token and return a new access/refresh pair."""

        now = datetime.now(timezone.utc)
        stored_token = await AuthRefreshTokenRepository.get_by_hash(
            db,
            hash_refresh_token(refresh_token),
            lock=True,
        )
        if stored_token is None:
            raise UnauthorizedException("Invalid session")

        session = await AuthSessionRepository.get_session_by_id(
            db,
            stored_token.session_id,
            lock=True,
        )
        if session is None:
            raise UnauthorizedException("Invalid session")

        if stored_token.used_at is not None or stored_token.revoked_at is not None:
            await AuthRefreshTokenRepository.mark_reuse_detected(
                db,
                stored_token,
                detected_at=now,
            )
            await AuthSessionRepository.mark_session_compromised(
                db,
                session,
                background_tasks=background_tasks,
                compromised_at=now,
                reason="refresh_reuse_detected",
            )
            await AuthRefreshTokenRepository.revoke_tokens_for_session(
                db,
                session_id=session.id,
                revoked_at=now,
                reason="refresh_reuse_detected",
            )
            await db.commit()
            raise UnauthorizedException("Session expired. Please log in again.")

        if (
            _ensure_timezone_aware(stored_token.expires_at) <= now
            or _ensure_timezone_aware(session.expires_at) <= now
        ):
            await AuthRefreshTokenRepository.revoke_token(
                db,
                stored_token,
                revoked_at=now,
                reason="expired",
            )
            await AuthSessionRepository.revoke_session(
                db,
                session,
                revoked_at=now,
                reason="expired",
            )
            await db.commit()
            raise UnauthorizedException("Session expired. Please log in again.")

        if session.revoked_at is not None or session.compromised_at is not None:
            raise UnauthorizedException("Session expired. Please log in again.")

        raw_new_refresh_token = generate_refresh_token()
        new_refresh_token = AuthRefreshToken(
            session_id=session.id,
            token_hash=hash_refresh_token(raw_new_refresh_token),
            token_jti=generate_token_jti(),
            issued_ip_address=ip_address,
            issued_user_agent=user_agent,
            expires_at=session.expires_at,
        )
        new_refresh_token = await AuthRefreshTokenRepository.create_refresh_token(
            db,
            new_refresh_token,
        )
        await AuthRefreshTokenRepository.mark_used(
            db,
            stored_token,
            used_at=now,
            replaced_by_token_id=new_refresh_token.id,
        )
        await AuthSessionRepository.touch_session(db, session, last_used_at=now)

        access_token = create_access_token(
            data=await AuthSessionService._build_access_token_claims_from_session(
                db,
                session,
            ),
            session_jti=session.session_jti,
        )
        await db.commit()

        return AuthSessionTokenPair(
            access_token=access_token,
            refresh_token=raw_new_refresh_token,
            session_id=session.id,
            session_jti=session.session_jti,
            refresh_token_expires_at=session.expires_at,
        )

    @staticmethod
    async def logout_by_refresh_token(
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> None:
        """Revoke the session associated with a refresh token."""

        now = datetime.now(timezone.utc)
        stored_token = await AuthRefreshTokenRepository.get_by_hash(
            db,
            hash_refresh_token(refresh_token),
            lock=True,
        )
        if stored_token is None:
            return

        session = await AuthSessionRepository.get_session_by_id(
            db,
            stored_token.session_id,
            lock=True,
        )
        if session is not None and session.revoked_at is None:
            await AuthSessionRepository.revoke_session(
                db,
                session,
                revoked_at=now,
                reason="logout",
            )

        await AuthRefreshTokenRepository.revoke_tokens_for_session(
            db,
            session_id=stored_token.session_id,
            revoked_at=now,
            reason="logout",
        )
        await db.commit()


class AuthService:
    """Business logic for the auth domain."""

    @staticmethod
    def _build_verification_required_payload(
        email: str,
        detail: str,
        *,
        resend_otp_available: bool,
    ) -> dict[str, str | bool]:
        """Build verification required payload."""

        normalized_email = _normalize_email(email)
        return {
            "message": detail,
            "verification_required": True,
            "email": normalized_email,
            "purpose": AuthPurpose.VERIFICATION.value,
            "redirect_to": "/verify-otp",
            "resend_otp_available": resend_otp_available,
        }

    @staticmethod
    def _otp_verification_headers(
        email: str,
        *,
        resend_otp_available: bool,
    ) -> dict[str, str]:
        """Build verification-required headers."""

        normalized_email = _normalize_email(email)
        return {
            "X-Verification-Required": "true",
            "X-Resend-OTP-Available": str(resend_otp_available).lower(),
            "X-Email": normalized_email,
            "X-OTP-Purpose": AuthPurpose.VERIFICATION.value,
            "X-Redirect-To": "/verify-otp",
        }

    @staticmethod
    async def _raise_verification_required(
        db: AsyncSession,
        *,
        email: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        """Raise verification-required and send/reuse OTP."""

        normalized_email = _normalize_email(email)
        detail = "Your account needs verification. We sent a new verification code."
        resend_otp_available = True
        headers: dict[str, str] | None = None

        try:
            await OTPService.generate_otp(
                db,
                RequestOTP(
                    email=normalized_email,
                    purpose=AuthPurpose.VERIFICATION.value,
                ),
                background_tasks=background_tasks,
            )
        except TooManyRequestsException as exc:
            resend_otp_available = False
            detail = (
                "Your account needs verification. A verification code was sent recently. "
                "Please use the latest code or wait before requesting another one."
            )
            headers = AuthService._otp_verification_headers(
                normalized_email,
                resend_otp_available=resend_otp_available,
            )
            headers["Retry-After"] = str(exc.retry_after)

        raise AccountNotVerifiedException(
            detail=detail,
            headers=headers
            or AuthService._otp_verification_headers(
                normalized_email,
                resend_otp_available=resend_otp_available,
            ),
            payload=AuthService._build_verification_required_payload(
                normalized_email,
                detail,
                resend_otp_available=resend_otp_available,
            ),
        )

    @staticmethod
    async def authenticate_actor(
        db: AsyncSession,
        payload: LoginRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> AuthenticatedActor:
        """Authenticate an actor without creating a session."""

        raw_identifier = payload.identifier.strip()
        identifier_type = _resolve_identifier_type(raw_identifier)
        normalized_identifier = (
            _normalize_email(raw_identifier)
            if identifier_type == IdentifierType.EMAIL
            else raw_identifier
        )

        if identifier_type == IdentifierType.EMAIL:
            superadmin = await _authenticate_superadmin(
                db,
                email=normalized_identifier,
                password=payload.password,
            )
            if superadmin is not None:
                return AuthenticatedActor(
                    actor_type=AuthSessionActorType.SUPERADMIN.value,
                    account_type=AuthSessionActorType.SUPERADMIN.value,
                    actor_id=superadmin.id,
                    email=superadmin.email,
                    role="superadmin",
                    user=LoginSessionUser(
                        id=str(superadmin.id),
                        email=superadmin.email,
                        actor_type=AuthSessionActorType.SUPERADMIN.value,
                        account_type=AuthSessionActorType.SUPERADMIN.value,
                        role="superadmin",
                    ),
                )

        tenant_actor = await _authenticate_tenant_actor(
            db,
            identifier=normalized_identifier,
            password=payload.password,
            identifier_type=identifier_type,
            background_tasks=background_tasks,
        )
        if tenant_actor is not None:
            return tenant_actor

        raise UnauthorizedException("Invalid email or password")

    @staticmethod
    async def reset_password(db: AsyncSession, payload: UpdatePassword) -> None:
        """Reset password using a verified password-reset token."""

        normalized_email = _normalize_email(payload.email)
        hashed_token = hash_auth_secret(payload.reset_token)
        now = datetime.now(timezone.utc)

        token_result = await db.execute(
            select(AuthRecord).where(
                func.lower(AuthRecord.email) == normalized_email,
                AuthRecord.purpose == AuthPurpose.PASSWORD_RESET,
                AuthRecord.hashed_value == hashed_token,
                AuthRecord.is_used == False,
            ).with_for_update()
        )
        reset_record = token_result.scalar_one_or_none()

        if reset_record is None:
            raise UnauthorizedException("Invalid or expired reset token")

        if _ensure_timezone_aware(reset_record.expires_at) < now:
            await db.delete(reset_record)
            await db.commit()
            raise UnauthorizedException("Invalid or expired reset token")

        actor, tenant, actor_type = await _get_email_actor_with_tenant(
            db,
            normalized_email,
            lock=True,
        )
        if not _email_actor_can_reset_password(actor, tenant):
            raise UnauthorizedException("Password reset is not available for this account")

        actor.password_hash = hash_password(payload.new_password)
        await AuthSessionRepository.revoke_all_sessions_for_actor(
            db,
            actor_type=AuthSessionService._to_session_actor_type(_enum_value(actor_type) or ""),
            actor_id=actor.id,
            revoked_at=now,
            reason="password_reset",
        )
        await db.delete(reset_record)
        await db.commit()


class TenantActivationService:
    """Business logic for tenant activation."""

    @staticmethod
    def _build_invite_link(
        raw_token: str,
        frontend_app_url: str | None = None,
    ) -> str:
        """Build invite link."""

        base_url = (frontend_app_url or settings.FRONTEND_APP_URL).strip().rstrip("/")
        return f"{base_url}/invite?token={quote(raw_token, safe='')}"

    @staticmethod
    async def create_activation_record(
        db: AsyncSession,
        *,
        tenant: Tenant,
        admin_user: TenantAdmin,
        frontend_app_url: str | None = None,
    ) -> str:
        """Create tenant activation record."""

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.TENANT_ACTIVATION_EXPIRATION_HOURS
        )

        await db.execute(
            delete(AuthRecord).where(
                func.lower(AuthRecord.email) == _normalize_email(admin_user.email),
                AuthRecord.purpose == AuthPurpose.TENANT_ACTIVATION,
            )
        )
        db.add(
            AuthRecord(
                email=admin_user.email,
                hashed_value=hash_auth_secret(raw_token),
                purpose=AuthPurpose.TENANT_ACTIVATION,
                expires_at=expires_at,
                tenant_id=tenant.id,
            )
        )
        await db.flush()

        return TenantActivationService._build_invite_link(
            raw_token,
            frontend_app_url=frontend_app_url,
        )

    @staticmethod
    async def send_activation_email(
        *,
        email: str,
        school_name: str,
        invite_link: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        """Send tenant activation email."""

        subject = f"Activate your {school_name} administrator account"
        html_body = get_tenant_invite_email_html(school_name, invite_link)

        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                to_email=email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
            return

        email_sent = await send_email(
            to_email=email,
            subject=subject,
            body=html_body,
            is_html=True,
        )
        if not email_sent:
            raise BadRequestException("Unable to send activation email. Please try again.")

    @staticmethod
    async def activate_tenant(
        db: AsyncSession,
        payload: TenantActivationRequest,
    ) -> dict[str, str]:
        """Activate a tenant admin account and tenant trial."""

        hashed_token = hash_auth_secret(payload.token)
        now = datetime.now(timezone.utc)

        record_result = await db.execute(
            select(AuthRecord).where(
                AuthRecord.hashed_value == hashed_token,
                AuthRecord.purpose == AuthPurpose.TENANT_ACTIVATION,
                AuthRecord.is_used == False,
            ).with_for_update()
        )
        activation_record = record_result.scalar_one_or_none()

        if activation_record is None:
            raise BadRequestException("Invalid or expired activation link.")

        if _ensure_timezone_aware(activation_record.expires_at) < now:
            await db.delete(activation_record)
            await db.commit()
            raise BadRequestException("Invalid or expired activation link.")

        normalized_email = _normalize_email(payload.email)
        if _normalize_email(activation_record.email) != normalized_email:
            await db.rollback()
            raise BadRequestException("Activation link does not match this email address.")

        admin = await TenantAdminRepository.get_by_email(
            db,
            _normalize_email(activation_record.email),
            lock=True,
        )
        tenant = await TenantRepository.get_by_id(
            db,
            activation_record.tenant_id,
            lock=True,
        )

        if admin is None or tenant is None or admin.tenant_id != tenant.id:
            await db.delete(activation_record)
            await db.commit()
            raise BadRequestException("Activation link is no longer valid.")

        if not _tenant_allows_activation_completion(tenant):
            await db.rollback()
            raise BadRequestException("Activation link is no longer valid.")

        admin.password_hash = hash_password(payload.password)
        admin.account_status = TenantAdminStatus.ACTIVE
        admin.is_verified = True
        admin.is_active = True

        tenant.verification_status = TenantVerificationStatus.ACTIVE
        if tenant.status == TenantStatus.INACTIVE:
            tenant.status = TenantStatus.TRIAL

        from app.modules.subscriptions.service import SubscriptionLifecycleService

        await SubscriptionLifecycleService.start_trial(
            db=db,
            tenant_id=tenant.id,
            notes="Trial started after activation link completion.",
        )
        await db.delete(activation_record)
        await db.commit()

        return {"detail": "Account activated successfully. You may now log in."}


class UserInviteService:
    """Business logic for tenant user and superadmin invites."""

    @staticmethod
    def _build_invite_link(
        raw_token: str,
        frontend_app_url: str | None = None,
    ) -> str:
        """Build invite link."""

        base_url = (frontend_app_url or settings.FRONTEND_APP_URL).strip().rstrip("/")
        return f"{base_url}/invite?token={quote(raw_token, safe='')}"

    @staticmethod
    async def create_invite_record(
        db: AsyncSession,
        *,
        email: str,
        tenant_id: uuid.UUID,
        frontend_app_url: str | None = None,
    ) -> str:
        """Create invite record."""

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.TENANT_ACTIVATION_EXPIRATION_HOURS
        )

        await db.execute(
            delete(AuthRecord).where(
                func.lower(AuthRecord.email) == _normalize_email(email),
                AuthRecord.purpose == AuthPurpose.USER_INVITE,
                AuthRecord.is_used == False,
            )
        )
        db.add(
            AuthRecord(
                email=_normalize_email(email),
                hashed_value=hash_auth_secret(raw_token),
                purpose=AuthPurpose.USER_INVITE,
                expires_at=expires_at,
                tenant_id=tenant_id,
            )
        )
        await db.flush()

        return UserInviteService._build_invite_link(
            raw_token,
            frontend_app_url=frontend_app_url,
        )

    @staticmethod
    async def send_invite_email(
        *,
        email: str,
        user_name: str,
        school_name: str,
        invite_link: str,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        """Send invite email."""

        subject = f"Set up your {school_name} account"
        html_body = get_user_invite_email_html(user_name, school_name, invite_link)

        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                to_email=email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
            return

        email_sent = await send_email(
            to_email=email,
            subject=subject,
            body=html_body,
            is_html=True,
        )
        if not email_sent:
            raise BadRequestException("Unable to send invite email. Please try again.")

    @staticmethod
    async def get_invite_status(
        db: AsyncSession,
        token: str,
    ) -> dict[str, str | None]:
        """Return invite status."""

        hashed_token = hash_auth_secret(token)
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(AuthRecord).where(
                AuthRecord.hashed_value == hashed_token,
                AuthRecord.purpose.in_(
                    (AuthPurpose.TENANT_ACTIVATION, AuthPurpose.USER_INVITE)
                ),
            ).order_by(AuthRecord.created_at.desc())
        )
        record = result.scalars().first()

        if record is None:
            superadmin_invite = await SuperAdminRepository.get_invite_status_record(
                db,
                hashed_token,
            )
            if superadmin_invite is None:
                return {"status": "invalid", "purpose": None}

            normalized_invite_email = _normalize_email(superadmin_invite.email)
            existing_user, existing_tenant, existing_superadmin = (
                await _get_platform_email_conflicts(db, normalized_invite_email)
            )

            if existing_superadmin is not None and existing_superadmin.is_active:
                return {"status": "used", "purpose": "superadmin_invite"}
            if existing_user is not None or existing_tenant is not None or existing_superadmin is not None:
                return {"status": "invalid", "purpose": "superadmin_invite"}
            if superadmin_invite.is_used:
                return {"status": "used", "purpose": "superadmin_invite"}
            if _ensure_timezone_aware(superadmin_invite.expires_at) < now:
                return {"status": "expired", "purpose": "superadmin_invite"}
            return {"status": "valid", "purpose": "superadmin_invite"}

        tenant = await TenantRepository.get_by_id(
            db,
            record.tenant_id,
        )

        if record.purpose == AuthPurpose.USER_INVITE:
            if not _tenant_allows_user_invite_completion(tenant):
                return {"status": "invalid", "purpose": None}
        if record.purpose == AuthPurpose.TENANT_ACTIVATION:
            if not _tenant_allows_activation_completion(tenant):
                return {"status": "invalid", "purpose": None}
        if record.is_used:
            return {"status": "used", "purpose": record.purpose.value}
        if _ensure_timezone_aware(record.expires_at) < now:
            return {"status": "expired", "purpose": record.purpose.value}
        return {"status": "valid", "purpose": record.purpose.value}

    @staticmethod
    async def accept_invite(
        db: AsyncSession,
        payload: UserInviteAcceptanceRequest,
    ) -> dict[str, str]:
        """Accept a teacher/parent invite, or delegate to superadmin invite."""

        hashed_token = hash_auth_secret(payload.token)
        now = datetime.now(timezone.utc)

        invite_result = await db.execute(
            select(AuthRecord).where(
                AuthRecord.hashed_value == hashed_token,
                AuthRecord.purpose == AuthPurpose.USER_INVITE,
            ).with_for_update()
        )
        invite_record = invite_result.scalar_one_or_none()

        if invite_record is None:
            return await UserInviteService.accept_superadmin_invite(db, payload)

        if invite_record.is_used:
            raise BadRequestException("This invite link has already been used. Please log in instead.")
        if _ensure_timezone_aware(invite_record.expires_at) < now:
            raise BadRequestException(
                "This invite link has expired. Please request a new invite from your school admin."
            )

        normalized_email = _normalize_email(payload.email)
        if _normalize_email(invite_record.email) != normalized_email:
            raise BadRequestException("Invite link does not match this email address.")

        actor, tenant, actor_type = await _get_email_actor_with_tenant(
            db,
            invite_record.email,
            lock=True,
        )
        normalized_actor_type = _enum_value(actor_type)

        if tenant.id != invite_record.tenant_id or not _tenant_allows_user_invite_completion(tenant):
            raise BadRequestException(
                "This invite link is invalid or has expired. Please request a new invite from your school admin."
            )

        if normalized_actor_type == ActorType.TENANT_ADMIN.value:
            raise BadRequestException("This invite link is not valid for administrator setup.")
        if normalized_actor_type == ActorType.STUDENT.value:
            raise BadRequestException("This invite link is not valid for student setup.")

        if isinstance(actor, Teacher) and actor.account_status != TeacherAccountStatus.PENDING:
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException("This invite link has already been used. Please log in instead.")

        if isinstance(actor, Parent) and actor.account_status != ParentAccountStatus.PENDING:
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException("This invite link has already been used. Please log in instead.")

        if actor.is_verified:
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException("This invite link has already been used. Please log in instead.")

        actor.password_hash = hash_password(payload.password)
        actor.is_verified = True
        actor.is_active = True
        actor.last_login_at = now

        if isinstance(actor, Teacher):
            actor.account_status = TeacherAccountStatus.ACTIVE
            actor_role = "teacher"
        elif isinstance(actor, Parent):
            actor.account_status = ParentAccountStatus.ACTIVE
            actor_role = "parent"
        else:
            raise BadRequestException("Unsupported invite actor type.")

        invite_record.is_used = True
        await db.execute(
            delete(AuthRecord).where(
                func.lower(AuthRecord.email) == _normalize_email(invite_record.email),
                AuthRecord.purpose == AuthPurpose.USER_INVITE,
                AuthRecord.id != invite_record.id,
                AuthRecord.is_used == False,
            )
        )
        await db.commit()

        return {
            "detail": "Account setup completed successfully. You may now log in.",
        }

    @staticmethod
    async def accept_superadmin_invite(
        db: AsyncSession,
        payload: UserInviteAcceptanceRequest,
    ) -> dict[str, str]:
        """Accept a superadmin invite."""

        hashed_token = hash_auth_secret(payload.token)
        now = datetime.now(timezone.utc)

        invite_record = await SuperAdminRepository.get_invite_by_hashed_token(
            db,
            hashed_token,
        )
        if invite_record is None:
            raise BadRequestException(
                "This invite link is invalid or has expired. Please request a new invite from the platform owner."
            )
        if invite_record.is_used:
            raise BadRequestException("This invite link has already been used. Please log in instead.")
        if _ensure_timezone_aware(invite_record.expires_at) < now:
            raise BadRequestException(
                "This invite link has expired. Please request a new invite from the platform owner."
            )

        normalized_email = _normalize_email(payload.email)
        if _normalize_email(invite_record.email) != normalized_email:
            raise BadRequestException("Invite link does not match this email address.")

        existing_user, existing_tenant, existing_superadmin = await _get_platform_email_conflicts(
            db,
            normalized_email,
        )
        if existing_user is not None or existing_tenant is not None:
            raise BadRequestException(
                "This invite can no longer be used because this email already belongs to another platform account."
            )
        if existing_superadmin is not None and existing_superadmin.is_active:
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException("This invite link has already been used. Please log in instead.")
        if existing_superadmin is not None:
            raise BadRequestException(
                "A superadmin account record already exists for this email. Ask another superadmin to reset or reactivate that account instead of accepting a new invite."
            )

        superadmin = SuperAdmin(
            email=normalized_email,
            password_hash=hash_password(payload.password),
            is_active=True,
        )
        await SuperAdminRepository.create(db, superadmin)
        invite_record.is_used = True
        await SuperAdminRepository.delete_active_invites_for_email(db, normalized_email)
        await db.commit()
        return {"detail": "Account setup completed successfully. You may now log in."}


class OTPService:
    """Business logic for OTP verification and password reset."""

    @staticmethod
    async def _get_verification_target(
        db: AsyncSession,
        email: str,
        *,
        lock: bool = False,
    ) -> tuple[TenantAdmin, Tenant]:
        """Resolve a verification email to its tenant admin and tenant."""

        normalized_email = _normalize_email(email)
        try:
            resolution = await AuthIdentityService.resolve_identifier(
                db=db,
                identifier=normalized_email,
                identifier_type=IdentifierType.EMAIL,
            )
        except NotFoundException as exc:
            raise NotFoundException("Tenant admin with this email not found.") from exc

        if resolution.actor_type != ActorType.TENANT_ADMIN:
            raise BadRequestException(
                "OTP verification is only available for tenant admin signup accounts."
            )

        admin = await TenantAdminRepository.get_by_id(
            db,
            admin_id=resolution.actor_id,
            lock=lock,
        )
        if admin is None:
            raise NotFoundException("Tenant admin not found.")

        tenant = await TenantRepository.get_by_id(
            db,
            resolution.tenant_id,
            lock=lock,
        )
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        if admin.tenant_id != tenant.id:
            raise BadRequestException("OTP verification is not available for this account.")

        return admin, tenant

    @staticmethod
    def _ensure_verification_target_allowed(
        admin: TenantAdmin,
        tenant: Tenant,
    ) -> None:
        """Validate whether a tenant admin can complete OTP verification."""

        if admin.account_status != TenantAdminStatus.PENDING or admin.is_verified:
            raise BadRequestException("OTP verification is not available for this account.")
        if tenant.verification_status == TenantVerificationStatus.REJECTED:
            raise BadRequestException("Tenant verification has been rejected.")
        if not _tenant_allows_otp_verification(tenant):
            raise BadRequestException("OTP verification is not available for this account.")

    @staticmethod
    async def _replace_otp_record(
        db: AsyncSession,
        payload: RequestOTP,
        otp_code: str,
        expires_at: datetime,
    ) -> None:
        """Replace existing OTP records for the target/purpose."""

        normalized_email = _normalize_email(payload.email)
        purpose = _enum_value(payload.purpose)

        if purpose == AuthPurpose.VERIFICATION.value:
            admin, _tenant = await OTPService._get_verification_target(
                db,
                normalized_email,
                lock=True,
            )
            record_email = admin.email
            tenant_id = admin.tenant_id
        elif purpose == AuthPurpose.PASSWORD_RESET.value:
            actor, _tenant, _actor_type = await _get_email_actor_with_tenant(
                db,
                normalized_email,
                lock=True,
            )
            record_email = actor.email
            tenant_id = actor.tenant_id
        else:
            raise BadRequestException(f"Unhandled OTP purpose: {payload.purpose}")

        await db.execute(
            delete(AuthRecord).where(
                func.lower(AuthRecord.email) == normalized_email,
                AuthRecord.purpose == payload.purpose,
            )
        )
        db.add(
            AuthRecord(
                email=record_email,
                hashed_value=hash_otp(otp_code),
                purpose=payload.purpose,
                expires_at=expires_at,
                tenant_id=tenant_id,
            )
        )
        await db.flush()

    @staticmethod
    async def generate_otp(
        db: AsyncSession,
        payload: RequestOTP,
        background_tasks: BackgroundTasks | None = None,
        *,
        commit: bool = True,
    ) -> None:
        """Generate and send an OTP."""

        normalized_email = _normalize_email(payload.email)
        purpose = _enum_value(payload.purpose)

        if purpose == AuthPurpose.VERIFICATION.value:
            admin, tenant = await OTPService._get_verification_target(db, normalized_email)
            OTPService._ensure_verification_target_allowed(admin, tenant)
        elif purpose == AuthPurpose.PASSWORD_RESET.value:
            actor, tenant, _actor_type = await _get_email_actor_with_tenant(db, normalized_email)
            if not _email_actor_can_reset_password(actor, tenant):
                raise BadRequestException("Password reset is not available for this account.")
        else:
            raise BadRequestException(f"Unhandled OTP purpose: {payload.purpose}")

        rate_limiter = OTPRateLimiter()
        allowed, retry_after = rate_limiter.is_allowed(normalized_email, payload.purpose)
        if not allowed:
            raise TooManyRequestsException(
                detail="Too many OTP requests. Please wait before trying again.",
                retry_after=retry_after,
            )

        otp_code = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.OTP_EXPIRATION_MINUTES
        )
        await OTPService._replace_otp_record(db, payload, otp_code, expires_at)
        if commit:
            await db.commit()

        subject = "Your Verification Code"
        purpose_str = "verification"
        if purpose == AuthPurpose.PASSWORD_RESET.value:
            subject = "Password Reset Code"
            purpose_str = "password reset"

        html_body = get_otp_email_html(
            code=otp_code,
            purpose=purpose_str,
            expiration_minutes=settings.OTP_EXPIRATION_MINUTES,
        )

        if background_tasks is not None:
            background_tasks.add_task(
                send_email,
                to_email=payload.email,
                subject=subject,
                body=html_body,
                is_html=True,
            )
            return

        email_sent = await send_email(
            to_email=payload.email,
            subject=subject,
            body=html_body,
            is_html=True,
        )
        if not email_sent:
            raise BadRequestException("Unable to send OTP email. Please try again.")

    @staticmethod
    async def verify_otp(db: AsyncSession, payload: VerifyOTP) -> dict[str, str]:
        """Verify an OTP and return the next-step payload."""

        now = datetime.now(timezone.utc)
        normalized_email = _normalize_email(payload.email)
        purpose = _enum_value(payload.purpose)

        result = await db.execute(
            select(AuthRecord).where(
                func.lower(AuthRecord.email) == normalized_email,
                AuthRecord.purpose == payload.purpose,
                AuthRecord.is_used == False,
            ).order_by(AuthRecord.created_at.desc()).with_for_update()
        )
        otp_record = result.scalars().first()

        if not otp_record or not verify_otp_hash(payload.code, otp_record.hashed_value):
            raise BadRequestException("Invalid OTP")
        if _ensure_timezone_aware(otp_record.expires_at) < now:
            raise BadRequestException("OTP has expired")

        response_data = {"detail": "OTP verified successfully"}

        if purpose == AuthPurpose.VERIFICATION.value:
            admin, tenant = await OTPService._get_verification_target(
                db,
                normalized_email,
                lock=True,
            )
            OTPService._ensure_verification_target_allowed(admin, tenant)

            admin.account_status = TenantAdminStatus.ACTIVE
            admin.is_verified = True
            tenant.verification_status = TenantVerificationStatus.ACTIVE
            if tenant.status == TenantStatus.INACTIVE:
                tenant.status = TenantStatus.TRIAL

            from app.modules.subscriptions.service import SubscriptionLifecycleService

            await SubscriptionLifecycleService.start_trial(
                db=db,
                tenant_id=tenant.id,
                notes="Trial started after OTP verification.",
            )
            otp_record.is_used = True

        elif purpose == AuthPurpose.PASSWORD_RESET.value:
            actor, tenant, _actor_type = await _get_email_actor_with_tenant(
                db,
                payload.email,
                lock=True,
            )
            if not _email_actor_can_reset_password(actor, tenant):
                raise BadRequestException("Password reset is not available for this account.")

            reset_token = secrets.token_urlsafe(32)
            reset_token_expires_at = now + timedelta(minutes=15)
            await db.execute(
                delete(AuthRecord).where(
                    func.lower(AuthRecord.email) == _normalize_email(actor.email),
                    AuthRecord.purpose == AuthPurpose.PASSWORD_RESET,
                )
            )
            db.add(
                AuthRecord(
                    email=actor.email,
                    hashed_value=hash_auth_secret(reset_token),
                    purpose=AuthPurpose.PASSWORD_RESET,
                    expires_at=reset_token_expires_at,
                    tenant_id=actor.tenant_id,
                )
            )
            response_data["reset_token"] = reset_token
        else:
            raise BadRequestException(f"Unhandled OTP purpose: {payload.purpose}")

        await db.commit()
        return response_data
