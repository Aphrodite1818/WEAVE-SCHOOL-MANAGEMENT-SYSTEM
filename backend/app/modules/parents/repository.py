"""Repositories for global parent accounts and tenant parent relationships."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.parents.models import (
    ParentAccount,
    ParentInvitation,
    ParentInvitationStatus,
    ParentMembership,
    ParentMembershipStatus,
)
from app.modules.students.models import StudentParentLink, StudentParentLinkStatus


class ParentAccountRepository:
    @staticmethod
    async def add(db: AsyncSession, account: ParentAccount) -> ParentAccount:
        db.add(account)
        await db.flush()
        return account

    @staticmethod
    async def get_by_id(db: AsyncSession, account_id: UUID, *, lock: bool = False) -> ParentAccount | None:
        query = select(ParentAccount).where(ParentAccount.id == account_id)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, normalized_email: str, *, lock: bool = False) -> ParentAccount | None:
        query = select(ParentAccount).where(ParentAccount.email == normalized_email)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def email_exists(db: AsyncSession, normalized_email: str) -> bool:
        result = await db.execute(select(ParentAccount.id).where(ParentAccount.email == normalized_email))
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def list_memberships(db: AsyncSession, account_id: UUID) -> list[ParentMembership]:
        result = await db.execute(
            select(ParentMembership)
            .where(ParentMembership.parent_account_id == account_id)
            .order_by(ParentMembership.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(db: AsyncSession, account: ParentAccount) -> ParentAccount:
        db.add(account)
        await db.flush()
        return account


class ParentMembershipRepository:
    @staticmethod
    async def add(db: AsyncSession, membership: ParentMembership) -> ParentMembership:
        db.add(membership)
        await db.flush()
        return membership

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        membership_id: UUID,
        *,
        lock: bool = False,
        load_account: bool = False,
    ) -> ParentMembership | None:
        query = select(ParentMembership).where(
            ParentMembership.tenant_id == tenant_id,
            ParentMembership.id == membership_id,
        )
        if load_account:
            query = query.options(joinedload(ParentMembership.parent_account))
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_account_and_tenant(
        db: AsyncSession,
        account_id: UUID,
        tenant_id: UUID,
        *,
        lock: bool = False,
    ) -> ParentMembership | None:
        query = select(ParentMembership).where(
            ParentMembership.parent_account_id == account_id,
            ParentMembership.tenant_id == tenant_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        status: ParentMembershipStatus | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ParentMembership], int]:
        filters = [ParentMembership.tenant_id == tenant_id]
        if status is not None:
            filters.append(ParentMembership.status == status)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(
                ParentMembership.parent_account.has(
                    or_(
                        ParentAccount.email.ilike(pattern),
                        ParentAccount.first_name.ilike(pattern),
                        ParentAccount.last_name.ilike(pattern),
                        ParentAccount.phone_number.ilike(pattern),
                    )
                )
            )
        count_result = await db.execute(select(func.count()).select_from(ParentMembership).where(*filters))
        result = await db.execute(
            select(ParentMembership)
            .options(joinedload(ParentMembership.parent_account))
            .where(*filters)
            .order_by(ParentMembership.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().unique().all()), count_result.scalar_one()

    @staticmethod
    async def list_usable_for_account(db: AsyncSession, account_id: UUID) -> list[ParentMembership]:
        result = await db.execute(
            select(ParentMembership)
            .where(
                ParentMembership.parent_account_id == account_id,
                ParentMembership.status.in_([
                    ParentMembershipStatus.ACTIVE,
                    ParentMembershipStatus.READ_ONLY,
                ]),
            )
            .order_by(ParentMembership.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def count_active_for_tenant(db: AsyncSession, tenant_id: UUID) -> int:
        result = await db.execute(
            select(func.count()).select_from(ParentMembership).where(
                ParentMembership.tenant_id == tenant_id,
                ParentMembership.status == ParentMembershipStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    @staticmethod
    async def get_link_status_counts(
        db: AsyncSession,
        tenant_id: UUID,
        membership_id: UUID,
    ) -> dict[StudentParentLinkStatus, int]:
        result = await db.execute(
            select(StudentParentLink.status, func.count(StudentParentLink.id))
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.parent_membership_id == membership_id,
            )
            .group_by(StudentParentLink.status)
        )
        return {status: count for status, count in result.all()}

    @staticmethod
    async def save(db: AsyncSession, membership: ParentMembership) -> ParentMembership:
        db.add(membership)
        await db.flush()
        return membership


class ParentInvitationRepository:
    @staticmethod
    async def add(db: AsyncSession, invitation: ParentInvitation) -> ParentInvitation:
        db.add(invitation)
        await db.flush()
        return invitation

    @staticmethod
    async def get_by_id(db: AsyncSession, tenant_id: UUID, invitation_id: UUID, *, lock: bool = False) -> ParentInvitation | None:
        query = select(ParentInvitation).where(
            ParentInvitation.tenant_id == tenant_id,
            ParentInvitation.id == invitation_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_token_digest(db: AsyncSession, token_digest: str, *, lock: bool = False) -> ParentInvitation | None:
        query = select(ParentInvitation).where(ParentInvitation.token_digest == token_digest)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_pending_for_student_email(
        db: AsyncSession,
        tenant_id: UUID,
        student_id: UUID,
        normalized_email: str,
        *,
        lock: bool = False,
    ) -> ParentInvitation | None:
        query = select(ParentInvitation).where(
            ParentInvitation.tenant_id == tenant_id,
            ParentInvitation.student_id == student_id,
            ParentInvitation.invited_email == normalized_email,
            ParentInvitation.status == ParentInvitationStatus.PENDING,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        status: ParentInvitationStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ParentInvitation], int]:
        filters = [ParentInvitation.tenant_id == tenant_id]
        if status is not None:
            filters.append(ParentInvitation.status == status)
        count_result = await db.execute(select(func.count()).select_from(ParentInvitation).where(*filters))
        result = await db.execute(
            select(ParentInvitation)
            .where(*filters)
            .order_by(ParentInvitation.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), count_result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, invitation: ParentInvitation) -> ParentInvitation:
        db.add(invitation)
        await db.flush()
        return invitation


# Compatibility alias for legacy tenant-scoped imports. New account code should
# use ParentAccountRepository directly.
ParentRepository = ParentAccountRepository
