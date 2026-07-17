"""Robust global teacher-account registration workflow."""

from __future__ import annotations

from enum import StrEnum

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_password
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    TooManyRequestsException,
)
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth.models import AuthPurpose
from app.modules.auth.schemas import RequestOTP
from app.modules.auth.service import OTPService
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.repository import AuthIdentityRepository
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.parents.repository import ParentAccountRepository
from app.modules.teachers.models import TeacherAccount, TeacherAccountStatus
from app.modules.teachers.repository import TeacherAccountRepository
from app.modules.teachers.schemas import TeacherAccountRegisterRequest
from app.modules.tenant_admins.repository import TenantAdminRepository


logger = get_logger(__name__)


class TeacherRegistrationState(StrEnum):
    """Registration state derived from the global teacher account."""

    AVAILABLE = "AVAILABLE"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class TeacherRegistrationService:
    """Create or update pending teacher accounts without corrupting identities."""

    @staticmethod
    def _registration_state(
        account: TeacherAccount | None,
    ) -> TeacherRegistrationState:
        if account is None:
            return TeacherRegistrationState.AVAILABLE
        if account.is_verified:
            return TeacherRegistrationState.ACTIVE
        if (
            account.is_active
            and account.account_status == TeacherAccountStatus.PENDING
        ):
            return TeacherRegistrationState.PENDING
        return TeacherRegistrationState.BLOCKED

    @staticmethod
    async def _ensure_no_unindexed_cross_account_owner(
        db: AsyncSession,
        *,
        normalized_email: str,
    ) -> None:
        """Catch legacy account rows whose AuthIdentity record is missing."""

        tenant_admin = await TenantAdminRepository.get_by_email(
            db,
            normalized_email,
            lock=True,
        )
        if tenant_admin is not None:
            raise ConflictException(
                "This email is already registered to another account."
            )

        parent_account = await ParentAccountRepository.get_by_email(
            db,
            normalized_email,
            lock=True,
        )
        if parent_account is not None:
            raise ConflictException(
                "This email is already registered to another account."
            )

    @staticmethod
    async def _ensure_teacher_identity(
        db: AsyncSession,
        *,
        account: TeacherAccount,
        normalized_email: str,
    ) -> None:
        """Create or repair the canonical global teacher email identity."""

        identity = await AuthIdentityRepository.get_by_identifier(
            db,
            normalized_email,
            IdentifierType.EMAIL,
        )
        canonical_actor_identity = await AuthIdentityRepository.get_by_actor(
            db,
            ActorType.TEACHER_ACCOUNT,
            account.id,
        )

        if identity is None:
            if canonical_actor_identity is not None:
                if (
                    canonical_actor_identity.identifier != normalized_email
                    or canonical_actor_identity.identifier_type
                    != IdentifierType.EMAIL
                    or canonical_actor_identity.tenant_id is not None
                ):
                    raise ConflictException(
                        "This teacher account already has a different login identity."
                    )
                if not canonical_actor_identity.is_active:
                    canonical_actor_identity.is_active = True
                    await AuthIdentityRepository.save(
                        db,
                        canonical_actor_identity,
                    )
                    AuthIdentityService._queue_cache_invalidation(
                        db,
                        AuthIdentityService._identifier_cache_key(
                            identifier=normalized_email,
                            identifier_type=IdentifierType.EMAIL,
                        ),
                    )
                return

            await AuthIdentityService.create_for_actor(
                db,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.TEACHER_ACCOUNT,
                    actor_id=account.id,
                    is_active=True,
                ),
            )
            return

        if (
            identity.actor_type
            not in {ActorType.TEACHER_ACCOUNT, ActorType.TEACHER}
            or identity.actor_id != account.id
        ):
            raise ConflictException(
                "This email is already registered to another account."
            )

        if (
            canonical_actor_identity is not None
            and canonical_actor_identity.id != identity.id
        ):
            raise ConflictException(
                "The teacher account has conflicting login identities."
            )

        changed = (
            identity.actor_type != ActorType.TEACHER_ACCOUNT
            or identity.tenant_id is not None
            or not identity.is_active
        )
        if changed:
            identity.actor_type = ActorType.TEACHER_ACCOUNT
            identity.tenant_id = None
            identity.is_active = True
            await AuthIdentityRepository.save(db, identity)
            AuthIdentityService._queue_cache_invalidation(
                db,
                AuthIdentityService._identifier_cache_key(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                ),
            )

    @staticmethod
    async def _apply_registration(
        db: AsyncSession,
        *,
        normalized_email: str,
        password: str,
    ) -> tuple[TeacherAccount, bool]:
        """Apply one registration attempt inside an atomic transaction."""

        async with db.begin():
            await AccountEmailGuard.ensure_not_superadmin_email(
                db=db,
                email=normalized_email,
                message="This email cannot be used for teacher registration.",
            )

            account = await TeacherAccountRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )
            identity = await AuthIdentityRepository.get_by_identifier(
                db,
                normalized_email,
                IdentifierType.EMAIL,
            )

            if account is None:
                if identity is not None:
                    raise ConflictException(
                        "This email is already registered to another account."
                    )
                await (
                    TeacherRegistrationService
                    ._ensure_no_unindexed_cross_account_owner(
                        db,
                        normalized_email=normalized_email,
                    )
                )
                account = await TeacherAccountRepository.add(
                    db,
                    TeacherAccount(
                        email=normalized_email,
                        password_hash=hash_password(password),
                        account_status=TeacherAccountStatus.PENDING,
                        is_verified=False,
                        is_active=True,
                    ),
                )
                await TeacherRegistrationService._ensure_teacher_identity(
                    db,
                    account=account,
                    normalized_email=normalized_email,
                )
                return account, True

            state = TeacherRegistrationService._registration_state(account)
            if state == TeacherRegistrationState.ACTIVE:
                raise ConflictException(
                    "This teacher account already exists. Please log in."
                )
            if state == TeacherRegistrationState.BLOCKED:
                raise ForbiddenException(
                    "This teacher account cannot be registered again. "
                    "Please contact support."
                )

            if identity is not None and (
                identity.actor_type
                not in {ActorType.TEACHER_ACCOUNT, ActorType.TEACHER}
                or identity.actor_id != account.id
            ):
                raise ConflictException(
                    "This email is already registered to another account."
                )

            account.password_hash = hash_password(password)
            account.account_status = TeacherAccountStatus.PENDING
            account.is_verified = False
            account.is_active = True
            await TeacherAccountRepository.save(db, account)
            await TeacherRegistrationService._ensure_teacher_identity(
                db,
                account=account,
                normalized_email=normalized_email,
            )
            return account, False

    @staticmethod
    async def _recover_concurrent_registration(
        db: AsyncSession,
        *,
        normalized_email: str,
        password: str,
    ) -> TeacherAccount:
        """Recover the account that won a concurrent registration race."""

        async with db.begin():
            account = await TeacherAccountRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )
            state = TeacherRegistrationService._registration_state(account)
            if account is None:
                raise ConflictException(
                    "Teacher registration could not be recovered. Please try again."
                )
            if state == TeacherRegistrationState.ACTIVE:
                raise ConflictException(
                    "This teacher account already exists. Please log in."
                )
            if state == TeacherRegistrationState.BLOCKED:
                raise ForbiddenException(
                    "This teacher account cannot be registered again. "
                    "Please contact support."
                )

            account.password_hash = hash_password(password)
            account.account_status = TeacherAccountStatus.PENDING
            account.is_verified = False
            account.is_active = True
            await TeacherAccountRepository.save(db, account)
            await TeacherRegistrationService._ensure_teacher_identity(
                db,
                account=account,
                normalized_email=normalized_email,
            )
            return account

    @staticmethod
    async def register_account(
        db: AsyncSession,
        payload: TeacherAccountRegisterRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, object]:
        """Register a global teacher account or update a pending registration."""

        normalized_email = str(payload.email).strip().casefold()
        created = False

        try:
            account, created = (
                await TeacherRegistrationService._apply_registration(
                    db,
                    normalized_email=normalized_email,
                    password=payload.password,
                )
            )
        except IntegrityError:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)
            account = (
                await TeacherRegistrationService
                ._recover_concurrent_registration(
                    db,
                    normalized_email=normalized_email,
                    password=payload.password,
                )
            )
            created = False
            logger.info(
                "Recovered concurrent teacher registration",
                extra={
                    "teacher_account_id": str(account.id),
                    "email": normalized_email,
                },
            )

        await AuthIdentityService.invalidate_after_commit(db)

        resend_otp_available = True
        message = (
            "Registration successful. Check your email for the verification code."
            if created
            else (
                "Your pending teacher registration was updated. "
                "We sent you a new verification code."
            )
        )

        try:
            await OTPService.generate_otp(
                db,
                RequestOTP(
                    email=normalized_email,
                    purpose=AuthPurpose.VERIFICATION.value,
                ),
                background_tasks=background_tasks,
            )
        except TooManyRequestsException:
            resend_otp_available = False
            message = (
                "Your teacher registration is pending verification. "
                "A verification code was sent recently. Use the latest code "
                "or wait before requesting another one."
            )

        logger.info(
            "Teacher registration completed",
            extra={
                "teacher_account_id": str(account.id),
                "email": normalized_email,
                "created": created,
                "resend_otp_available": resend_otp_available,
            },
        )
        return {
            "created": created,
            "email": normalized_email,
            "verification_required": True,
            "purpose": AuthPurpose.VERIFICATION.value,
            "redirect_to": "/verify-otp",
            "resend_otp_available": resend_otp_available,
            "detail": message,
            "message": message,
        }
