"""Cross-account email conflict guards."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.repository import AuthIdentityRepository
from app.modules.superadmin.repository import SuperAdminRepository


INVITATION_ROLE_LABELS = {
    ActorType.PARENT_ACCOUNT: "parent",
    ActorType.TEACHER_ACCOUNT: "teacher",
}
INVITATION_EMAIL_CONFLICT_MESSAGE = (
    "This email is already registered under another role."
)


class AccountEmailGuard:
    """Reusable email guards for account creation and invitation flows."""

    @staticmethod
    def _normalize_email(email: str) -> str:
        """Normalize email consistently before lookup or storage."""

        return email.strip().lower()

    @staticmethod
    async def ensure_not_superadmin_email(
        db: AsyncSession,
        email: str,
        *,
        exclude_superadmin_id: uuid.UUID | None = None,
        message: str = "This email is already in use",
    ) -> str:
        """
        Block tenant-side accounts from using an existing superadmin email.

        Returns the normalized email so callers can persist a consistent value.
        """

        normalized_email = AccountEmailGuard._normalize_email(email)

        existing_superadmin = await SuperAdminRepository.get_by_email(
            db=db,
            email=normalized_email,
        )

        if existing_superadmin is not None:
            if (
                exclude_superadmin_id is None
                or existing_superadmin.id != exclude_superadmin_id
            ):
                raise ConflictException(message)

        return normalized_email

    @staticmethod
    async def ensure_available_for_invitation_role(
        db: AsyncSession,
        email: str,
        *,
        invited_actor_type: ActorType,
    ) -> str:
        """
        Ensure an invitation email is not already owned by an incompatible role.

        Invitations create real records and can send emails, so the backend must
        reject wrong-role addresses before the invite is persisted.
        """

        invited_actor_type = ActorType(invited_actor_type)
        if invited_actor_type not in INVITATION_ROLE_LABELS:
            raise ValueError("Unsupported invitation actor type.")

        normalized_email = await AccountEmailGuard.ensure_not_superadmin_email(
            db=db,
            email=email,
            message=INVITATION_EMAIL_CONFLICT_MESSAGE,
        )
        identity = await AuthIdentityRepository.get_by_identifier(
            db,
            normalized_email,
            IdentifierType.EMAIL,
        )
        if identity is None:
            return normalized_email

        if identity.actor_type == invited_actor_type:
            return normalized_email

        raise ConflictException(INVITATION_EMAIL_CONFLICT_MESSAGE)
