import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.superadmin.models import SuperAdmin, SuperAdminInvite


def _normalize_email(email: str) -> str:
    """Normalize the email address."""
    return email.strip().lower()


class SuperAdminRepository:
    """Database access helpers for the superadmin domain."""

    @staticmethod
    async def get_by_id(db: AsyncSession, superadmin_id: uuid.UUID) -> SuperAdmin | None:
        """Return the record matched by id."""
        result = await db.execute(select(SuperAdmin).where(SuperAdmin.id == superadmin_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> SuperAdmin | None:
        """Return the record matched by email."""
        result = await db.execute(
            select(SuperAdmin).where(func.lower(SuperAdmin.email) == _normalize_email(email))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SuperAdmin]:
        """Perform list."""
        result = await db.execute(select(SuperAdmin).offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, superadmin: SuperAdmin) -> SuperAdmin:
        """Perform create."""
        db.add(superadmin)
        await db.flush()
        await db.refresh(superadmin)
        return superadmin

    @staticmethod
    async def save(db: AsyncSession, superadmin: SuperAdmin) -> SuperAdmin:
        """Perform save."""
        db.add(superadmin)
        await db.flush()
        await db.refresh(superadmin)
        return superadmin

    @staticmethod
    async def create_invite(db: AsyncSession, invite: SuperAdminInvite) -> SuperAdminInvite:
        """Create invite."""
        db.add(invite)
        await db.flush()
        await db.refresh(invite)
        return invite

    @staticmethod
    async def delete_active_invites_for_email(db: AsyncSession, email: str) -> None:
        """Delete active invites for email."""
        await db.execute(
            delete(SuperAdminInvite).where(
                func.lower(SuperAdminInvite.email) == _normalize_email(email),
                SuperAdminInvite.is_used == False,
            )
        )

    @staticmethod
    async def get_invite_by_hashed_token(
        db: AsyncSession,
        hashed_token: str,
    ) -> SuperAdminInvite | None:
        """Return invite by hashed token."""
        result = await db.execute(
            select(SuperAdminInvite)
            .where(SuperAdminInvite.hashed_token == hashed_token)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_invite_status_record(
        db: AsyncSession,
        hashed_token: str,
    ) -> SuperAdminInvite | None:
        """Return invite status record."""
        result = await db.execute(
            select(SuperAdminInvite)
            .where(SuperAdminInvite.hashed_token == hashed_token)
            .order_by(SuperAdminInvite.created_at.desc())
        )
        return result.scalars().first()
