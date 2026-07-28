"""Pydantic contracts for the school calendar module."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarDaySource,
    SchoolCalendarDayType,
    SchoolCalendarEventAudience,
    SchoolCalendarEventStatus,
    SchoolCalendarEventType,
    SchoolCalendarStatus,
)


class CalendarInputBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=False)


class CalendarOutputBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True, populate_by_name=True)


def _validate_weekdays(values: list[int]) -> list[int]:
    if not values:
        raise ValueError("at least one instructional weekday is required")
    if len(set(values)) != len(values):
        raise ValueError("instructional weekdays cannot contain duplicates")
    if any(value < 0 or value > 6 for value in values):
        raise ValueError("instructional weekdays must be integers from 0 to 6")
    return sorted(values)


class SchoolCalendarConfigurationCreate(CalendarInputBase):
    timezone: str = Field(default="Africa/Lagos", min_length=3, max_length=80)
    instructional_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    default_open_time: time | None = None
    default_close_time: time | None = None
    default_student_attendance_required: bool = True
    default_workforce_attendance_required: bool = True

    @field_validator("instructional_weekdays")
    @classmethod
    def validate_weekdays(cls, values: list[int]) -> list[int]:
        return _validate_weekdays(values)

    @model_validator(mode="after")
    def validate_times(self):
        if self.default_open_time and self.default_close_time and self.default_close_time <= self.default_open_time:
            raise ValueError("default_close_time must be later than default_open_time")
        return self


class SchoolCalendarConfigurationUpdate(CalendarInputBase):
    timezone: str | None = Field(default=None, min_length=3, max_length=80)
    instructional_weekdays: list[int] | None = None
    default_open_time: time | None = None
    default_close_time: time | None = None
    default_student_attendance_required: bool | None = None
    default_workforce_attendance_required: bool | None = None

    @field_validator("instructional_weekdays")
    @classmethod
    def validate_weekdays(cls, values: list[int] | None) -> list[int] | None:
        return None if values is None else _validate_weekdays(values)

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one configuration field is required")
        if self.default_open_time and self.default_close_time and self.default_close_time <= self.default_open_time:
            raise ValueError("default_close_time must be later than default_open_time")
        return self


class SchoolCalendarConfigurationResponse(CalendarOutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    timezone: str
    instructional_weekdays: list[int]
    default_open_time: time | None
    default_close_time: time | None
    default_student_attendance_required: bool
    default_workforce_attendance_required: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class SchoolCalendarGenerateRequest(CalendarInputBase):
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    overwrite_generated_days: bool = False


class SchoolCalendarActivationRequest(CalendarInputBase):
    confirmation: Literal["ACTIVATE_SCHOOL_CALENDAR"]


class SchoolCalendarArchiveRequest(CalendarInputBase):
    confirmation: Literal["ARCHIVE_SCHOOL_CALENDAR"]
    reason: str | None = Field(default=None, min_length=3, max_length=500)
    force_replacement: bool = False


class SchoolCalendarDayUpdate(CalendarInputBase):
    calendar_id: uuid.UUID | None = None
    day_type: SchoolCalendarDayType | None = None
    title: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    school_open: bool | None = None
    student_activity_allowed: bool | None = None
    student_attendance_required: bool | None = None
    workforce_attendance_required: bool | None = None
    opens_at: time | None = None
    closes_at: time | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=500)
    historical_correction_confirmed: bool = False

    @model_validator(mode="after")
    def validate_day(self):
        if not self.model_fields_set:
            raise ValueError("at least one day field is required")
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be later than opens_at")
        if self.student_attendance_required is True and self.student_activity_allowed is False:
            raise ValueError("student attendance cannot be required when student activity is disallowed")
        if self.student_attendance_required is True and self.school_open is False:
            raise ValueError("student attendance cannot be required when school is closed")
        return self


class SchoolCalendarDateRangeUpdate(CalendarInputBase):
    start_date: date
    end_date: date
    day_type: SchoolCalendarDayType
    title: str | None = Field(default=None, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    school_open: bool
    student_activity_allowed: bool
    student_attendance_required: bool
    workforce_attendance_required: bool
    opens_at: time | None = None
    closes_at: time | None = None
    reason: str = Field(min_length=3, max_length=500)
    historical_correction_confirmed: bool = False

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            raise ValueError("closes_at must be later than opens_at")
        if self.student_attendance_required and not self.student_activity_allowed:
            raise ValueError("student attendance cannot be required when student activity is disallowed")
        if self.student_attendance_required and not self.school_open:
            raise ValueError("student attendance cannot be required when school is closed")
        return self


class SchoolCalendarEmergencyClosureRequest(CalendarInputBase):
    calendar_id: uuid.UUID | None = None
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class SchoolCalendarEventCreate(CalendarInputBase):
    calendar_id: uuid.UUID
    title: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    event_type: SchoolCalendarEventType = SchoolCalendarEventType.OTHER
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool = False
    audience: SchoolCalendarEventAudience = SchoolCalendarEventAudience.ALL
    location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_event(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class SchoolCalendarEventUpdate(CalendarInputBase):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    event_type: SchoolCalendarEventType | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_all_day: bool | None = None
    audience: SchoolCalendarEventAudience | None = None
    location: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_event_update(self):
        if not self.model_fields_set:
            raise ValueError("at least one event field is required")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class SchoolCalendarEventPublishRequest(CalendarInputBase):
    confirmation: Literal["PUBLISH_SCHOOL_CALENDAR_EVENT"]


class SchoolCalendarEventCancelRequest(CalendarInputBase):
    confirmation: Literal["CANCEL_SCHOOL_CALENDAR_EVENT"]
    reason: str = Field(min_length=3, max_length=500)


class SchoolCalendarDayResponse(CalendarOutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    calendar_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    calendar_date: date
    day_type: SchoolCalendarDayType
    title: str | None
    description: str | None
    school_open: bool
    student_activity_allowed: bool
    student_attendance_required: bool
    workforce_attendance_required: bool
    opens_at: time | None
    closes_at: time | None
    source: SchoolCalendarDaySource
    is_manual_override: bool
    created_by_admin_id: uuid.UUID | None
    updated_by_admin_id: uuid.UUID | None
    can_edit: bool = False
    requires_historical_correction: bool = False
    requires_reason: bool = False
    created_at: datetime
    updated_at: datetime


class SchoolCalendarResponse(CalendarOutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    status: SchoolCalendarStatus
    generated_at: datetime | None
    generated_from_configuration_revision: int | None = None
    activated_at: datetime | None
    activated_by_admin_id: uuid.UUID | None
    archived_at: datetime | None
    archived_by_admin_id: uuid.UUID | None
    can_activate: bool = False
    can_archive: bool = False
    can_edit: bool = False
    can_regenerate: bool = False
    blocker_messages: list[str] = []
    blocker_codes: list[str] = []
    missing_dates: int = 0
    extra_dates: int = 0
    duplicate_dates: int = 0
    invalid_days: int = 0
    configuration_outdated: bool = False
    dependency_counts: dict[str, int] = {}
    created_at: datetime
    updated_at: datetime


class SchoolCalendarListResponse(CalendarOutputBase):
    items: list[SchoolCalendarResponse]
    total: int


class SchoolCalendarDependencyPreview(CalendarOutputBase):
    calendar_id: uuid.UUID
    dependency_counts: dict[str, int]
    blocker_messages: list[str] = []
    blocker_codes: list[str] = []
    can_activate: bool
    can_archive: bool
    can_edit: bool
    can_regenerate: bool
    missing_dates: int = 0
    extra_dates: int = 0
    duplicate_dates: int = 0
    invalid_days: int = 0
    configuration_outdated: bool = False


class SchoolCalendarGeneratePreview(CalendarOutputBase):
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    can_generate: bool
    blocker_messages: list[str] = []
    warning_messages: list[str] = []


class SchoolCalendarGenerateResponse(CalendarOutputBase):
    calendar: SchoolCalendarResponse
    total_days: int
    instructional_days: int
    weekend_days: int
    manual_days_preserved: int
    generated_days_created: int
    generated_days_updated: int
    warnings: list[str] = []


class SchoolCalendarRangeResponse(CalendarOutputBase):
    items: list[SchoolCalendarDayResponse]
    total: int


class ResolvedSchoolDayResponse(CalendarOutputBase):
    tenant_id: uuid.UUID
    date: date
    calendar_id: uuid.UUID | None = None
    academic_session_id: uuid.UUID | None = None
    academic_term_id: uuid.UUID | None = None
    calendar_status: SchoolCalendarStatus | None = None
    day_type: SchoolCalendarDayType | None = None
    school_open: bool = False
    student_activity_allowed: bool = False
    student_attendance_required: bool = False
    workforce_attendance_required: bool = False
    opens_at: time | None = None
    closes_at: time | None = None
    title: str | None = None
    reason: str | None = None
    code: str
    events: list[SchoolCalendarEventResponse] = []
    next_operational_day: date | None = None


class SchoolCalendarEventResponse(CalendarOutputBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    calendar_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID
    title: str
    description: str | None
    event_type: SchoolCalendarEventType
    starts_at: datetime
    ends_at: datetime
    is_all_day: bool
    audience: SchoolCalendarEventAudience
    location: str | None
    status: SchoolCalendarEventStatus
    created_by_admin_id: uuid.UUID | None
    published_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SchoolCalendarEventListResponse(CalendarOutputBase):
    items: list[SchoolCalendarEventResponse]
    total: int


class SchoolCalendarUpcomingResponse(CalendarOutputBase):
    days: list[SchoolCalendarDayResponse] = []
    events: list[SchoolCalendarEventResponse] = []
    total_days: int
    total_events: int
