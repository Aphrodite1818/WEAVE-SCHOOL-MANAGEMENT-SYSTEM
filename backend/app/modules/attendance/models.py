"""Attendance, workforce time, and geofencing persistence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.attendance.attendance_enums import (
    AttendanceActorType,
    AttendanceCorrectionStatus,
    AttendanceCorrectionTarget,
    AttendanceNotificationChannel,
    AttendanceNotificationStatus,
    AttendanceSettingsStatus,
    GeofenceDecision,
    SchoolGeofenceStatus,
    StudentAttendanceSheetStatus,
    StudentAttendanceStatus,
    TemporaryAssignmentStatus,
    WorkforceAttendanceStatus,
    enum_values,
)
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


def _enum(enum_cls, name: str) -> SQLEnum:
    return SQLEnum(
        enum_cls,
        name=name,
        schema=PUBLIC_SCHEMA,
        values_callable=enum_values,
    )


class AttendanceSettings(BaseModel):
    """Tenant attendance defaults and privacy controls."""

    __tablename__ = "attendance_settings"

    status: Mapped[AttendanceSettingsStatus] = mapped_column(
        _enum(AttendanceSettingsStatus, "attendance_settings_status"),
        nullable=False,
        default=AttendanceSettingsStatus.ACTIVE,
        server_default=AttendanceSettingsStatus.ACTIVE.value,
    )
    timezone: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="Africa/Lagos"
    )
    student_marking_opens_at: Mapped[time | None] = mapped_column(Time(), nullable=True)
    student_marking_closes_at: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    workforce_check_in_opens_at: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    workforce_check_in_closes_at: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    workforce_check_out_opens_at: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    workforce_check_out_closes_at: Mapped[time | None] = mapped_column(
        Time(), nullable=True
    )
    late_after_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    require_geofence_for_workforce: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    geofence_accuracy_threshold_m: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    geofence_tolerance_m: Mapped[int] = mapped_column(
        Integer, nullable=False, default=25, server_default="25"
    )
    location_raw_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=7, server_default="7"
    )
    location_evidence_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=365, server_default="365"
    )
    require_student_sheet_submission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notify_absent_parents: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    notify_absent_staff: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    configuration_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_attendance_settings_tenant"),
        CheckConstraint(
            "student_marking_opens_at IS NULL OR student_marking_closes_at IS NULL OR student_marking_closes_at > student_marking_opens_at",
            name="ck_attendance_settings_student_window",
        ),
        CheckConstraint(
            "workforce_check_in_opens_at IS NULL OR workforce_check_in_closes_at IS NULL OR workforce_check_in_closes_at > workforce_check_in_opens_at",
            name="ck_attendance_settings_workforce_in_window",
        ),
        CheckConstraint(
            "workforce_check_out_opens_at IS NULL OR workforce_check_out_closes_at IS NULL OR workforce_check_out_closes_at > workforce_check_out_opens_at",
            name="ck_attendance_settings_workforce_out_window",
        ),
        CheckConstraint(
            "geofence_accuracy_threshold_m > 0",
            name="ck_attendance_settings_accuracy_positive",
        ),
        CheckConstraint(
            "geofence_tolerance_m >= 0",
            name="ck_attendance_settings_tolerance_nonnegative",
        ),
        CheckConstraint(
            "location_raw_retention_days BETWEEN 0 AND 90",
            name="ck_attendance_settings_raw_retention_range",
        ),
        CheckConstraint(
            "location_evidence_retention_days BETWEEN 30 AND 2555",
            name="ck_attendance_settings_evidence_retention_range",
        ),
    )


class SchoolGeofence(BaseModel):
    """Server-owned geofence definition for one tenant site."""

    __tablename__ = "school_geofences"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SchoolGeofenceStatus] = mapped_column(
        _enum(SchoolGeofenceStatus, "school_geofence_status"),
        nullable=False,
        default=SchoolGeofenceStatus.ACTIVE,
        server_default=SchoolGeofenceStatus.ACTIVE.value,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    evaluations: Mapped[list["GeofenceEvaluation"]] = relationship(
        "GeofenceEvaluation", back_populates="geofence"
    )

    __table_args__ = (
        CheckConstraint(
            "latitude BETWEEN -90 AND 90", name="ck_school_geofences_latitude_range"
        ),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="ck_school_geofences_longitude_range"
        ),
        CheckConstraint("radius_m > 0", name="ck_school_geofences_radius_positive"),
        Index("ix_school_geofences_tenant_status", "tenant_id", "status"),
        Index(
            "uq_school_geofences_primary_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_primary = true AND status = 'active'"),
        ),
    )


class GeofenceEvaluation(BaseModel):
    """One server-side location evaluation captured as evidence."""

    __tablename__ = "geofence_evaluations"

    geofence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_geofences.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_type: Mapped[AttendanceActorType] = mapped_column(
        _enum(AttendanceActorType, "attendance_actor_type"), nullable=False
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purpose: Mapped[str] = mapped_column(String(80), nullable=False)
    decision: Mapped[GeofenceDecision] = mapped_column(
        _enum(GeofenceDecision, "geofence_decision"), nullable=False
    )
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accuracy_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tolerance_m: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    provided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latitude_raw: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude_raw: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    raw_location_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    device_context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    geofence: Mapped[SchoolGeofence | None] = relationship(
        "SchoolGeofence", back_populates="evaluations"
    )

    __table_args__ = (
        CheckConstraint(
            "latitude_raw IS NULL OR latitude_raw BETWEEN -90 AND 90",
            name="ck_geofence_evaluations_latitude_range",
        ),
        CheckConstraint(
            "longitude_raw IS NULL OR longitude_raw BETWEEN -180 AND 180",
            name="ck_geofence_evaluations_longitude_range",
        ),
        CheckConstraint(
            "accuracy_m IS NULL OR accuracy_m > 0",
            name="ck_geofence_evaluations_accuracy_positive",
        ),
        CheckConstraint(
            "distance_m IS NULL OR distance_m >= 0",
            name="ck_geofence_evaluations_distance_nonnegative",
        ),
        Index(
            "ix_geofence_evaluations_tenant_actor",
            "tenant_id",
            "actor_type",
            "actor_id",
            "created_at",
        ),
        Index(
            "ix_geofence_evaluations_tenant_decision",
            "tenant_id",
            "decision",
            "created_at",
        ),
        Index(
            "ix_geofence_evaluations_tenant_expiry",
            "tenant_id",
            "raw_location_expires_at",
            "evidence_expires_at",
        ),
    )


class StudentAttendanceSheet(BaseModel):
    """Class-level attendance register for one date."""

    __tablename__ = "student_attendance_sheets"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=True,
    )
    calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_calendars.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[StudentAttendanceSheetStatus] = mapped_column(
        _enum(StudentAttendanceSheetStatus, "student_attendance_sheet_status"),
        nullable=False,
        default=StudentAttendanceSheetStatus.DRAFT,
        server_default=StudentAttendanceSheetStatus.DRAFT.value,
    )
    opened_by_teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_by_teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    locked_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    records: Mapped[list["StudentAttendanceRecord"]] = relationship(
        "StudentAttendanceRecord", back_populates="sheet"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "class_id",
            "attendance_date",
            name="uq_student_attendance_sheet_class_date",
        ),
        Index(
            "ix_student_attendance_sheets_tenant_date", "tenant_id", "attendance_date"
        ),
        Index(
            "ix_student_attendance_sheets_tenant_status",
            "tenant_id",
            "status",
            "attendance_date",
        ),
    )


class StudentAttendanceRecord(BaseModel):
    """Attendance row for one student on one class sheet."""

    __tablename__ = "student_attendance_records"

    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_attendance_sheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    student_enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_enrollments.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[StudentAttendanceStatus] = mapped_column(
        _enum(StudentAttendanceStatus, "student_attendance_status"),
        nullable=False,
        default=StudentAttendanceStatus.UNMARKED,
        server_default=StudentAttendanceStatus.UNMARKED.value,
    )
    marked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    marked_by_actor_type: Mapped[AttendanceActorType | None] = mapped_column(
        _enum(AttendanceActorType, "student_attendance_marked_by_type"), nullable=True
    )
    marked_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    sheet: Mapped[StudentAttendanceSheet] = relationship(
        "StudentAttendanceSheet", back_populates="records"
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "sheet_id",
            "student_id",
            name="uq_student_attendance_record_sheet_student",
        ),
        Index(
            "ix_student_attendance_records_tenant_student", "tenant_id", "student_id"
        ),
        Index("ix_student_attendance_records_tenant_status", "tenant_id", "status"),
    )


class WorkforceAttendanceRecord(BaseModel):
    """Teacher/staff workforce attendance for one day."""

    __tablename__ = "workforce_attendance_records"

    teacher_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    academic_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    academic_term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=True,
    )
    calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("school_calendars.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[WorkforceAttendanceStatus] = mapped_column(
        _enum(WorkforceAttendanceStatus, "workforce_attendance_status"),
        nullable=False,
        default=WorkforceAttendanceStatus.CHECKED_IN,
        server_default=WorkforceAttendanceStatus.CHECKED_IN.value,
    )
    check_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_in_geofence_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geofence_evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )
    check_out_geofence_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geofence_evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )
    check_in_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_out_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    corrected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "teacher_membership_id",
            "attendance_date",
            name="uq_workforce_attendance_teacher_date",
        ),
        CheckConstraint(
            "check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at",
            name="ck_workforce_attendance_checkout_after_checkin",
        ),
        Index("ix_workforce_attendance_tenant_date", "tenant_id", "attendance_date"),
        Index(
            "ix_workforce_attendance_tenant_teacher",
            "tenant_id",
            "teacher_membership_id",
        ),
    )


class TemporaryAttendanceAssignment(BaseModel):
    """Temporary delegation to manage a class attendance sheet."""

    __tablename__ = "temporary_attendance_assignments"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    teacher_membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teacher_memberships.id", ondelete="RESTRICT"),
        nullable=False,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TemporaryAssignmentStatus] = mapped_column(
        _enum(TemporaryAssignmentStatus, "temporary_attendance_assignment_status"),
        nullable=False,
        default=TemporaryAssignmentStatus.ACTIVE,
        server_default=TemporaryAssignmentStatus.ACTIVE.value,
    )
    assigned_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "ends_on >= starts_on", name="ck_temporary_attendance_assignment_date_order"
        ),
        Index(
            "ix_temporary_attendance_assignments_tenant_teacher",
            "tenant_id",
            "teacher_membership_id",
            "starts_on",
            "ends_on",
        ),
        Index(
            "ix_temporary_attendance_assignments_tenant_class",
            "tenant_id",
            "class_id",
            "starts_on",
            "ends_on",
        ),
    )


class AttendanceCorrection(BaseModel):
    """Audited correction request for an attendance row."""

    __tablename__ = "attendance_corrections"

    target_type: Mapped[AttendanceCorrectionTarget] = mapped_column(
        _enum(AttendanceCorrectionTarget, "attendance_correction_target"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[AttendanceCorrectionStatus] = mapped_column(
        _enum(AttendanceCorrectionStatus, "attendance_correction_status"),
        nullable=False,
        default=AttendanceCorrectionStatus.PENDING,
        server_default=AttendanceCorrectionStatus.PENDING.value,
    )
    requested_by_actor_type: Mapped[AttendanceActorType] = mapped_column(
        _enum(AttendanceActorType, "attendance_correction_actor_type"), nullable=False
    )
    requested_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    requested_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    applied_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "ix_attendance_corrections_tenant_status",
            "tenant_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_attendance_corrections_tenant_target",
            "tenant_id",
            "target_type",
            "target_id",
        ),
    )


class AttendanceNotification(BaseModel):
    """Idempotent reminder/notification work item for attendance events."""

    __tablename__ = "attendance_notifications"

    notification_key: Mapped[str] = mapped_column(String(220), nullable=False)
    channel: Mapped[AttendanceNotificationChannel] = mapped_column(
        _enum(AttendanceNotificationChannel, "attendance_notification_channel"),
        nullable=False,
    )
    status: Mapped[AttendanceNotificationStatus] = mapped_column(
        _enum(AttendanceNotificationStatus, "attendance_notification_status"),
        nullable=False,
        default=AttendanceNotificationStatus.PENDING,
        server_default=AttendanceNotificationStatus.PENDING.value,
    )
    recipient_actor_type: Mapped[AttendanceActorType] = mapped_column(
        _enum(AttendanceActorType, "attendance_notification_actor_type"), nullable=False
    )
    recipient_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "notification_key",
            name="uq_attendance_notifications_tenant_key",
        ),
        Index(
            "ix_attendance_notifications_tenant_status",
            "tenant_id",
            "status",
            "scheduled_for",
        ),
    )


class AttendanceAuditLog(BaseModel):
    """Append-only audit event for attendance actions."""

    __tablename__ = "attendance_audit_logs"

    actor_type: Mapped[AttendanceActorType] = mapped_column(
        _enum(AttendanceActorType, "attendance_audit_actor_type"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, default=dict
    )

    __table_args__ = (
        Index(
            "ix_attendance_audit_logs_tenant_entity",
            "tenant_id",
            "entity_type",
            "entity_id",
            "created_at",
        ),
        Index(
            "ix_attendance_audit_logs_tenant_actor",
            "tenant_id",
            "actor_type",
            "actor_id",
            "created_at",
        ),
    )
