"""Repositories used by academic-session closure and student progression services."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    StudentProgressionItem,
    StudentProgressionRun,
)


class AcademicSessionLifecycleRepository:
    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        session_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.id == session_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_current_open(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.is_current.is_(True),
            AcademicSession.status == AcademicSessionStatus.OPEN,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(db: AsyncSession, tenant_id: UUID) -> list[AcademicSession]:
        result = await db.execute(
            select(AcademicSession)
            .where(AcademicSession.tenant_id == tenant_id)
            .order_by(
                AcademicSession.start_date.asc().nulls_last(),
                AcademicSession.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(db: AsyncSession, session: AcademicSession) -> AcademicSession:
        db.add(session)
        await db.flush()
        return session


class StudentProgressionRunRepository:
    @staticmethod
    async def add(db: AsyncSession, run: StudentProgressionRun) -> StudentProgressionRun:
        db.add(run)
        await db.flush()
        return run

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        tenant_id: UUID,
        run_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentProgressionRun | None:
        query = select(StudentProgressionRun).where(
            StudentProgressionRun.tenant_id == tenant_id,
            StudentProgressionRun.id == run_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_session(
        db: AsyncSession,
        tenant_id: UUID,
        academic_session_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentProgressionRun | None:
        query = select(StudentProgressionRun).where(
            StudentProgressionRun.tenant_id == tenant_id,
            StudentProgressionRun.academic_session_id == academic_session_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_idempotency_key(
        db: AsyncSession,
        tenant_id: UUID,
        idempotency_key: str,
        *,
        lock: bool = False,
    ) -> StudentProgressionRun | None:
        query = select(StudentProgressionRun).where(
            StudentProgressionRun.tenant_id == tenant_id,
            StudentProgressionRun.idempotency_key == idempotency_key,
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
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[StudentProgressionRun], int]:
        count_result = await db.execute(
            select(func.count()).select_from(StudentProgressionRun).where(
                StudentProgressionRun.tenant_id == tenant_id
            )
        )
        result = await db.execute(
            select(StudentProgressionRun)
            .where(StudentProgressionRun.tenant_id == tenant_id)
            .order_by(StudentProgressionRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), count_result.scalar_one()

    @staticmethod
    async def save(db: AsyncSession, run: StudentProgressionRun) -> StudentProgressionRun:
        db.add(run)
        await db.flush()
        return run


class StudentProgressionItemRepository:
    @staticmethod
    async def add(db: AsyncSession, item: StudentProgressionItem) -> StudentProgressionItem:
        db.add(item)
        await db.flush()
        return item

    @staticmethod
    async def add_many(
        db: AsyncSession,
        items: list[StudentProgressionItem],
    ) -> list[StudentProgressionItem]:
        if not items:
            return []
        db.add_all(items)
        await db.flush()
        return items

    @staticmethod
    async def get_by_run_and_student(
        db: AsyncSession,
        run_id: UUID,
        student_id: UUID,
        *,
        lock: bool = False,
    ) -> StudentProgressionItem | None:
        query = select(StudentProgressionItem).where(
            StudentProgressionItem.progression_run_id == run_id,
            StudentProgressionItem.student_id == student_id,
        )
        if lock:
            query = query.with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_run(
        db: AsyncSession,
        tenant_id: UUID,
        run_id: UUID,
    ) -> list[StudentProgressionItem]:
        result = await db.execute(
            select(StudentProgressionItem)
            .where(
                StudentProgressionItem.tenant_id == tenant_id,
                StudentProgressionItem.progression_run_id == run_id,
            )
            .order_by(StudentProgressionItem.student_id.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def save(db: AsyncSession, item: StudentProgressionItem) -> StudentProgressionItem:
        db.add(item)
        await db.flush()
        return item


class StudentProgressionRepository:
    """Canonical facade used by the progression service.

    Run and item persistence remain separated internally, while the service gets
    one stable contract and does not depend on implementation class names.
    """

    add_run = StudentProgressionRunRepository.add
    save_run = StudentProgressionRunRepository.save
    get_run_by_id = StudentProgressionRunRepository.get_by_id
    get_run_by_session = StudentProgressionRunRepository.get_by_session
    get_run_by_idempotency_key = StudentProgressionRunRepository.get_by_idempotency_key
    list_runs_for_tenant = StudentProgressionRunRepository.list_for_tenant

    add_item = StudentProgressionItemRepository.add
    add_items = StudentProgressionItemRepository.add_many
    get_item_by_run_and_student = StudentProgressionItemRepository.get_by_run_and_student
    list_items_for_run = StudentProgressionItemRepository.list_for_run
    save_item = StudentProgressionItemRepository.save
