"""Service layer for global teacher account registration."""

from __future__ import annotations

from enum import Enum as PyEnum
from typing import Any, Literal

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_password
from app.core.exceptions import ConflictException, TooManyRequestsException
from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth.models import AuthPurpose
from app.modules.auth.schemas import RequestOTP
from app.modules.auth.service import OTPService
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.teachers.models import TeacherAccount, TeacherAccountStatus
from app.modules.teachers.repository import TeacherAccountRepository
from app.modules.teachers.schemas import TeacherAccountRegisterRequest


logger = get_logger(__name__)


class TeacherRegistrationState(str, PyEnum):
    """Possible registration states for a global teacher account."""

    AVAILABLE = "AVAILABLE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    INACTIVE = "INACTIVE"


class TeacherAccountService:
    """Business logic for global teacher accounts."""

    @staticmethod
    def get_registration_state(
        account: TeacherAccount | None,
    ) -> (
        Literal[TeacherRegistrationState.AVAILABLE]
        | Literal[TeacherRegistrationState.LOCKED]
        | Literal[TeacherRegistrationState.INACTIVE]
        | Literal[TeacherRegistrationState.PENDING_VERIFICATION]
        | Literal[TeacherRegistrationState.ACTIVE]
    ):
        """Determine how registration should treat a teacher email."""

        if account is None:
            return TeacherRegistrationState.AVAILABLE

        if account.account_status == TeacherAccountStatus.LOCKED:
            return TeacherRegistrationState.LOCKED

        if account.account_status == TeacherAccountStatus.INACTIVE or not account.is_active:
            return TeacherRegistrationState.INACTIVE

        if account.account_status == TeacherAccountStatus.PENDING or not account.is_verified:
            return TeacherRegistrationState.PENDING_VERIFICATION

        return TeacherRegistrationState.ACTIVE

    @staticmethod
    def _identity_payload(account: TeacherAccount) -> AuthIdentityCreate:
        return AuthIdentityCreate(
            identifier=account.email,
            identifier_type=IdentifierType.EMAIL,
            actor_type=ActorType.TEACHER,
            actor_id=account.id,
            is_active=True,
        )

    @staticmethod
    def _build_registration_response(
        *,
        account: TeacherAccount,
        created: bool,
        message: str,
        resend_otp_available: bool,
    ) -> dict[str, Any]:
        """Build the frontend registration and verification response."""

        return {
            "created": created,
            "email": account.email,
            "verification_required": True,
            "purpose": AuthPurpose.VERIFICATION.value,
            "redirect_to": "/verify-otp",
            "resend_otp_available": resend_otp_available,
            "detail": message,
            "message": message,
        }

    @staticmethod
    async def _recover_concurrent_registration(
        *,
        db: AsyncSession,
        normalized_email: str,
        password: str,
    ) -> TeacherAccount:
        """
        Recover when two registration requests create the same email at once.

        The request that loses the unique-email race reloads the pending account,
        refreshes its password, and ensures the global auth identity exists.
        """

        async with db.begin():
            account = await TeacherAccountRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )
            state = TeacherAccountService.get_registration_state(account)

            if account is None or state != TeacherRegistrationState.PENDING_VERIFICATION:
                raise ConflictException("This email is already registered. Please log in")

            account.password_hash = hash_password(password)
            account.account_status = TeacherAccountStatus.PENDING
            account.is_verified = False
            account.is_active = True

            await TeacherAccountRepository.save(db, account)
            await AuthIdentityService.ensure_for_actor(
                db=db,
                payload=TeacherAccountService._identity_payload(account),
            )

            return account

    @staticmethod
    async def register_account(
        db: AsyncSession,
        payload: TeacherAccountRegisterRequest,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Register or resume registration for a global teacher account.

        This creates login credentials only. School access is still controlled by
        teacher memberships and invitation acceptance.
        """

        normalized_email = payload.email.strip().casefold()
        account: TeacherAccount | None = None
        reused_pending_account = False

        try:
            async with db.begin():
                normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
                    db=db,
                    email=normalized_email,
                    message="This email cannot be used for teacher registration",
                )

                account = await TeacherAccountRepository.get_by_email(
                    db,
                    normalized_email,
                    lock=True,
                )

                registration_state = TeacherAccountService.get_registration_state(account)

                if registration_state == TeacherRegistrationState.ACTIVE:
                    raise ConflictException("This email is already registered. Please log in")

                if registration_state == TeacherRegistrationState.LOCKED:
                    raise ConflictException(
                        "This teacher account is locked. Please contact support"
                    )

                if registration_state == TeacherRegistrationState.INACTIVE:
                    raise ConflictException(
                        "This teacher account is inactive. "
                        "Please contact support or use account recovery"
                    )

                password_hash = hash_password(payload.password)

                if registration_state == TeacherRegistrationState.PENDING_VERIFICATION:
                    if account is None:
                        raise ConflictException(
                            "The existing teacher registration could not be loaded"
                        )

                    reused_pending_account = True
                    account.password_hash = password_hash
                    account.account_status = TeacherAccountStatus.PENDING
                    account.is_verified = False
                    account.is_active = True

                    await TeacherAccountRepository.save(db, account)
                    await AuthIdentityService.ensure_for_actor(
                        db=db,
                        payload=TeacherAccountService._identity_payload(account),
                    )

                    logger.info(
                        "Teacher registration reused pending account",
                        extra={
                            "teacher_account_id": str(account.id),
                            "email": normalized_email,
                        },
                    )
                else:
                    account = TeacherAccount(
                        email=normalized_email,
                        password_hash=password_hash,
                        account_status=TeacherAccountStatus.PENDING,
                        is_verified=False,
                        is_active=True,
                    )

                    await TeacherAccountRepository.add(db, account)
                    await AuthIdentityService.create_for_actor(
                        db=db,
                        payload=TeacherAccountService._identity_payload(account),
                    )

                    logger.info(
                        "Created pending global teacher account",
                        extra={
                            "teacher_account_id": str(account.id),
                            "email": normalized_email,
                        },
                    )
        except IntegrityError:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)

            account = await TeacherAccountService._recover_concurrent_registration(
                db=db,
                normalized_email=normalized_email,
                password=payload.password,
            )
            reused_pending_account = True

            logger.info(
                "Recovered concurrent teacher registration",
                extra={
                    "teacher_account_id": str(account.id),
                    "email": normalized_email,
                },
            )

        if account is None:
            raise ConflictException("Teacher registration could not be completed.")

        await AuthIdentityService.invalidate_after_commit(db)

        message = (
            "Registration successful. "
            "Please check your email for the verification code."
        )
        resend_otp_available = True

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
            if not reused_pending_account:
                raise

            resend_otp_available = False
            message = (
                "Your registration already exists but needs verification. "
                "A verification code was sent recently. Please use the latest "
                "code or wait before requesting another one."
            )

        if reused_pending_account:
            if resend_otp_available:
                message = (
                    "Your registration already exists but needs verification. "
                    "We sent you a new verification code."
                )

            logger.info(
                "Resumed pending teacher registration",
                extra={
                    "teacher_account_id": str(account.id),
                    "email": normalized_email,
                    "resend_otp_available": resend_otp_available,
                },
            )

            return TeacherAccountService._build_registration_response(
                account=account,
                created=False,
                message=message,
                resend_otp_available=resend_otp_available,
            )

        logger.info(
            "Teacher registration created and verification requested",
            extra={
                "teacher_account_id": str(account.id),
                "email": normalized_email,
            },
        )

        return TeacherAccountService._build_registration_response(
            account=account,
            created=True,
            message=message,
            resend_otp_available=resend_otp_available,
        )
