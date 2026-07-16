"""Global parent-account registration and profile lifecycle services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password, verify_password
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.modules.parents.models import ParentAccount, ParentAccountStatus
from app.modules.parents.repository import ParentAccountRepository
from app.modules.parents.schemas import (
    ParentAccountOnboardingRequest,
    ParentAccountPasswordChangeRequest,
    ParentAccountProfileUpdateRequest,
    ParentAccountRegisterRequest,
    normalize_email,
)


@dataclass(frozen=True, slots=True)
class ParentPasswordChangeResult:
    """Result returned after a successful parent password change."""

    account: ParentAccount
    revoke_all_sessions: bool = True


class ParentAccountService:
    """
    Business logic for the global parent identity.

    ParentAccount is not tenant-owned. This service must never create or modify
    ParentMembership records. School access is handled by invitation and
    membership services.
    """

    @staticmethod
    async def register_account(
        db: AsyncSession,
        payload: ParentAccountRegisterRequest,
    ) -> ParentAccount:
        """
        Register a global parent account.

        Registration creates login credentials only. It does not create a
        tenant membership or grant access to any student.
        """

        normalized_email = normalize_email(str(payload.email))

        try:
            async with db.begin():
                if await ParentAccountRepository.email_exists(
                    db,
                    normalized_email,
                ):
                    raise ConflictException(
                        "A parent account already exists for this email"
                    )

                account = ParentAccount(
                    email=normalized_email,
                    password_hash=hash_password(payload.password),
                    account_status=ParentAccountStatus.PENDING,
                    is_verified=False,
                    is_active=True,
                )

                return await ParentAccountRepository.add(db, account)
        except IntegrityError as exc:
            # The global unique constraint is the final protection against two
            # concurrent registrations that pass the existence check together.
            raise ConflictException(
                "A parent account already exists for this email"
            ) from exc

    @staticmethod
    async def complete_onboarding(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountOnboardingRequest,
    ) -> ParentAccount:
        """Complete the minimum global parent profile after registration."""

        async with db.begin():
            account = await ParentAccountRepository.get_by_id(
                db,
                account_id,
                lock=True,
            )
            ParentAccountService._require_account(account)
            ParentAccountService._require_profile_access(account)

            if account.profile_completed:
                raise ConflictException(
                    "Parent account onboarding has already been completed"
                )

            account.first_name = payload.first_name
            account.last_name = payload.last_name
            account.phone_number = payload.phone_number
            account.occupation = payload.occupation
            account.address = payload.address
            account.emergency_phone = payload.emergency_phone

            return await ParentAccountRepository.save(db, account)

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountProfileUpdateRequest,
    ) -> ParentAccount:
        """Update parent-controlled fields on the global profile."""

        async with db.begin():
            account = await ParentAccountRepository.get_by_id(
                db,
                account_id,
                lock=True,
            )
            ParentAccountService._require_account(account)
            ParentAccountService._require_profile_access(account)

            changes = payload.model_dump(exclude_unset=True)
            for field_name, value in changes.items():
                setattr(account, field_name, value)

            return await ParentAccountRepository.save(db, account)

    @staticmethod
    async def change_password(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountPasswordChangeRequest,
    ) -> ParentPasswordChangeResult:
        """
        Change the global parent password.

        The caller must revoke all global parent-account sessions and all
        tenant-context parent-membership sessions after the transaction commits.
        """

        async with db.begin():
            account = await ParentAccountRepository.get_by_id(
                db,
                account_id,
                lock=True,
            )
            ParentAccountService._require_account(account)
            ParentAccountService._require_authentication_access(account)

            if not verify_password(
                payload.current_password,
                account.password_hash,
            ):
                raise UnauthorizedException("Current password is incorrect")

            if verify_password(payload.new_password, account.password_hash):
                raise ConflictException(
                    "New password must be different from the current password"
                )

            account.password_hash = hash_password(payload.new_password)
            saved_account = await ParentAccountRepository.save(db, account)

            return ParentPasswordChangeResult(account=saved_account)

    @staticmethod
    async def get_account(
        db: AsyncSession,
        *,
        account_id: UUID,
    ) -> ParentAccount:
        """Return one global parent account by ID."""

        account = await ParentAccountRepository.get_by_id(db, account_id)
        ParentAccountService._require_account(account)
        return account

    @staticmethod
    def _require_account(
        account: ParentAccount | None,
    ) -> ParentAccount:
        """Return the account or raise a stable not-found exception."""

        if account is None:
            raise NotFoundException("Parent account not found")
        return account

    @staticmethod
    def _require_profile_access(account: ParentAccount) -> None:
        """Ensure the account may update its global profile."""

        if not account.is_active:
            raise ForbiddenException("Parent account is inactive")

        if account.account_status == ParentAccountStatus.LOCKED:
            raise ForbiddenException("Parent account is locked")

        if account.account_status == ParentAccountStatus.INACTIVE:
            raise ForbiddenException("Parent account is inactive")

    @staticmethod
    def _require_authentication_access(account: ParentAccount) -> None:
        """Ensure the account may change authentication credentials."""

        ParentAccountService._require_profile_access(account)

        if account.account_status not in {
            ParentAccountStatus.PENDING,
            ParentAccountStatus.ACTIVE,
        }:
            raise ForbiddenException(
                "Parent account cannot change its password in its current state"
            )
