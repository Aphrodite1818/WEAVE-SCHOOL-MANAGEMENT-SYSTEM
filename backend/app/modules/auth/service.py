#======================================#
#            auth/service.py           #
#======================================#

import uuid
import random
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import (
    create_access_token,
    hash_auth_secret,
    hash_otp,
    hash_password,
    verify_otp as verify_otp_hash,
    verify_password,
)
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
from app.config.settings import settings
from app.modules.auth.models import AuthPurpose, AuthRecord
from app.modules.auth.schemas import (
    LoginSessionUser,
    LoginRequest,
    RequestOTP,
    TenantActivationRequest,
    UserInviteAcceptanceRequest,
    UpdatePassword,
    VerifyOTP,
)
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.parents.repository import ParentRepository
from app.modules.students.models import Student, StudentAccountStatus
from app.modules.students.repository import StudentRepository
from app.modules.superadmin.models import SuperAdmin
from app.modules.superadmin.repository import SuperAdminRepository
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.models import Tenant, TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository
from app.core.utils.otp_rate_limiter import OTPRateLimiter

EmailActor = TenantAdmin | Teacher | Parent


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


async def _get_platform_email_conflicts(
    db: AsyncSession,
    email: str,
) -> tuple[object | None, Tenant | None, SuperAdmin | None]:
    """Internal helper for get platform email conflicts."""
    normalized_email = _normalize_email(email)
    existing_user = await TenantAdminRepository.get_by_email(db, normalized_email)
    if existing_user is None:
        existing_user = await TeacherRepository.get_by_email(db, normalized_email)
    if existing_user is None:
        existing_user = await ParentRepository.get_by_email(db, normalized_email)
    existing_tenant = await TenantRepository.get_by_email_including_deleted(db, normalized_email)
    existing_superadmin = await SuperAdminRepository.get_by_email(db, normalized_email)
    return existing_user, existing_tenant, existing_superadmin


async def _authenticate_superadmin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
) -> SuperAdmin | None:
    """Internal helper for authenticate superadmin."""
    superadmin = await SuperAdminRepository.get_by_email(db, email)
    if superadmin is None:
        return None
    if not verify_password(password, superadmin.password_hash):
        raise UnauthorizedException("Invalid email or password")
    if not superadmin.is_active:
        raise UnauthorizedException("Superadmin account is not active")

    superadmin.last_login_at = datetime.now(timezone.utc)
    await SuperAdminRepository.save(db, superadmin)
    await db.commit()
    return superadmin


async def _authenticate_tenant_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    background_tasks: BackgroundTasks | None = None,
) -> TenantAdmin | None:
    """Authenticate a tenant admin through AuthIdentity."""

    normalized_email = _normalize_email(email)

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

    admin.last_login_at = datetime.now(timezone.utc)
    await TenantAdminRepository.save(db, admin)
    await db.commit()

    return admin


def _tenant_allows_login(tenant: Tenant | None) -> bool:
    """Internal helper for tenant allows login."""
    return (
        tenant is not None
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.ACTIVE
        and tenant.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)
    )


def _tenant_allows_user_invite_completion(tenant: Tenant | None) -> bool:
    """Internal helper for tenant allows user invite completion."""
    return _tenant_allows_login(tenant)


def _tenant_allows_activation_completion(tenant: Tenant | None) -> bool:
    """Internal helper for tenant allows activation completion."""
    return (
        tenant is not None
        and not tenant.is_deleted
        and tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION
        and tenant.status == TenantStatus.INACTIVE
    )


def _tenant_allows_otp_verification(tenant: Tenant | None) -> bool:
    """Internal helper for tenant allows otp verification."""
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
        teacher.last_login_at = datetime.now(timezone.utc)
        await TeacherRepository.save(db, teacher)
        await db.commit()
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
        parent.last_login_at = datetime.now(timezone.utc)
        await ParentRepository.save(db, parent)
        await db.commit()
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
        if student is None or student.password_hash is None:
            raise UnauthorizedException("Account not found")
        if not verify_password(password, student.password_hash):
            raise UnauthorizedException("Invalid credentials")
        if (
            not student.is_active
            or not student.is_verified
            or student.account_status != StudentAccountStatus.ACTIVE
        ):
            raise UnauthorizedException("Account is not active")
        student.last_login_at = datetime.now(timezone.utc)
        await StudentRepository.save(db, student)
        await db.commit()
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

    actor_query = None
    if resolution.actor_type == ActorType.TENANT_ADMIN:
        actor_query = select(TenantAdmin).where(TenantAdmin.id == resolution.actor_id)
    elif resolution.actor_type == ActorType.TEACHER:
        actor_query = select(Teacher).where(Teacher.id == resolution.actor_id)
    elif resolution.actor_type == ActorType.PARENT:
        actor_query = select(Parent).where(Parent.id == resolution.actor_id)
    else:
        raise BadRequestException(
            "This email address is not eligible for this authentication flow."
        )

    tenant_query = select(Tenant).where(Tenant.id == resolution.tenant_id)

    if lock:
        actor_query = actor_query.with_for_update()
        tenant_query = tenant_query.with_for_update()

    actor_result = await db.execute(actor_query)
    actor = actor_result.scalar_one_or_none()
    if actor is None:
        raise NotFoundException("Account not found.")

    tenant_result = await db.execute(tenant_query)
    tenant = tenant_result.scalar_one_or_none()
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
    """Represent the AuthenticatedActor type."""
    actor_type: str
    account_type: str
    actor_id: uuid.UUID
    email: str
    role: str | None = None
    tenant_id: uuid.UUID | None = None
    password_reset_required: bool | None = None
    user: LoginSessionUser | None = None


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
        """Internal helper for otp verification headers."""
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
        """Internal helper for raise verification required."""
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
        """Perform authenticate actor."""
        normalized_identifier = payload.identifier.strip()

        superadmin = await _authenticate_superadmin(
            db,
            email=normalized_identifier,
            password=payload.password,
        )
        if superadmin is not None:
            return AuthenticatedActor(
                actor_type="superadmin",
                account_type="superadmin",
                actor_id=superadmin.id,
                email=superadmin.email,
                role="superadmin",
                user=LoginSessionUser(
                    id=str(superadmin.id),
                    email=superadmin.email,
                    actor_type="superadmin",
                    account_type="superadmin",
                    role="superadmin",
                ),
            )

        identifier_type = _resolve_identifier_type(normalized_identifier)
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
        """Perform reset password."""
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

        if reset_record.expires_at.replace(tzinfo=timezone.utc) < now:
            await db.delete(reset_record)
            await db.commit()
            raise UnauthorizedException("Invalid or expired reset token")

        actor, tenant, _actor_type = await _get_email_actor_with_tenant(
            db,
            normalized_email,
            lock=True,
        )
        if not _email_actor_can_reset_password(actor, tenant):
            raise UnauthorizedException("Password reset is not available for this account")

        hashed_pw = hash_password(payload.new_password)

        actor.password_hash = hashed_pw
        await db.delete(reset_record)
        await db.commit()


class TenantActivationService:
    """Business logic for the auth domain."""

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
        """Create activation record."""
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
        """Perform send activation email."""
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
            raise BadRequestException(
                "Unable to send activation email. Please try again."
            )

    @staticmethod
    async def activate_tenant(
        db: AsyncSession,
        payload: TenantActivationRequest,
    ) -> dict[str, str]:
        """Perform activate tenant."""
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

        if activation_record.expires_at.replace(tzinfo=timezone.utc) < now:
            await db.delete(activation_record)
            await db.commit()
            raise BadRequestException("Invalid or expired activation link.")

        normalized_email = payload.email.strip().lower()
        if activation_record.email.strip().lower() != normalized_email:
            await db.rollback()
            raise BadRequestException(
                "Activation link does not match this email address."
            )

        admin_result = await db.execute(
            select(TenantAdmin).where(
                func.lower(TenantAdmin.email) == _normalize_email(activation_record.email)
            ).with_for_update()
        )
        admin = admin_result.scalar_one_or_none()

        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == activation_record.tenant_id).with_for_update()
        )
        tenant = tenant_result.scalar_one_or_none()

        if admin is None or tenant is None:
            await db.delete(activation_record)
            await db.commit()
            raise BadRequestException("Activation link is no longer valid.")

        if admin.tenant_id != tenant.id:
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

        await db.delete(activation_record)
        await db.commit()

        return {"detail": "Account activated successfully. You may now log in."}


class UserInviteService:
    """Business logic for the auth domain."""

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
        """Perform send invite email."""
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
            raise BadRequestException(
                "Unable to send invite email. Please try again."
            )

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
            existing_user, existing_tenant, existing_superadmin = await _get_platform_email_conflicts(
                db,
                normalized_invite_email,
            )

            if existing_superadmin is not None and existing_superadmin.is_active:
                return {"status": "used", "purpose": "superadmin_invite"}

            if existing_user is not None or existing_tenant is not None or existing_superadmin is not None:
                return {"status": "invalid", "purpose": "superadmin_invite"}

            if superadmin_invite.is_used:
                return {"status": "used", "purpose": "superadmin_invite"}

            if superadmin_invite.expires_at.replace(tzinfo=timezone.utc) < now:
                return {"status": "expired", "purpose": "superadmin_invite"}

            return {"status": "valid", "purpose": "superadmin_invite"}

        tenant_result = await db.execute(select(Tenant).where(Tenant.id == record.tenant_id))
        tenant = tenant_result.scalar_one_or_none()

        if record.purpose == AuthPurpose.USER_INVITE:
            if not _tenant_allows_user_invite_completion(tenant):
                return {"status": "invalid", "purpose": None}

        if record.purpose == AuthPurpose.TENANT_ACTIVATION and not _tenant_allows_activation_completion(tenant):
            return {"status": "invalid", "purpose": None}

        if record.is_used:
            return {"status": "used", "purpose": record.purpose.value}

        if record.expires_at.replace(tzinfo=timezone.utc) < now:
            return {"status": "expired", "purpose": record.purpose.value}

        return {"status": "valid", "purpose": record.purpose.value}

    @staticmethod
    async def accept_invite(
        db: AsyncSession,
        payload: UserInviteAcceptanceRequest,
    ) -> dict[str, str]:
        """Perform accept invite."""
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
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )

        if invite_record.expires_at.replace(tzinfo=timezone.utc) < now:
            raise BadRequestException(
                "This invite link has expired. Please request a new invite from your school admin."
            )

        normalized_email = payload.email.strip().lower()
        if invite_record.email.strip().lower() != normalized_email:
            raise BadRequestException(
                "Invite link does not match this email address."
            )

        actor, tenant, actor_type = await _get_email_actor_with_tenant(
            db,
            invite_record.email,
            lock=True,
        )
        normalized_actor_type = _enum_value(actor_type)

        if tenant.id != invite_record.tenant_id:
            raise BadRequestException(
                "This invite link is invalid or has expired. Please request a new invite from your school admin."
            )

        if not _tenant_allows_user_invite_completion(tenant):
            raise BadRequestException(
                "This invite link is invalid or has expired. Please request a new invite from your school admin."
            )

        if normalized_actor_type == ActorType.TENANT_ADMIN.value:
            raise BadRequestException("This invite link is not valid for administrator setup.")

        if normalized_actor_type == ActorType.STUDENT.value:
            raise BadRequestException("This invite link is not valid for student setup.")

        if actor.account_status != TeacherAccountStatus.PENDING and isinstance(actor, Teacher):
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )

        if actor.account_status != ParentAccountStatus.PENDING and isinstance(actor, Parent):
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )

        if actor.is_verified:
            invite_record.is_used = True
            await db.commit()
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )

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
        access_token = create_access_token(
            data={
                "sub": str(actor.id),
                "email": actor.email,
                "actor_type": normalized_actor_type,
                "role": actor_role,
                "account_type": normalized_actor_type,
                "tenant_id": str(actor.tenant_id),
            }
        )

        return {
            "detail": "Account setup completed successfully.",
            "access_token": access_token,
            "token_type": "bearer",
            "actor_type": normalized_actor_type,
            "role": actor_role,
            "account_type": normalized_actor_type,
        }

    @staticmethod
    async def accept_superadmin_invite(
        db: AsyncSession,
        payload: UserInviteAcceptanceRequest,
    ) -> dict[str, str]:
        """Perform accept superadmin invite."""
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
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )
        if invite_record.expires_at.replace(tzinfo=timezone.utc) < now:
            raise BadRequestException(
                "This invite link has expired. Please request a new invite from the platform owner."
            )

        normalized_email = _normalize_email(payload.email)
        if invite_record.email.strip().lower() != normalized_email:
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
            raise BadRequestException(
                "This invite link has already been used. Please log in instead."
            )

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
    """Business logic for the auth domain."""

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

        admin_query = select(TenantAdmin).where(TenantAdmin.id == resolution.actor_id)
        tenant_query = select(Tenant).where(Tenant.id == resolution.tenant_id)

        if lock:
            admin_query = admin_query.with_for_update()
            tenant_query = tenant_query.with_for_update()

        admin_result = await db.execute(admin_query)
        admin = admin_result.scalar_one_or_none()
        if admin is None:
            raise NotFoundException("Tenant admin not found.")

        tenant_result = await db.execute(tenant_query)
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        if admin.tenant_id != tenant.id:
            raise BadRequestException(
                "OTP verification is not available for this account."
            )

        return admin, tenant

    @staticmethod
    def _ensure_verification_target_allowed(
        admin: TenantAdmin,
        tenant: Tenant,
    ) -> None:
        """Validate whether a tenant admin can complete OTP verification."""

        if admin.account_status != TenantAdminStatus.PENDING or admin.is_verified:
            raise BadRequestException(
                "OTP verification is not available for this account."
            )

        if tenant.verification_status == TenantVerificationStatus.REJECTED:
            raise BadRequestException("Tenant verification has been rejected.")

        if not _tenant_allows_otp_verification(tenant):
            raise BadRequestException(
                "OTP verification is not available for this account."
            )

    @staticmethod
    async def _replace_otp_record(
        db: AsyncSession,
        payload: RequestOTP,
        otp_code: str,
        expires_at: datetime,
    ) -> None:
        """Internal helper for replace otp record."""
        normalized_email = _normalize_email(payload.email)

        if payload.purpose == AuthPurpose.VERIFICATION:
            admin, _tenant = await OTPService._get_verification_target(
                db,
                normalized_email,
                lock=True,
            )
            record_email = admin.email
            tenant_id = admin.tenant_id
        elif payload.purpose == AuthPurpose.PASSWORD_RESET:
            actor, _tenant, _actor_type = await _get_email_actor_with_tenant(
                db,
                normalized_email,
                lock=True,
            )
            record_email = actor.email
            tenant_id = actor.tenant_id
        else:
            raise BadRequestException(f"Unhandled OTP purpose : {payload.purpose}")

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
        """Perform generate otp."""
        normalized_email = _normalize_email(payload.email)

        if payload.purpose == AuthPurpose.VERIFICATION:
            admin, tenant = await OTPService._get_verification_target(
                db,
                normalized_email,
            )
            OTPService._ensure_verification_target_allowed(admin, tenant)
        elif payload.purpose == AuthPurpose.PASSWORD_RESET:
            actor, tenant, _actor_type = await _get_email_actor_with_tenant(
                db,
                normalized_email,
            )

            if not _email_actor_can_reset_password(actor, tenant):
                raise BadRequestException(
                    "Password reset is not available for this account."
                )
        else:
            raise BadRequestException(f"Unhandled OTP purpose : {payload.purpose}")

        rate_limiter = OTPRateLimiter()
        allowed, retry_after = rate_limiter.is_allowed(
            normalized_email,
            payload.purpose,
        )

        if not allowed:
            raise TooManyRequestsException(
                detail="Too many OTP requests. Please wait before trying again.",
                retry_after=retry_after,
            )

        otp_code = ''.join(random.choices(string.digits, k=6))
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRATION_MINUTES)

        await OTPService._replace_otp_record(db, payload, otp_code, expires_at)
        if commit:
            await db.commit()

        subject = "Your Verification Code"
        purpose_str = "verification"
        if payload.purpose == AuthPurpose.PASSWORD_RESET:
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
        """Perform verify otp."""
        now = datetime.now(timezone.utc)
        normalized_email = _normalize_email(payload.email)

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

        if otp_record.expires_at.replace(tzinfo=timezone.utc) < now:
            raise BadRequestException("OTP has expired")

        response_data = {"detail": "OTP verified successfully"}

        if payload.purpose == AuthPurpose.VERIFICATION:
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
            otp_record.is_used = True

        elif payload.purpose == AuthPurpose.PASSWORD_RESET:
            actor, tenant, _actor_type = await _get_email_actor_with_tenant(
                db,
                payload.email,
                lock=True,
            )

            if not _email_actor_can_reset_password(actor, tenant):
                raise BadRequestException("Password reset is not available for this account.")

            reset_token = secrets.token_urlsafe(32)
            reset_token_expires_at = now + timedelta(minutes=15)

            # Replace any previous reset token so only the latest one remains valid.
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
            raise BadRequestException(f"Unhandled OTP purpose : {payload.purpose}")

        await db.commit()

        return response_data
