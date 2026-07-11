# ====================================== #
#      auth_identity/repository.py       #
# ====================================== #

"""Auth identity data access layer."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth_identity.models import (
    ActorType,
    AuthIdentity,
    IdentifierType,
)


class AuthIdentityRepository:
    """Database operations for AuthIdentity records."""

    @staticmethod
    async def create(
        db: AsyncSession,
        record: AuthIdentity,
    ) -> AuthIdentity:
        """Create an auth identity record."""

        db.add(record)
        await db.flush()
        return record

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        identity_id: uuid.UUID,
    ) -> AuthIdentity | None:
        """Fetch an auth identity by its primary ID."""

        result = await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.id == identity_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_identifier(
        db: AsyncSession,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> AuthIdentity | None:
        """Fetch an identity by login identifier, active or inactive."""

        result = await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.identifier == identifier,
                AuthIdentity.identifier_type == identifier_type,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_identifier(
        db: AsyncSession,
        identifier: str,
        identifier_type: IdentifierType,
    ) -> AuthIdentity | None:
        """Fetch an active identity by login identifier."""

        result = await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.identifier == identifier,
                AuthIdentity.identifier_type == identifier_type,
                AuthIdentity.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_actor(
        db: AsyncSession,
        actor_type: ActorType,
        actor_id: uuid.UUID,
    ) -> AuthIdentity | None:
        """Fetch an identity by actor type and actor ID."""

        result = await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.actor_type == actor_type,
                AuthIdentity.actor_id == actor_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def identifier_exists(
        db: AsyncSession,
        identifier: str,
        identifier_type: IdentifierType,
        exclude_identity_id: uuid.UUID | None = None,
    ) -> bool:
        """Return True if a login identifier already exists."""

        conditions = [
            AuthIdentity.identifier == identifier,
            AuthIdentity.identifier_type == identifier_type,
        ]

        if exclude_identity_id is not None:
            conditions.append(AuthIdentity.id != exclude_identity_id)

        result = await db.execute(select(exists().where(*conditions)))
        return bool(result.scalar())

    @staticmethod
    async def save(
        db: AsyncSession,
        record: AuthIdentity,
    ) -> AuthIdentity:
        """Persist changes to an existing identity record."""

        await db.flush()
        return record

    @staticmethod
    async def deactivate(
        db: AsyncSession,
        record: AuthIdentity,
    ) -> AuthIdentity:
        """Deactivate an identity record."""

        record.is_active = False
        await db.flush()
        return record
