"""Database access helpers for tenant branding."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant_branding.models import TenantBranding


class TenantBrandingRepository:
    """Persistence operations for tenant branding rows only."""

    @staticmethod
    async def create_branding(
        db: AsyncSession,
        *,
        branding: TenantBranding,
    ) -> TenantBranding:
        """Create a tenant branding row."""

        db.add(branding)
        await db.flush()
        await db.refresh(branding)
        return branding

    @staticmethod
    async def get_by_tenant_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> TenantBranding | None:
        """Fetch branding for a tenant."""

        result = await db.execute(
            select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_tenant_id_for_update(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> TenantBranding | None:
        """Fetch branding for a tenant with a row-level lock."""

        result = await db.execute(
            select(TenantBranding).where(TenantBranding.tenant_id == tenant_id).with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        defaults: dict[str, Any],
    ) -> TenantBranding:
        """Return the tenant branding row, creating it when missing."""

        branding = await TenantBrandingRepository.get_by_tenant_id_for_update(
            db=db,
            tenant_id=tenant_id,
        )
        if branding is not None:
            return branding

        branding = TenantBranding(
            tenant_id=tenant_id,
            **defaults,
        )
        return await TenantBrandingRepository.create_branding(
            db=db,
            branding=branding,
        )

    @staticmethod
    async def update_branding(
        db: AsyncSession,
        *,
        branding: TenantBranding,
        updates: dict[str, Any],
    ) -> TenantBranding:
        """Apply field updates to an existing branding row."""

        for field_name, value in updates.items():
            setattr(branding, field_name, value)

        return await TenantBrandingRepository.save(
            db=db,
            branding=branding,
        )

    @staticmethod
    async def reset_branding(
        db: AsyncSession,
        *,
        branding: TenantBranding,
        defaults: dict[str, Any],
    ) -> TenantBranding:
        """Reset a branding row back to default values."""

        for field_name, value in defaults.items():
            setattr(branding, field_name, value)

        return await TenantBrandingRepository.save(
            db=db,
            branding=branding,
        )

    @staticmethod
    async def save(
        db: AsyncSession,
        *,
        branding: TenantBranding,
    ) -> TenantBranding:
        """Persist changes to a tenant branding row."""

        db.add(branding)
        await db.flush()
        await db.refresh(branding)
        return branding
