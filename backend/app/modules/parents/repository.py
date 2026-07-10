from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.parents.models import Parent


class ParentRepository:
    """Database operations for parent actors."""

    @staticmethod
    async def create_parent(
        db: AsyncSession,
        parent: Parent,
    ) -> Parent:
        """Create a parent record."""

        db.add(parent)
        await db.flush()
        await db.refresh(parent)
        return parent

    @staticmethod
    async def get_parent_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        parent_id: UUID,
    ) -> Parent | None:
        """Get parent by ID within a tenant."""

        result = await db.execute(
            select(Parent).where(
                Parent.id == parent_id,
                Parent.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        parent_id: UUID,
        *,
        lock: bool = False,
    ) -> Parent | None:
        """Get parent by global ID."""

        query = select(Parent).where(Parent.id == parent_id)

        if lock:
            query = query.with_for_update()

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_id(
        db: AsyncSession,
        parent_id: UUID,
    ) -> Parent | None:
        """Get active parent by global ID."""

        result = await db.execute(
            select(Parent).where(
                Parent.id == parent_id,
                Parent.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(
        db: AsyncSession,
        email: str,
    ) -> Parent | None:
        """Get parent by globally unique email."""

        result = await db.execute(
            select(Parent).where(
                func.lower(Parent.email) == email.strip().lower(),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_email(
        db: AsyncSession,
        email: str,
    ) -> Parent | None:
        """Get active parent by globally unique email."""

        result = await db.execute(
            select(Parent).where(
                func.lower(Parent.email) == email.strip().lower(),
                Parent.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def email_exists(
        db: AsyncSession,
        email: str,
        exclude_parent_id: UUID | None = None,
    ) -> bool:
        """Return True if a parent email already exists."""

        query = select(Parent.id).where(
            func.lower(Parent.email) == email.strip().lower(),
        )

        if exclude_parent_id is not None:
            query = query.where(Parent.id != exclude_parent_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def list_all_parents(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
    ) -> tuple[list[Parent], int]:
        """List parents within a tenant."""

        filters = [Parent.tenant_id == tenant_id]

        if search:
            search_pattern = f"%{search.strip()}%"
            filters.append(
                or_(
                    Parent.email.ilike(search_pattern),
                    Parent.first_name.ilike(search_pattern),
                    Parent.last_name.ilike(search_pattern),
                    Parent.phone_number.ilike(search_pattern),
                    Parent.occupation.ilike(search_pattern),
                )
            )

        total_result = await db.execute(
            select(func.count()).select_from(Parent).where(*filters)
        )
        total = total_result.scalar_one()

        result = await db.execute(
            select(Parent)
            .where(*filters)
            .order_by(Parent.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    @staticmethod
    async def save(
        db: AsyncSession,
        parent: Parent,
    ) -> Parent:
        """Persist parent changes."""

        db.add(parent)
        await db.flush()
        await db.refresh(parent)
        return parent

    @staticmethod
    async def update_parent(
        db: AsyncSession,
        parent: Parent,
    ) -> Parent:
        """Compatibility wrapper for persisting parent changes."""

        return await ParentRepository.save(db=db, parent=parent)

    @staticmethod
    async def delete_parent(
        db: AsyncSession,
        parent: Parent,
    ) -> None:
        """Delete a parent profile."""

        await db.delete(parent)
        await db.flush()
