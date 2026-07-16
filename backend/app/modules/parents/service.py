#==========================#
#     parent.service.py    #
#==========================#


"""service layer for global parent account registration"""


from __future__ import annotations
from enum import Enum as PyEnum
from typing import Any, Literal
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_password
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    TooManyRequestsException
)

from app.modules.auth.account_email_guard import AccountEmailGuard
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.repository import AuthIdentityRepository
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.auth.models import AuthPurpose
from app.modules.auth.schemas import RequestOTP
from app.modules.auth.service import OTPService
from app.modules.parents.models import(
    ParentAccount,
    ParentAccountStatus
)
from app.modules.parents.repository import ParentAccountRepository
from app.modules.parents.schemas import ParentAccountRegisterRequest
from app.modules.parents.schemas import (
    ParentAccountOnboardingRequest,
    ParentAccountProfileUpdateRequest,
    ParentAccountResponse,
)
 
logger = get_logger(__name__)

class ParentRegistrationState(str , PyEnum):
    """Possible registration states for a global parent account"""

    AVAILABLE = "AVAILABLE"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    INACTIVE = "INACTIVE"


class ParentAccountService:
    """Business logic for global parent accounts"""


    @staticmethod
    def get_registration_state(
        account : ParentAccount | None
    ) -> Literal[ParentRegistrationState.AVAILABLE] | Literal[ParentRegistrationState.LOCKED] | Literal[ParentRegistrationState.INACTIVE] | Literal[ParentRegistrationState.PENDING_VERIFICATION] | Literal[ParentRegistrationState.ACTIVE]:
        """
        Determine how registration should treat a parent email

        AVAILABLE:
            no parent account owns the email


        PENDING_VERIFICATION:
            Registration was started but email verification was not completed


        ACTIVE:
            The global parent account has already been verified and activated


        LOCKED:
            The global account was locked for security or administrative 
            reasons


        INACTIVE:
            the global account has been deactivated and must not be
            silently restored through registration
        """


        if account is None:
            return ParentRegistrationState.AVAILABLE
        

        if account.account_status == ParentAccountStatus.LOCKED:
            return ParentRegistrationState.LOCKED
        
        if(
            account.account_status == ParentAccountStatus.INACTIVE
            or not account.is_active
        ):
            return ParentRegistrationState.INACTIVE
        

        if(
            account.account_status == ParentAccountStatus.PENDING
            or not account.is_verified
        ):
            return ParentRegistrationState.PENDING_VERIFICATION
        

        return ParentRegistrationState.ACTIVE
    


    @staticmethod
    def _build_registration_response(
        *,
        account : ParentAccount,
        created: bool,
        message : str,
        resend_otp_available : bool
    ) -> dict[str, Any]:
        """Build the frontend registration and verification response"""

        return{
            "created": created,
            "email":account.email,
            "verification_required": True,
            "purpose":AuthPurpose.VERIFICATION.value,
            "redirect_to" :"/verify-otp",
            "resend_otp_available" : resend_otp_available,
            "detail" : message,
            "message":message

        }

    @staticmethod
    def _require_account(account: ParentAccount | None) -> ParentAccount:
        """Return the loaded global parent account or raise a stable error."""

        if account is None:
            raise NotFoundException("Parent account not found")
        return account

    @staticmethod
    def _require_onboarding_access(account: ParentAccount) -> None:
        """Ensure the account is allowed to update its global profile."""

        if not account.is_active:
            raise ForbiddenException("Parent account is inactive")

        if account.account_status == ParentAccountStatus.LOCKED:
            raise ForbiddenException("Parent account is locked")

        if account.account_status == ParentAccountStatus.INACTIVE:
            raise ForbiddenException("Parent account is inactive")

    @staticmethod
    async def _load_registration_account(
        *,
        db: AsyncSession,
        normalized_email: str,
    ) -> ParentAccount | None:
        """
        Load the parent account allowed to use this email.

        AuthIdentity is the login ownership table, so it must be checked before
        creating or resuming a role-specific account. A matching parent-account
        identity can resume through the parent account row; any other identity
        means this email already belongs to another authenticatable actor.
        """

        identity = await AuthIdentityRepository.get_by_identifier(
            db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )

        if identity is None:
            return await ParentAccountRepository.get_by_email(
                db,
                normalized_email,
                lock=True,
            )

        if identity.actor_type != ActorType.PARENT:
            raise ConflictException("This email is already registered. Please log in")

        account = await ParentAccountRepository.get_by_id(
            db,
            identity.actor_id,
            lock=True,
        )

        if account is None or account.email != normalized_email:
            raise ConflictException("This email is already registered. Please log in")

        return account
    



    @staticmethod
    async def _recover_concurrent_registration(
        *,
        db : AsyncSession,
        normalized_email : str ,
        password : str 
    ) -> ParentAccount:
        """
        Recover when two regisration requests create the same email at once

        The unique email constraints allow only on insert. The request
        that loses the race reloads the newly creatd account and treates it
        as a resumable pending registration
        """

        async with db.begin():
            account = await ParentAccountRepository.get_by_email(
                db,
                normalized_email,
                lock = True
            )
            state = ParentAccountService.get_registration_state(account)


            if(
                account is None
                or state != ParentRegistrationState.PENDING_VERIFICATION
            ):
                raise ConflictException(
                    "This email is already registered. Please log in"
                )
            

            account.password_hash = hash_password(password)
            account.account_status = ParentAccountStatus.PENDING
            account.is_verified = False
            account.is_active = True

            await ParentAccountRepository.save(
                db,
                account
            )

            await AuthIdentityService.ensure_for_actor(
                db=db,
                payload=AuthIdentityCreate(
                    identifier=normalized_email,
                    identifier_type=IdentifierType.EMAIL,
                    actor_type=ActorType.PARENT,
                    actor_id=account.id,
                    is_active=True,
                ),
            )

            return account
        



    @staticmethod
    async def register_account(
        db : AsyncSession,
        payload : ParentAccountRegisterRequest,
        background_tasks : BackgroundTasks | None = None
    ) -> dict[str, Any]:
        """
        Register or resume registration for a global parent account

        New registration:
         creates a pending parent account and sends an email - verification OTP

         partial registration
            reuses the existing pending account, replaces its password with 
            the newly supplied password and sends or reuses an OTP

        Active account:
            Registration is rejected and the user is directed to log in


        Locked or inactive account:
            Registration cannot reactivate the account 
        """


        normalized_email = payload.email.strip().casefold()
        account : ParentAccount | None = None
        reused_pending_account = False

        try:
            async with db.begin():
                normalized_email = (
                    await AccountEmailGuard.ensure_not_superadmin_email(
                        db = db ,
                        email = normalized_email,
                        message = "This email cannot be used for parent registration"
                    )
                )


                account = await ParentAccountService._load_registration_account(
                    db=db,
                    normalized_email=normalized_email,
                )


                registration_state = (
                    ParentAccountService.get_registration_state(account)
                )

                if registration_state == ParentRegistrationState.ACTIVE:
                    raise ConflictException(
                        "This email is already registered. Please log in"
                    )
                

                if registration_state == ParentRegistrationState.LOCKED:
                    raise ConflictException(
                        "This parent account is locked , Please contact support"
                    )
                


                if registration_state == ParentRegistrationState.INACTIVE:
                    raise ConflictException(
                        "This parent account is inactive"
                        "Please contact support or use account recovery"
                    )
                

                password_hash = hash_password(payload.password)



                if(
                    registration_state
                    == ParentRegistrationState.PENDING_VERIFICATION
                ):
                    if account is None:
                        raise ConflictException(
                            "The existing parent registration could not be loaded"
                        )
                    

                    reused_pending_account = True


                    account.password_hash = password_hash
                    account.account_status = ParentAccountStatus.PENDING
                    account.is_verified = False
                    account.is_active = True


                    await ParentAccountRepository.save(
                        db,
                        account
                    )

                    await AuthIdentityService.ensure_for_actor(
                        db=db,
                        payload=AuthIdentityCreate(
                            identifier=normalized_email,
                            identifier_type=IdentifierType.EMAIL,
                            actor_type=ActorType.PARENT,
                            actor_id=account.id,
                            is_active=True,
                        ),
                    )


                    logger.info(
                        "Parent registration reused pending account",
                        extra = {
                            "parent_account_id": str(account.id),
                            "email" : normalized_email
                        }
                    )

                else:
                    account = ParentAccount(
                        email = normalized_email,
                        password_hash = password_hash,
                        account_status = ParentAccountStatus.PENDING,
                        is_verified = False ,
                        is_active = True
                    )


                    await ParentAccountRepository.add(
                        db ,
                        account
                    )

                    await AuthIdentityService.create_for_actor(
                        db=db,
                        payload=AuthIdentityCreate(
                            identifier=normalized_email,
                            identifier_type=IdentifierType.EMAIL,
                            actor_type=ActorType.PARENT,
                            actor_id=account.id,
                            is_active=True,
                        ),
                    )


                    logger.info(
                        "Created pending global parent account",
                        extra={
                            "parent_account_id": str(account.id),
                            "email": normalized_email
                        }
                    )


        except IntegrityError:
            await db.rollback()
            AuthIdentityService.discard_pending_invalidations(db)

            account = await ParentAccountService._recover_concurrent_registration(
                db = db ,
                normalized_email = normalized_email,
                password = payload.password
            )

            reused_pending_account = True


            logger.info(
                "Recovered concurrent parent registration",

                extra = {
                    "parent_account_id": str(account.id),
                    "email" : normalized_email
                }
            )


        if account is None:
            raise ConflictException(
                "Parent registration could not be completed."
            )

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
                # A brand-new registration should not claim a verification OTP
                # was sent when the first dispatch was rate-limited or failed.
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
                "Resumed pending parent registration",
                extra={
                    "parent_account_id": str(account.id),
                    "email": normalized_email,
                    "resend_otp_available": resend_otp_available,
                },
            )

            return ParentAccountService._build_registration_response(
                account=account,
                created=False,
                message=message,
                resend_otp_available=resend_otp_available,
            )

        logger.info(
            "Parent registration created and verification requested",
            extra={
                "parent_account_id": str(account.id),
                "email": normalized_email,
            },
        )

        return ParentAccountService._build_registration_response(
            account=account,
            created=True,
            message=message,
            resend_otp_available=resend_otp_available,
        )

    @staticmethod
    def _parent_onboarding_status(account: ParentAccount) -> dict[str, Any]:
        """Build a compact onboarding status payload for the frontend."""

        return {
            "actor_type": "parent",
            "parent_account_id": account.id,
            "onboarding_required": not account.profile_completed,
            "profile_completed": account.profile_completed,
            "completion_target": "parent_account",
            "required_fields": ["first_name", "last_name"],
            "current_values": {
                "email": account.email,
                "first_name": account.first_name,
                "last_name": account.last_name,
                "phone_number": account.phone_number,
                "occupation": account.occupation,
                "address": account.address,
                "emergency_phone": account.emergency_phone,
            },
        }

    @staticmethod
    async def get_onboarding_status(
        db: AsyncSession,
        *,
        account_id: UUID,
    ) -> dict[str, Any]:
        """Return onboarding state for a global parent account."""

        account = await ParentAccountRepository.get_by_id(db, account_id)
        account = ParentAccountService._require_account(account)
        ParentAccountService._require_onboarding_access(account)
        return ParentAccountService._parent_onboarding_status(account)

    @staticmethod
    async def complete_onboarding(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountOnboardingRequest,
    ) -> ParentAccountResponse:
        """
        Complete the global parent profile after lightweight registration.

        This intentionally updates only ParentAccount fields. Tenant
        memberships and student links remain invitation/admin-owned workflows.
        """

        account = await ParentAccountRepository.get_by_id(
            db,
            account_id,
            lock=True,
        )
        account = ParentAccountService._require_account(account)
        ParentAccountService._require_onboarding_access(account)

        if account.profile_completed:
            raise ConflictException(
                "Parent account onboarding has already been completed"
            )

        update_data = payload.model_dump()
        for field, value in update_data.items():
            setattr(account, field, value)

        updated_account = await ParentAccountRepository.save(db, account)

        await db.refresh(updated_account)
        return ParentAccountResponse.model_validate(updated_account)

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountProfileUpdateRequest,
    ) -> ParentAccountResponse:
        """
        Update parent-controlled global profile fields.

        Email and password are intentionally excluded from this flow because
        they need dedicated verification and credential-change workflows.
        """

        account = await ParentAccountRepository.get_by_id(
            db,
            account_id,
            lock=True,
        )
        account = ParentAccountService._require_account(account)
        ParentAccountService._require_onboarding_access(account)

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)

        updated_account = await ParentAccountRepository.save(db, account)

        await db.refresh(updated_account)
        return ParentAccountResponse.model_validate(updated_account)
