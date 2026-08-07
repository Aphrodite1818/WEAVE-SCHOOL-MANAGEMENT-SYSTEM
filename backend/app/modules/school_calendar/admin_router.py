"""Tenant-admin school calendar routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarEventAudience,
    SchoolCalendarEventStatus,
    SchoolCalendarStatus,
)
from app.modules.school_calendar.generation_service import (
    SchoolCalendarGenerationService,
)
from app.modules.school_calendar.schemas import (
    SchoolCalendarActivationRequest,
    SchoolCalendarArchiveRequest,
    SchoolCalendarConfigurationCreate,
    SchoolCalendarConfigurationResponse,
    SchoolCalendarConfigurationUpdate,
    SchoolCalendarDateRangeUpdate,
    SchoolCalendarDayResponse,
    SchoolCalendarDayUpdate,
    SchoolCalendarDependencyPreview,
    SchoolCalendarEmergencyClosureRequest,
    SchoolCalendarEventCancelRequest,
    SchoolCalendarEventCreate,
    SchoolCalendarEventListResponse,
    SchoolCalendarEventPublishRequest,
    SchoolCalendarEventResponse,
    SchoolCalendarEventUpdate,
    SchoolCalendarGenerateRequest,
    SchoolCalendarGenerateResponse,
    SchoolCalendarListResponse,
    SchoolCalendarRangeResponse,
    SchoolCalendarResponse,
)
from app.modules.school_calendar.service import SchoolCalendarService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/school-calendar", tags=["Tenant Admin School Calendar"]
)

CurrentTenantAdmin: TypeAlias = Annotated[
    TenantAdmin, Depends(get_current_tenant_admin)
]


async def _ensure_academic_setup(db: DbSession, tenant_id: UUID) -> None:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db, tenant_id, FeatureCode.ACADEMIC_SETUP
    )


@router.get("/configuration", response_model=SchoolCalendarConfigurationResponse)
async def get_configuration(
    db: DbSession, current_admin: CurrentTenantAdmin
) -> SchoolCalendarConfigurationResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.get_configuration(db, current_admin.tenant_id)


@router.post(
    "/configuration",
    response_model=SchoolCalendarConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_configuration(
    payload: SchoolCalendarConfigurationCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarConfigurationResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.get_or_create_configuration(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.put("/configuration", response_model=SchoolCalendarConfigurationResponse)
async def update_configuration(
    payload: SchoolCalendarConfigurationUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarConfigurationResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.upsert_configuration(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.post("/generate", response_model=SchoolCalendarGenerateResponse)
async def generate_calendar(
    payload: SchoolCalendarGenerateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarGenerateResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarGenerationService.generate(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.get("", response_model=SchoolCalendarListResponse)
async def list_calendars(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    academic_session_id: UUID | None = Query(default=None),
    status_filter: SchoolCalendarStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> SchoolCalendarListResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.list_calendars(
        db,
        current_admin.tenant_id,
        academic_session_id=academic_session_id,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get("/days", response_model=SchoolCalendarRangeResponse)
async def list_days(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    calendar_id: UUID = Query(),
    start_date: date = Query(),
    end_date: date = Query(),
) -> SchoolCalendarRangeResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.list_days(
        db,
        current_admin.tenant_id,
        calendar_id=calendar_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.patch("/days/{calendar_date}", response_model=SchoolCalendarDayResponse)
async def update_day(
    calendar_date: date,
    payload: SchoolCalendarDayUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarDayResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.update_day(
        db,
        tenant_id=current_admin.tenant_id,
        calendar_date=calendar_date,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.patch("/date-range", response_model=SchoolCalendarRangeResponse)
async def update_date_range(
    payload: SchoolCalendarDateRangeUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarRangeResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.update_date_range(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.post("/emergency-closure", response_model=SchoolCalendarRangeResponse)
async def emergency_closure(
    payload: SchoolCalendarEmergencyClosureRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarRangeResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.emergency_closure(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.post(
    "/events",
    response_model=SchoolCalendarEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_event(
    payload: SchoolCalendarEventCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarEventResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.create_event(
        db,
        tenant_id=current_admin.tenant_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.get("/events", response_model=SchoolCalendarEventListResponse)
async def list_events(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    calendar_id: UUID | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    status_filter: SchoolCalendarEventStatus | None = Query(
        default=None, alias="status"
    ),
    audience: SchoolCalendarEventAudience | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> SchoolCalendarEventListResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.list_events(
        db,
        current_admin.tenant_id,
        calendar_id=calendar_id,
        start_date=start_date,
        end_date=end_date,
        status=status_filter,
        audience={audience} if audience is not None else None,
        skip=skip,
        limit=limit,
    )


@router.patch("/events/{event_id}", response_model=SchoolCalendarEventResponse)
async def update_event(
    event_id: UUID,
    payload: SchoolCalendarEventUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarEventResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.update_event(
        db,
        tenant_id=current_admin.tenant_id,
        event_id=event_id,
        payload=payload,
    )


@router.post("/events/{event_id}/publish", response_model=SchoolCalendarEventResponse)
async def publish_event(
    event_id: UUID,
    payload: SchoolCalendarEventPublishRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarEventResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.publish_event(
        db,
        tenant_id=current_admin.tenant_id,
        event_id=event_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.post("/events/{event_id}/cancel", response_model=SchoolCalendarEventResponse)
async def cancel_event(
    event_id: UUID,
    payload: SchoolCalendarEventCancelRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarEventResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.cancel_event(
        db,
        tenant_id=current_admin.tenant_id,
        event_id=event_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )


@router.get("/{calendar_id}", response_model=SchoolCalendarResponse)
async def get_calendar(
    calendar_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin
) -> SchoolCalendarResponse:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.get_calendar(
        db, current_admin.tenant_id, calendar_id
    )


@router.get(
    "/{calendar_id}/dependencies", response_model=SchoolCalendarDependencyPreview
)
async def calendar_dependencies(
    calendar_id: UUID, db: DbSession, current_admin: CurrentTenantAdmin
) -> SchoolCalendarDependencyPreview:
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.calendar_dependency_preview(
        db, current_admin.tenant_id, calendar_id
    )


@router.post("/{calendar_id}/activate", response_model=SchoolCalendarResponse)
async def activate_calendar(
    calendar_id: UUID,
    payload: SchoolCalendarActivationRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarResponse:
    _ = payload.confirmation
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.activate_calendar(
        db,
        tenant_id=current_admin.tenant_id,
        calendar_id=calendar_id,
        acting_admin_id=current_admin.id,
    )


@router.post("/{calendar_id}/archive", response_model=SchoolCalendarResponse)
async def archive_calendar(
    calendar_id: UUID,
    payload: SchoolCalendarArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> SchoolCalendarResponse:
    _ = payload.confirmation
    await _ensure_academic_setup(db, current_admin.tenant_id)
    return await SchoolCalendarService.archive_calendar(
        db,
        tenant_id=current_admin.tenant_id,
        calendar_id=calendar_id,
        payload=payload,
        acting_admin_id=current_admin.id,
    )
