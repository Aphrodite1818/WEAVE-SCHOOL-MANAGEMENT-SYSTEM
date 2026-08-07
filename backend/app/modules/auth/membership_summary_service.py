"""Account-scoped school membership summaries for workspace switching."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parents.repository import ParentAccountRepository
from app.modules.teachers.repository import TeacherAccountRepository
from app.tenant_management.models import Tenant


class AccountMembershipSummary(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    membership_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_logo_url: str | None = None
    membership_status: str
    joined_at: datetime | None = None
    ended_at: datetime | None = None


class AccountMembershipSummaryList(BaseModel):
    items: list[AccountMembershipSummary]
    total: int


class AccountMembershipSummaryService:
    @staticmethod
    async def _tenant_map(
        db: AsyncSession,
        tenant_ids: set[UUID],
    ) -> dict[UUID, Tenant]:
        if not tenant_ids:
            return {}
        tenants = (
            (await db.execute(select(Tenant).where(Tenant.id.in_(tenant_ids))))
            .scalars()
            .all()
        )
        return {tenant.id: tenant for tenant in tenants}

    @staticmethod
    async def list_parent_memberships(
        db: AsyncSession,
        *,
        account_id: UUID,
    ) -> AccountMembershipSummaryList:
        memberships = await ParentAccountRepository.list_memberships(db, account_id)
        tenant_map = await AccountMembershipSummaryService._tenant_map(
            db,
            {item.tenant_id for item in memberships},
        )
        items = [
            AccountMembershipSummary(
                membership_id=membership.id,
                tenant_id=membership.tenant_id,
                tenant_name=(
                    tenant_map[membership.tenant_id].school_name
                    if membership.tenant_id in tenant_map
                    else "Unavailable school"
                ),
                tenant_logo_url=(
                    tenant_map[membership.tenant_id].logo_url
                    if membership.tenant_id in tenant_map
                    else None
                ),
                membership_status=membership.status.value,
                joined_at=membership.joined_at,
                ended_at=membership.ended_at,
            )
            for membership in memberships
        ]
        return AccountMembershipSummaryList(items=items, total=len(items))

    @staticmethod
    async def list_teacher_memberships(
        db: AsyncSession,
        *,
        account_id: UUID,
    ) -> AccountMembershipSummaryList:
        memberships = await TeacherAccountRepository.list_memberships(db, account_id)
        tenant_map = await AccountMembershipSummaryService._tenant_map(
            db,
            {item.tenant_id for item in memberships},
        )
        items = [
            AccountMembershipSummary(
                membership_id=membership.id,
                tenant_id=membership.tenant_id,
                tenant_name=(
                    tenant_map[membership.tenant_id].school_name
                    if membership.tenant_id in tenant_map
                    else "Unavailable school"
                ),
                tenant_logo_url=(
                    tenant_map[membership.tenant_id].logo_url
                    if membership.tenant_id in tenant_map
                    else None
                ),
                membership_status=membership.status.value,
                joined_at=membership.joined_at,
                ended_at=membership.ended_at,
            )
            for membership in memberships
        ]
        return AccountMembershipSummaryList(items=items, total=len(items))
