"""Stable school-day policy API for future attendance workflows."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarEventAudience,
    SchoolCalendarEventStatus,
)
from app.modules.school_calendar.repository import SchoolCalendarRepository
from app.modules.school_calendar.schemas import (
    ResolvedSchoolDayResponse,
    SchoolCalendarEventResponse,
)


class SchoolDayPolicyService:
    async def resolve_day(
        self,
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        target_date: date,
        audience: set[SchoolCalendarEventAudience] | None = None,
    ) -> ResolvedSchoolDayResponse:
        next_day = await SchoolCalendarRepository.get_next_operational_day(
            db,
            tenant_id,
            after_date=target_date,
        )
        calendar = await SchoolCalendarRepository.get_active_calendar_for_date(
            db, tenant_id, target_date
        )
        if calendar is None:
            return ResolvedSchoolDayResponse(
                tenant_id=tenant_id,
                date=target_date,
                school_open=False,
                student_activity_allowed=False,
                student_attendance_required=False,
                workforce_attendance_required=False,
                reason="No active school calendar covers this date.",
                code="no_active_calendar",
                next_operational_day=next_day.calendar_date if next_day else None,
            )
        day = await SchoolCalendarRepository.get_day_by_date(
            db,
            tenant_id,
            calendar.id,
            target_date,
        )
        if day is None:
            return ResolvedSchoolDayResponse(
                tenant_id=tenant_id,
                date=target_date,
                calendar_id=calendar.id,
                academic_session_id=calendar.academic_session_id,
                academic_term_id=calendar.academic_term_id,
                calendar_status=calendar.status,
                reason="The active calendar is missing this date.",
                code="missing_calendar_day",
                next_operational_day=next_day.calendar_date if next_day else None,
            )
        events, _ = await SchoolCalendarRepository.list_events(
            db,
            tenant_id,
            start_date=target_date,
            end_date=target_date,
            status=None if audience is None else SchoolCalendarEventStatus.PUBLISHED,
            audience=audience,
            limit=50,
        )
        return ResolvedSchoolDayResponse(
            tenant_id=tenant_id,
            date=target_date,
            calendar_id=calendar.id,
            academic_session_id=calendar.academic_session_id,
            academic_term_id=calendar.academic_term_id,
            calendar_status=calendar.status,
            day_type=day.day_type,
            school_open=day.school_open,
            student_activity_allowed=day.student_activity_allowed,
            student_attendance_required=day.student_attendance_required,
            workforce_attendance_required=day.workforce_attendance_required,
            opens_at=day.opens_at,
            closes_at=day.closes_at,
            title=day.title,
            reason=None,
            code="ok",
            events=[SchoolCalendarEventResponse.model_validate(event) for event in events],
            next_operational_day=next_day.calendar_date if next_day else None,
        )

    async def require_school_open(
        self, db: AsyncSession, *, tenant_id: uuid.UUID, target_date: date
    ) -> ResolvedSchoolDayResponse:
        resolved = await self.resolve_day(db, tenant_id=tenant_id, target_date=target_date)
        if not resolved.school_open:
            raise ConflictException(
                resolved.reason or "School is not open on this date.",
                payload={"code": resolved.code},
            )
        return resolved

    async def require_student_activity_allowed(
        self, db: AsyncSession, *, tenant_id: uuid.UUID, target_date: date
    ) -> ResolvedSchoolDayResponse:
        resolved = await self.resolve_day(db, tenant_id=tenant_id, target_date=target_date)
        if not resolved.student_activity_allowed:
            raise ConflictException(
                resolved.reason or "Student activity is not allowed on this date.",
                payload={"code": resolved.code},
            )
        return resolved

    async def require_student_attendance_day(
        self, db: AsyncSession, *, tenant_id: uuid.UUID, target_date: date
    ) -> ResolvedSchoolDayResponse:
        resolved = await self.resolve_day(db, tenant_id=tenant_id, target_date=target_date)
        if not resolved.student_attendance_required:
            raise ConflictException(
                resolved.reason or "Student attendance is not required on this date.",
                payload={"code": resolved.code},
            )
        return resolved

    async def require_workforce_attendance_day(
        self, db: AsyncSession, *, tenant_id: uuid.UUID, target_date: date
    ) -> ResolvedSchoolDayResponse:
        resolved = await self.resolve_day(db, tenant_id=tenant_id, target_date=target_date)
        if not resolved.workforce_attendance_required:
            raise ConflictException(
                resolved.reason or "Workforce attendance is not required on this date.",
                payload={"code": resolved.code},
            )
        return resolved
