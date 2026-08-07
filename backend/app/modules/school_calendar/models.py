"""School calendar persistence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    UUID,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarDaySource,
    SchoolCalendarDayType,
    SchoolCalendarEventAudience,
    SchoolCalendarEventStatus,
    SchoolCalendarEventType,
    SchoolCalendarStatus,
)
from app.modules.student_academics.models import enum_values
from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class SchoolCalendarConfiguration(BaseModel):
    __tablename__ = "school_calendar_configurations"

    timezone: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="Africa/Lagos",
        server_default="Africa/Lagos",
    )
    instructional_weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False
    )
    default_open_time: Mapped[time | None] = mapped_column(
        Time(timezone=False), nullable=True
    )
    default_close_time: Mapped[time | None] = mapped_column(
        Time(timezone=False), nullable=True
    )
    default_student_attendance_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    default_workforce_attendance_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_school_calendar_configurations_tenant"),
        CheckConstraint(
            "cardinality(instructional_weekdays) > 0",
            name="ck_school_calendar_config_weekdays_not_empty",
        ),
        CheckConstraint(
            "instructional_weekdays <@ ARRAY[0,1,2,3,4,5,6]",
            name="ck_school_calendar_config_weekdays_range",
        ),
        CheckConstraint(
            "default_open_time IS NULL OR default_close_time IS NULL OR default_close_time > default_open_time",
            name="ck_school_calendar_config_open_close_order",
        ),
    )


class SchoolCalendar(BaseModel):
    __tablename__ = "school_calendars"

    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[SchoolCalendarStatus] = mapped_column(
        SQLEnum(
            SchoolCalendarStatus,
            name="school_calendar_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=SchoolCalendarStatus.DRAFT,
        server_default=SchoolCalendarStatus.DRAFT.value,
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generated_from_configuration_revision: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "academic_term_id", name="uq_school_calendars_tenant_term"
        ),
        Index("ix_school_calendars_tenant_status", "tenant_id", "status"),
        Index(
            "uq_school_calendars_active_term",
            "tenant_id",
            "academic_term_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint(
            """
            (status = 'draft' AND activated_at IS NULL AND archived_at IS NULL)
            OR (status = 'active' AND activated_at IS NOT NULL AND archived_at IS NULL)
            OR (status = 'archived' AND archived_at IS NOT NULL)
            """,
            name="ck_school_calendars_status_timestamps",
        ),
    )


class SchoolCalendarDay(BaseModel):
    __tablename__ = "school_calendar_days"

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("school_calendars.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False)
    day_type: Mapped[SchoolCalendarDayType] = mapped_column(
        SQLEnum(
            SchoolCalendarDayType,
            name="school_calendar_day_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    school_open: Mapped[bool] = mapped_column(Boolean, nullable=False)
    student_activity_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    student_attendance_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    workforce_attendance_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    opens_at: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    closes_at: Mapped[time | None] = mapped_column(Time(timezone=False), nullable=True)
    source: Mapped[SchoolCalendarDaySource] = mapped_column(
        SQLEnum(
            SchoolCalendarDaySource,
            name="school_calendar_day_source",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=SchoolCalendarDaySource.GENERATED,
        server_default=SchoolCalendarDaySource.GENERATED.value,
    )
    is_manual_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "calendar_id",
            "calendar_date",
            name="uq_school_calendar_days_tenant_calendar_date",
        ),
        Index("ix_school_calendar_days_tenant_date", "tenant_id", "calendar_date"),
        Index(
            "ix_school_calendar_days_tenant_term_date",
            "tenant_id",
            "academic_term_id",
            "calendar_date",
        ),
        CheckConstraint(
            "opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at",
            name="ck_school_calendar_days_open_close_order",
        ),
        CheckConstraint(
            "student_attendance_required = false OR student_activity_allowed = true",
            name="ck_school_calendar_days_attendance_requires_activity",
        ),
        CheckConstraint(
            "school_open = true OR student_attendance_required = false",
            name="ck_school_calendar_days_closed_no_student_attendance",
        ),
    )


class SchoolCalendarEvent(BaseModel):
    __tablename__ = "school_calendar_events"

    calendar_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("school_calendars.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_sessions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    academic_term_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("academic_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    event_type: Mapped[SchoolCalendarEventType] = mapped_column(
        SQLEnum(
            SchoolCalendarEventType,
            name="school_calendar_event_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_all_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    audience: Mapped[SchoolCalendarEventAudience] = mapped_column(
        SQLEnum(
            SchoolCalendarEventAudience,
            name="school_calendar_event_audience",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=SchoolCalendarEventAudience.ALL,
        server_default=SchoolCalendarEventAudience.ALL.value,
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[SchoolCalendarEventStatus] = mapped_column(
        SQLEnum(
            SchoolCalendarEventStatus,
            name="school_calendar_event_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=SchoolCalendarEventStatus.DRAFT,
        server_default=SchoolCalendarEventStatus.DRAFT.value,
    )
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index(
            "ix_school_calendar_events_tenant_status_start",
            "tenant_id",
            "status",
            "starts_at",
        ),
        CheckConstraint(
            "ends_at > starts_at", name="ck_school_calendar_events_ends_after_start"
        ),
        CheckConstraint(
            "status <> 'published' OR published_at IS NOT NULL",
            name="ck_school_calendar_events_published_at",
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name="ck_school_calendar_events_cancelled_at",
        ),
    )


class SchoolCalendarLifecycleAudit(BaseModel):
    __tablename__ = "school_calendar_lifecycle_audits"

    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    previous_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    acting_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("tenant_admins.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "ix_school_calendar_lifecycle_audits_tenant_entity",
            "tenant_id",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_school_calendar_lifecycle_audits_tenant_action", "tenant_id", "action"
        ),
    )
