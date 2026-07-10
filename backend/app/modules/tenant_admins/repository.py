# ====================================== #
#      tenant_admins/repository.py       #
# ====================================== #

"""Tenant admins data access layer."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenant_admins.models import TenantAdmin


class TenantAdminRepository:
    """Database operations for tenant admin records."""

    @staticmethod
    async def create(
        db: AsyncSession,
        admin: TenantAdmin,
    ) -> TenantAdmin:
        """Create a tenant admin record."""

        db.add(admin)
        await db.flush()
        await db.refresh(admin)
        return admin

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        admin_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> TenantAdmin | None:
        """Fetch tenant admin by ID."""

        query = select(TenantAdmin).where(
            TenantAdmin.id == admin_id,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_id(
        db: AsyncSession,
        admin_id: uuid.UUID,
    ) -> TenantAdmin | None:
        """Fetch active tenant admin by ID."""

        result = await db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == admin_id,
                TenantAdmin.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(
        db: AsyncSession,
        email: str,
        *,
        lock: bool = False,
    ) -> TenantAdmin | None:
        """Fetch tenant admin by email."""

        query = select(TenantAdmin).where(
            func.lower(TenantAdmin.email) == email.strip().lower(),
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_tenant_and_id(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        admin_id: uuid.UUID,
        lock: bool = False,
    ) -> TenantAdmin | None:
        """Fetch a tenant admin by ID within a tenant."""

        query = select(TenantAdmin).where(
            TenantAdmin.tenant_id == tenant_id,
            TenantAdmin.id == admin_id,
        )

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_email(
        db: AsyncSession,
        email: str,
    ) -> TenantAdmin | None:
        """Fetch active tenant admin by email."""

        result = await db.execute(
            select(TenantAdmin).where(
                func.lower(TenantAdmin.email) == email.strip().lower(),
                TenantAdmin.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_tenant_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> TenantAdmin | None:
        """Fetch the admin account attached to a tenant."""

        result = await db.execute(
            select(TenantAdmin).where(
                TenantAdmin.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def email_exists(
        db: AsyncSession,
        email: str,
        exclude_admin_id: uuid.UUID | None = None,
    ) -> bool:
        """Return True if a tenant admin email already exists."""

        query = select(TenantAdmin.id).where(
            func.lower(TenantAdmin.email) == email.strip().lower(),
        )

        if exclude_admin_id is not None:
            query = query.where(TenantAdmin.id != exclude_admin_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def save(
        db: AsyncSession,
        admin: TenantAdmin,
    ) -> TenantAdmin:
        """Persist changes to an existing tenant admin record."""

        db.add(admin)
        await db.flush()
        await db.refresh(admin)
        return admin
