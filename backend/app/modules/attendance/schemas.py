"""Pydantic contracts for attendance and geofencing APIs."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.attendance.attendance_enums import (
    AttendanceCorrectionStatus,
    AttendanceCorrectionTarget,
    AttendanceNotificationChannel,
    AttendanceNotificationStatus,
    GeofenceDecision,
    SchoolGeofenceStatus,
    StudentAttendanceSheetStatus,
    StudentAttendanceStatus,
    TemporaryAssignmentStatus,
    WorkforceAttendanceStatus,
)


class InputBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        use_enum_values=False,
        validate_assignment=True,
    )


class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        populate_by_name=True,
    )


class AttendanceSettingsUpdate(InputBase):
    timezone: str | None = Field(default=None, min_length=1, max_length=80)
    student_marking_opens_at: time | None = None
    student_marking_closes_at: time | None = None
    workforce_check_in_opens_at: time | None = None
    workforce_check_in_closes_at: time | None = None
    workforce_check_out_opens_at: time | None = None
    workforce_check_out_closes_at: time | None = None
    late_after_time: time | None = None
    require_geofence_for_workforce: bool | None = None
    geofence_accuracy_threshold_m: int | None = Field(default=None, gt=0, le=5000)
    geofence_tolerance_m: int | None = Field(default=None, ge=0, le=1000)
    location_raw_retention_days: int | None = Field(default=None, ge=0, le=90)
    location_evidence_retention_days: int | None = Field(default=None, ge=30, le=2555)
    require_student_sheet_submission: bool | None = None
    notify_absent_parents: bool | None = None
    notify_absent_staff: bool | None = None

    @model_validator(mode="after")
    def validate_windows(self) -> "AttendanceSettingsUpdate":
        pairs = (
            ("student_marking_opens_at", "student_marking_closes_at"),
            ("workforce_check_in_opens_at", "workforce_check_in_closes_at"),
            ("workforce_check_out_opens_at", "workforce_check_out_closes_at"),
        )
        for start_name, end_name in pairs:
            start = getattr(self, start_name)
            end = getattr(self, end_name)
            if start is not None and end is not None and end <= start:
                raise ValueError(f"{end_name} must be after {start_name}")
        return self


class AttendanceSettingsResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    status: str
    timezone: str
    student_marking_opens_at: time | None
    student_marking_closes_at: time | None
    workforce_check_in_opens_at: time | None
    workforce_check_in_closes_at: time | None
    workforce_check_out_opens_at: time | None
    workforce_check_out_closes_at: time | None
    late_after_time: time | None
    require_geofence_for_workforce: bool
    geofence_accuracy_threshold_m: int
    geofence_tolerance_m: int
    location_raw_retention_days: int
    location_evidence_retention_days: int
    require_student_sheet_submission: bool
    notify_absent_parents: bool
    notify_absent_staff: bool
    configuration_revision: int
    created_at: datetime
    updated_at: datetime


class LocationSample(InputBase):
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"), decimal_places=6)
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"), decimal_places=6)
    accuracy_m: int = Field(gt=0, le=10000)
    provided_at: datetime | None = None
    device_context: dict[str, Any] | None = None


class SchoolGeofenceCreate(InputBase):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"), decimal_places=6)
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"), decimal_places=6)
    radius_m: int = Field(gt=0, le=10000)
    is_primary: bool = False


class SchoolGeofenceUpdate(InputBase):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    latitude: Decimal | None = Field(default=None, ge=Decimal("-90"), le=Decimal("90"), decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=Decimal("-180"), le=Decimal("180"), decimal_places=6)
    radius_m: int | None = Field(default=None, gt=0, le=10000)
    is_primary: bool | None = None


class SchoolGeofenceResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    latitude: Decimal
    longitude: Decimal
    radius_m: int
    status: str
    is_primary: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SchoolGeofenceListResponse(OutputBase):
    items: list[SchoolGeofenceResponse]
    total: int


class GeofencePreviewRequest(InputBase):
    geofence_id: UUID | None = None
    location: LocationSample
    purpose: str = Field(default="preview", max_length=80)


class GeofenceEvaluationResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    geofence_id: UUID | None
    actor_type: str
    actor_id: UUID
    purpose: str
    decision: str
    distance_m: int | None
    accuracy_m: int | None
    tolerance_m: int
    provided_at: datetime | None
    raw_location_expires_at: datetime | None
    evidence_expires_at: datetime | None
    reason: str | None
    created_at: datetime


class StudentAttendanceRecordMark(InputBase):
    student_id: UUID
    status: StudentAttendanceStatus
    reason: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=2000)


class StudentAttendanceSheetOpenRequest(InputBase):
    class_id: UUID
    attendance_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class StudentAttendanceBulkMarkRequest(InputBase):
    records: list[StudentAttendanceRecordMark] = Field(min_length=1, max_length=300)

    @field_validator("records")
    @classmethod
    def unique_students(cls, value: list[StudentAttendanceRecordMark]) -> list[StudentAttendanceRecordMark]:
        ids = [item.student_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("records cannot contain duplicate student_id values")
        return value


class StudentAttendanceSheetSubmitRequest(InputBase):
    notes: str | None = Field(default=None, max_length=2000)


class StudentAttendanceRecordResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    sheet_id: UUID
    student_id: UUID
    student_enrollment_id: UUID | None
    status: str
    marked_at: datetime | None
    marked_by_actor_type: str | None
    marked_by_actor_id: UUID | None
    reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class StudentAttendanceSheetResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    class_id: UUID
    attendance_date: date
    academic_session_id: UUID
    academic_term_id: UUID | None
    calendar_id: UUID | None
    status: str
    submitted_at: datetime | None
    approved_at: datetime | None
    locked_at: datetime | None
    cancelled_at: datetime | None
    notes: str | None
    records: list[StudentAttendanceRecordResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class StudentAttendanceSheetListResponse(OutputBase):
    items: list[StudentAttendanceSheetResponse]
    total: int


class StudentAttendanceRecordListResponse(OutputBase):
    items: list[StudentAttendanceRecordResponse]
    total: int


class WorkforceCheckInRequest(InputBase):
    attendance_date: date | None = None
    location: LocationSample | None = None
    notes: str | None = Field(default=None, max_length=2000)


class WorkforceCheckOutRequest(InputBase):
    attendance_date: date | None = None
    location: LocationSample | None = None
    notes: str | None = Field(default=None, max_length=2000)


class WorkforceAttendanceResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    teacher_membership_id: UUID
    attendance_date: date
    academic_session_id: UUID | None
    academic_term_id: UUID | None
    calendar_id: UUID | None
    status: str
    check_in_at: datetime | None
    check_out_at: datetime | None
    check_in_geofence_evaluation_id: UUID | None
    check_out_geofence_evaluation_id: UUID | None
    check_in_notes: str | None
    check_out_notes: str | None
    corrected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkforceAttendanceListResponse(OutputBase):
    items: list[WorkforceAttendanceResponse]
    total: int


class TemporaryAttendanceAssignmentCreate(InputBase):
    class_id: UUID
    teacher_membership_id: UUID
    starts_on: date
    ends_on: date
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_dates(self) -> "TemporaryAttendanceAssignmentCreate":
        if self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class TemporaryAttendanceAssignmentResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    class_id: UUID
    teacher_membership_id: UUID
    starts_on: date
    ends_on: date
    status: str
    reason: str | None
    created_at: datetime
    updated_at: datetime


class AttendanceCorrectionCreate(InputBase):
    target_type: AttendanceCorrectionTarget
    target_id: UUID
    reason: str = Field(min_length=3, max_length=2000)
    requested_state: dict[str, Any]


class AttendanceCorrectionReview(InputBase):
    approved: bool
    admin_note: str | None = Field(default=None, max_length=2000)


class AttendanceCorrectionResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    target_type: str
    target_id: UUID
    status: str
    requested_by_actor_type: str
    requested_by_actor_id: UUID
    reviewed_by_admin_id: UUID | None
    reviewed_at: datetime | None
    reason: str
    admin_note: str | None
    previous_state: dict[str, Any] | None
    requested_state: dict[str, Any]
    applied_state: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AttendanceCorrectionListResponse(OutputBase):
    items: list[AttendanceCorrectionResponse]
    total: int


class AttendanceAnalyticsResponse(OutputBase):
    start_date: date
    end_date: date
    student_totals: dict[str, int]
    workforce_totals: dict[str, int]
    student_attendance_rate: float | None
    workforce_check_in_rate: float | None


class AttendanceReadinessResponse(OutputBase):
    ready: bool
    blockers: list[str]
    warnings: list[str]
    counts: dict[str, int]


class AttendanceNotificationResponse(OutputBase):
    id: UUID
    tenant_id: UUID
    notification_key: str
    channel: AttendanceNotificationChannel
    status: AttendanceNotificationStatus
    recipient_actor_id: UUID | None
    recipient_email: str | None
    subject: str | None
    payload: dict[str, Any]
    scheduled_for: datetime | None
    sent_at: datetime | None
    failure_reason: str | None
