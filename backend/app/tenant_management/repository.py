# ======================================#
#    tenant_management/repository.py   #
# ======================================#

"""Provide data-access helpers for tenant entities."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant_management.models import Tenant, TenantVerificationStatus


def _normalize_email(email: str) -> str:
    """Normalize the email address."""
    return email.strip().lower()


class TenantRepository:
    """Encapsulate tenant persistence and lookup operations."""

    @staticmethod
    async def get_by_id_including_deleted(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> Tenant | None:
        """Return a tenant by ID whether or not it has been soft-deleted."""
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a non-deleted tenant by ID."""

        query = select(Tenant).where(Tenant.id == tenant_id, Tenant.is_deleted == False)

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_slug(
        db: AsyncSession,
        slug: str,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a non-deleted tenant by slug."""
        query = select(Tenant).where(Tenant.slug == slug, Tenant.is_deleted == False)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_admission_number_prefix(
        db: AsyncSession,
        admission_number_prefix: str,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a non-deleted tenant by admission number prefix."""
        normalized_prefix = admission_number_prefix.strip().upper()
        query = select(Tenant).where(
            func.upper(Tenant.admission_number_prefix) == normalized_prefix,
            Tenant.is_deleted == False,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(
        db: AsyncSession,
        email: str,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a non-deleted tenant by email address."""
        normalized_email = _normalize_email(email)
        query = select(Tenant).where(
            func.lower(Tenant.email) == normalized_email, Tenant.is_deleted == False
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email_including_deleted(
        db: AsyncSession,
        email: str,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a tenant by email address whether or not it has been soft-deleted."""
        normalized_email = _normalize_email(email)
        query = select(Tenant).where(func.lower(Tenant.email) == normalized_email)
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_school_name(
        db: AsyncSession,
        school_name: str,
        *,
        lock: bool = False,
    ) -> Tenant | None:
        """Return a non-deleted tenant by normalized school name."""
        normalized_school_name = school_name.strip().lower()
        query = select(Tenant).where(
            func.lower(Tenant.school_name) == normalized_school_name,
            Tenant.is_deleted == False,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_school_bot_number(
        db: AsyncSession,
        school_bot_whatssap_number: str,
    ) -> Tenant | None:
        """Return a non-deleted tenant by its WhatsApp bot number."""
        result = await db.execute(
            select(Tenant).where(
                Tenant.school_bot_whatssap_number == school_bot_whatssap_number,
                Tenant.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        include_deleted: bool = False,
    ) -> list[Tenant]:
        """Return a paginated list of tenants."""
        statement = select(Tenant)
        if not include_deleted:
            statement = statement.where(Tenant.is_deleted == False)

        result = await db.execute(statement.offset(skip).limit(limit))
        return list(result.scalars().all())

    @staticmethod
    async def create(db: AsyncSession, tenant: Tenant) -> Tenant:
        """Persist a tenant and flush it into the current transaction."""
        db.add(tenant)
        await db.flush()
        return tenant

    @staticmethod
    async def save(
        db: AsyncSession,
        tenant: Tenant,
    ) -> Tenant:
        """Persist tenant changes."""
        db.add(tenant)
        await db.flush()
        await db.refresh(tenant)
        return tenant

    @staticmethod
    async def email_exists(db: AsyncSession, email: str) -> bool:
        """Return whether a tenant already exists for the given email."""
        normalized_email = _normalize_email(email)

        result = await db.execute(
            select(Tenant.id)
            .where(Tenant.email == normalized_email)
            .limit(1)  # stop searching after first match
        )

        return result.scalar_one_or_none() is not None

    @staticmethod
    async def slug_exists(db: AsyncSession, slug: str) -> bool:
        """Return whether a tenant slug is already in use."""
        result = await db.execute(select(Tenant.id).where(Tenant.slug == slug).limit(1))

        return result.scalar_one_or_none() is not None

    @staticmethod
    async def school_bot_whatssap_number_exists(
        db: AsyncSession,
        whatssap_number: str,
    ) -> bool:
        """Return whether a WhatsApp bot number is already assigned."""
        result = await db.execute(
            select(Tenant.id).where(Tenant.school_bot_whatssap_number == whatssap_number).limit(1)
        )

        return result.scalar_one_or_none() is not None

    @staticmethod
    async def is_verified(db: AsyncSession, email: str) -> bool:
        """Return whether the tenant linked to the email is verified."""
        normalized_email = _normalize_email(email)

        result = await db.execute(
            select(Tenant.verification_status).where(Tenant.email == normalized_email).limit(1)
        )

        return result.scalar_one_or_none() == TenantVerificationStatus.ACTIVE
