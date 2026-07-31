"""Read-only school calendar routes for tenant actors."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import TenantActor, get_current_tenant_member
from app.modules.parents.models import Parent
from app.modules.school_calendar.calendar_enums import SchoolCalendarEventAudience
from app.modules.school_calendar.policy_service import SchoolDayPolicyService
from app.modules.school_calendar.schemas import (
    ResolvedSchoolDayResponse,
    SchoolCalendarEventListResponse,
    SchoolCalendarRangeResponse,
    SchoolCalendarUpcomingResponse,
)
from app.modules.school_calendar.service import SchoolCalendarService
from app.modules.students.models import Student
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/school-calendar", tags=["School Calendar"])
CurrentTenantMember: TypeAlias = Annotated[TenantActor, Depends(get_current_tenant_member)]


def _audiences_for(actor: TenantActor) -> set[SchoolCalendarEventAudience]:
    if isinstance(actor, TenantAdmin):
        return {SchoolCalendarEventAudience.ALL, SchoolCalendarEventAudience.TENANT_ADMINS}
    if isinstance(actor, Teacher):
        return {SchoolCalendarEventAudience.ALL, SchoolCalendarEventAudience.TEACHERS}
    if isinstance(actor, Parent):
        return {SchoolCalendarEventAudience.ALL, SchoolCalendarEventAudience.PARENTS}
    if isinstance(actor, Student):
        return {SchoolCalendarEventAudience.ALL, SchoolCalendarEventAudience.STUDENTS}
    return {SchoolCalendarEventAudience.ALL}


async def _ensure_academic_setup(db: DbSession, tenant_id: UUID) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(db, tenant_id, FeatureCode.ACADEMIC_SETUP)


@router.get("/today", response_model=ResolvedSchoolDayResponse)
async def today(
    db: DbSession,
    current_actor: CurrentTenantMember,
    target_date: date | None = Query(default=None, alias="date"),
) -> ResolvedSchoolDayResponse:
    await _ensure_academic_setup(db, current_actor.tenant_id)
    service = SchoolDayPolicyService()
    resolved_date = target_date or await SchoolCalendarService.tenant_today(db, current_actor.tenant_id)
    return await service.resolve_day(
        db,
        tenant_id=current_actor.tenant_id,
        target_date=resolved_date,
        audience=_audiences_for(current_actor),
    )


@router.get("/range", response_model=SchoolCalendarRangeResponse)
async def range_days(
    db: DbSession,
    current_actor: CurrentTenantMember,
    calendar_id: UUID | None = Query(default=None),
    start_date: date = Query(),
    end_date: date = Query(),
) -> SchoolCalendarRangeResponse:
    await _ensure_academic_setup(db, current_actor.tenant_id)
    return await SchoolCalendarService.list_days(
        db,
        current_actor.tenant_id,
        calendar_id=calendar_id,
        start_date=start_date,
        end_date=end_date,
        active_only=True,
    )


@router.get("/events", response_model=SchoolCalendarEventListResponse)
async def events(
    db: DbSession,
    current_actor: CurrentTenantMember,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> SchoolCalendarEventListResponse:
    await _ensure_academic_setup(db, current_actor.tenant_id)
    return await SchoolCalendarService.list_events(
        db,
        current_actor.tenant_id,
        start_date=start_date,
        end_date=end_date,
        audience=_audiences_for(current_actor),
        actor_facing=True,
        skip=skip,
        limit=limit,
    )


@router.get("/upcoming", response_model=SchoolCalendarUpcomingResponse)
async def upcoming(
    db: DbSession,
    current_actor: CurrentTenantMember,
    start_date: date | None = Query(default=None),
    days: int = Query(default=30, ge=1, le=120),
    limit: int = Query(default=10, ge=1, le=50),
) -> SchoolCalendarUpcomingResponse:
    await _ensure_academic_setup(db, current_actor.tenant_id)
    resolved_start = start_date or await SchoolCalendarService.tenant_today(db, current_actor.tenant_id)
    return await SchoolCalendarService.upcoming(
        db,
        current_actor.tenant_id,
        start_date=resolved_start,
        end_date=resolved_start + timedelta(days=days),
        audience=_audiences_for(current_actor),
        limit=limit,
    )
