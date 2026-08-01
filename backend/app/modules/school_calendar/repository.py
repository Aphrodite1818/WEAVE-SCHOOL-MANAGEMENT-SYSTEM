"""Persistence helpers for school calendars."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarDaySource,
    SchoolCalendarDayType,
    SchoolCalendarEventAudience,
    SchoolCalendarEventStatus,
    SchoolCalendarStatus,
)
from app.modules.school_calendar.models import (
    SchoolCalendar,
    SchoolCalendarConfiguration,
    SchoolCalendarDay,
    SchoolCalendarEvent,
    SchoolCalendarLifecycleAudit,
)


class SchoolCalendarRepository:
    @staticmethod
    async def _save(db: AsyncSession, entity):
        db.add(entity)
        await db.flush()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def get_configuration(db: AsyncSession, tenant_id: uuid.UUID) -> SchoolCalendarConfiguration | None:
        return (
            await db.execute(
                select(SchoolCalendarConfiguration).where(
                    SchoolCalendarConfiguration.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def create_configuration(db: AsyncSession, config: SchoolCalendarConfiguration) -> SchoolCalendarConfiguration:
        return await SchoolCalendarRepository._save(db, config)

    @staticmethod
    async def update_configuration(db: AsyncSession, config: SchoolCalendarConfiguration) -> SchoolCalendarConfiguration:
        return await SchoolCalendarRepository._save(db, config)

    @staticmethod
    async def get_calendar_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        calendar_id: uuid.UUID,
    ) -> SchoolCalendar | None:
        return (
            await db.execute(
                select(SchoolCalendar).where(
                    SchoolCalendar.tenant_id == tenant_id,
                    SchoolCalendar.id == calendar_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_calendar_by_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> SchoolCalendar | None:
        return (
            await db.execute(
                select(SchoolCalendar).where(
                    SchoolCalendar.tenant_id == tenant_id,
                    SchoolCalendar.academic_term_id == term_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_calendars(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        status: SchoolCalendarStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[SchoolCalendar], int]:
        filters = [SchoolCalendar.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(SchoolCalendar.academic_session_id == academic_session_id)
        if status is not None:
            filters.append(SchoolCalendar.status == status)
        total = (
            await db.execute(select(func.count()).select_from(SchoolCalendar).where(*filters))
        ).scalar_one()
        rows = (
            await db.execute(
                select(SchoolCalendar)
                .where(*filters)
                .order_by(SchoolCalendar.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def get_active_calendar_for_date(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        target_date: date,
    ) -> SchoolCalendar | None:
        return (
            await db.execute(
                select(SchoolCalendar)
                .join(SchoolCalendarDay, SchoolCalendarDay.calendar_id == SchoolCalendar.id)
                .where(
                    SchoolCalendar.tenant_id == tenant_id,
                    SchoolCalendar.status == SchoolCalendarStatus.ACTIVE,
                    SchoolCalendarDay.tenant_id == tenant_id,
                    SchoolCalendarDay.calendar_date == target_date,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def lock_calendar(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        calendar_id: uuid.UUID,
    ) -> SchoolCalendar | None:
        return (
            await db.execute(
                select(SchoolCalendar)
                .where(SchoolCalendar.tenant_id == tenant_id, SchoolCalendar.id == calendar_id)
                .with_for_update()
            )
        ).scalar_one_or_none()

    @staticmethod
    async def save_calendar(db: AsyncSession, calendar: SchoolCalendar) -> SchoolCalendar:
        return await SchoolCalendarRepository._save(db, calendar)

    @staticmethod
    async def bulk_insert_days(db: AsyncSession, days: list[SchoolCalendarDay]) -> list[SchoolCalendarDay]:
        db.add_all(days)
        await db.flush()
        return days

    @staticmethod
    async def get_day_by_date(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        calendar_id: uuid.UUID,
        calendar_date: date,
        *,
        lock: bool = False,
    ) -> SchoolCalendarDay | None:
        query = select(SchoolCalendarDay).where(
            SchoolCalendarDay.tenant_id == tenant_id,
            SchoolCalendarDay.calendar_id == calendar_id,
            SchoolCalendarDay.calendar_date == calendar_date,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_days_by_range(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        calendar_id: uuid.UUID | None = None,
        start_date: date,
        end_date: date,
        active_only: bool = False,
        lock: bool = False,
    ) -> list[SchoolCalendarDay]:
        filters = [
            SchoolCalendarDay.tenant_id == tenant_id,
            SchoolCalendarDay.calendar_date >= start_date,
            SchoolCalendarDay.calendar_date <= end_date,
        ]
        if calendar_id is not None:
            filters.append(SchoolCalendarDay.calendar_id == calendar_id)
        query = select(SchoolCalendarDay)
        if active_only:
            query = query.join(SchoolCalendar, SchoolCalendar.id == SchoolCalendarDay.calendar_id)
            filters.extend(
                [
                    SchoolCalendar.tenant_id == tenant_id,
                    SchoolCalendar.status == SchoolCalendarStatus.ACTIVE,
                ]
            )
        query = query.where(*filters).order_by(SchoolCalendarDay.calendar_date.asc())
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def get_next_operational_day(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        after_date: date,
    ) -> SchoolCalendarDay | None:
        return (
            await db.execute(
                select(SchoolCalendarDay)
                .join(SchoolCalendar, SchoolCalendar.id == SchoolCalendarDay.calendar_id)
                .where(
                    SchoolCalendarDay.tenant_id == tenant_id,
                    SchoolCalendar.tenant_id == tenant_id,
                    SchoolCalendar.status == SchoolCalendarStatus.ACTIVE,
                    SchoolCalendarDay.calendar_date > after_date,
                    SchoolCalendarDay.school_open.is_(True),
                )
                .order_by(SchoolCalendarDay.calendar_date.asc())
                .limit(1)
            )
        ).scalar_one_or_none()

    @staticmethod
    async def count_days(db: AsyncSession, tenant_id: uuid.UUID, calendar_id: uuid.UUID) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(SchoolCalendarDay).where(
                        SchoolCalendarDay.tenant_id == tenant_id,
                        SchoolCalendarDay.calendar_id == calendar_id,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_unresolved_days(db: AsyncSession, tenant_id: uuid.UUID, calendar_id: uuid.UUID) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(SchoolCalendarDay).where(
                        SchoolCalendarDay.tenant_id == tenant_id,
                        SchoolCalendarDay.calendar_id == calendar_id,
                        SchoolCalendarDay.day_type.is_(None),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_missing_dates(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        calendar_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
    ) -> int:
        expected = (end_date - start_date).days + 1
        existing = int(
            (
                await db.execute(
                    select(func.count(func.distinct(SchoolCalendarDay.calendar_date))).where(
                        SchoolCalendarDay.tenant_id == tenant_id,
                        SchoolCalendarDay.calendar_id == calendar_id,
                        SchoolCalendarDay.calendar_date >= start_date,
                        SchoolCalendarDay.calendar_date <= end_date,
                    )
                )
            ).scalar_one()
        )
        return max(expected - existing, 0)

    @staticmethod
    async def count_extra_dates(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        calendar_id: uuid.UUID,
        *,
        start_date: date,
        end_date: date,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(SchoolCalendarDay).where(
                        SchoolCalendarDay.tenant_id == tenant_id,
                        SchoolCalendarDay.calendar_id == calendar_id,
                        (
                            (SchoolCalendarDay.calendar_date < start_date)
                            | (SchoolCalendarDay.calendar_date > end_date)
                        ),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_duplicate_dates(db: AsyncSession, tenant_id: uuid.UUID, calendar_id: uuid.UUID) -> int:
        duplicate_groups = (
            select(SchoolCalendarDay.calendar_date)
            .where(
                SchoolCalendarDay.tenant_id == tenant_id,
                SchoolCalendarDay.calendar_id == calendar_id,
            )
            .group_by(SchoolCalendarDay.calendar_date)
            .having(func.count(SchoolCalendarDay.id) > 1)
            .subquery()
        )
        return int((await db.execute(select(func.count()).select_from(duplicate_groups))).scalar_one())

    @staticmethod
    async def count_invalid_days(db: AsyncSession, tenant_id: uuid.UUID, calendar_id: uuid.UUID) -> int:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(SchoolCalendarDay).where(
                        SchoolCalendarDay.tenant_id == tenant_id,
                        SchoolCalendarDay.calendar_id == calendar_id,
                        (
                            (SchoolCalendarDay.school_open.is_(True) & (SchoolCalendarDay.opens_at.is_(None) | SchoolCalendarDay.closes_at.is_(None)))
                            | (SchoolCalendarDay.school_open.is_(True) & (SchoolCalendarDay.closes_at <= SchoolCalendarDay.opens_at))
                            | (SchoolCalendarDay.student_attendance_required.is_(True) & SchoolCalendarDay.student_activity_allowed.is_(False))
                            | (SchoolCalendarDay.student_attendance_required.is_(True) & SchoolCalendarDay.school_open.is_(False))
                        ),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def update_day(db: AsyncSession, day: SchoolCalendarDay) -> SchoolCalendarDay:
        return await SchoolCalendarRepository._save(db, day)

    @staticmethod
    async def bulk_update_date_range(db: AsyncSession, days: list[SchoolCalendarDay]) -> list[SchoolCalendarDay]:
        db.add_all(days)
        await db.flush()
        return days

    @staticmethod
    async def delete_generated_draft_days(db: AsyncSession, tenant_id: uuid.UUID, calendar_id: uuid.UUID) -> int:
        result = await db.execute(
            delete(SchoolCalendarDay).where(
                SchoolCalendarDay.tenant_id == tenant_id,
                SchoolCalendarDay.calendar_id == calendar_id,
                SchoolCalendarDay.source == SchoolCalendarDaySource.GENERATED,
                SchoolCalendarDay.is_manual_override.is_(False),
            )
        )
        await db.flush()
        return int(result.rowcount or 0)

    @staticmethod
    async def create_event(db: AsyncSession, event: SchoolCalendarEvent) -> SchoolCalendarEvent:
        return await SchoolCalendarRepository._save(db, event)

    @staticmethod
    async def get_event_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        event_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> SchoolCalendarEvent | None:
        query = select(SchoolCalendarEvent).where(
            SchoolCalendarEvent.tenant_id == tenant_id,
            SchoolCalendarEvent.id == event_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_events(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        calendar_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: SchoolCalendarEventStatus | None = None,
        audience: set[SchoolCalendarEventAudience] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[SchoolCalendarEvent], int]:
        filters = [SchoolCalendarEvent.tenant_id == tenant_id]
        if calendar_id is not None:
            filters.append(SchoolCalendarEvent.calendar_id == calendar_id)
        if start_date is not None:
            filters.append(func.date(SchoolCalendarEvent.ends_at) >= start_date)
        if end_date is not None:
            filters.append(func.date(SchoolCalendarEvent.starts_at) <= end_date)
        if status is not None:
            filters.append(SchoolCalendarEvent.status == status)
        if audience:
            filters.append(SchoolCalendarEvent.audience.in_(audience))
        total = (
            await db.execute(select(func.count()).select_from(SchoolCalendarEvent).where(*filters))
        ).scalar_one()
        rows = (
            await db.execute(
                select(SchoolCalendarEvent)
                .where(*filters)
                .order_by(SchoolCalendarEvent.starts_at.asc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def update_event(db: AsyncSession, event: SchoolCalendarEvent) -> SchoolCalendarEvent:
        return await SchoolCalendarRepository._save(db, event)

    @staticmethod
    async def add_audit(db: AsyncSession, audit: SchoolCalendarLifecycleAudit) -> SchoolCalendarLifecycleAudit:
        db.add(audit)
        await db.flush()
        return audit
