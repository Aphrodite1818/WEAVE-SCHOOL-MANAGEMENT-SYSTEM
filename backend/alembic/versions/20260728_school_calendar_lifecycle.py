"""Add school calendar lifecycle.

Revision ID: 20260728_school_calendar
Revises: 270287aab63d
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_school_calendar"
down_revision: str | Sequence[str] | None = "270287aab63d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    postgresql.ENUM(*values, name=name, schema="public").create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*values, name=name, schema="public", create_type=False)


def upgrade() -> None:
    # PostgreSQL cannot use a newly-added enum label in later DDL in the same
    # transaction on older supported versions. Add it outside the migration
    # transaction before constraints reference the value.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE public.academic_term_status ADD VALUE IF NOT EXISTS 'closing'")
    op.add_column(
        "academic_terms",
        sa.Column("closing_started_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.drop_constraint("ck_academic_term_status_timestamps", "academic_terms", schema="public", type_="check")
    op.execute(
        """
        UPDATE public.academic_terms
        SET opened_at = COALESCE(opened_at, created_at, now())
        WHERE status IN ('open', 'closed')
          AND opened_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.academic_terms
        SET closing_started_at = COALESCE(closing_started_at, closed_at, updated_at, now())
        WHERE status = 'closed'
          AND closing_started_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE public.academic_terms
        SET is_current = false
        WHERE status <> 'open'
          AND is_current = true
        """
    )
    op.create_check_constraint(
        "ck_academic_term_status_timestamps",
        "academic_terms",
        """
        (status = 'draft' AND opened_at IS NULL AND closing_started_at IS NULL AND closed_at IS NULL)
        OR (status = 'open' AND opened_at IS NOT NULL AND closing_started_at IS NULL AND closed_at IS NULL)
        OR (status = 'closing' AND opened_at IS NOT NULL AND closing_started_at IS NOT NULL AND closed_at IS NULL)
        OR (status = 'closed' AND opened_at IS NOT NULL AND closing_started_at IS NOT NULL AND closed_at IS NOT NULL)
        """,
        schema="public",
    )

    calendar_status = _create_enum("school_calendar_status", ("draft", "active", "archived"))
    day_type = _create_enum(
        "school_calendar_day_type",
        (
            "instructional_day",
            "examination_day",
            "weekend",
            "public_holiday",
            "school_holiday",
            "mid_term_break",
            "staff_training_day",
            "special_school_day",
            "emergency_closure",
        ),
    )
    day_source = _create_enum("school_calendar_day_source", ("generated", "manual", "system"))
    event_type = _create_enum(
        "school_calendar_event_type",
        ("academic", "holiday", "examination", "meeting", "activity", "emergency", "other"),
    )
    event_audience = _create_enum(
        "school_calendar_event_audience",
        ("all", "tenant_admins", "teachers", "parents", "students"),
    )
    event_status = _create_enum("school_calendar_event_status", ("draft", "published", "cancelled"))

    op.create_table(
        "school_calendar_configurations",
        sa.Column("timezone", sa.String(length=80), server_default="Africa/Lagos", nullable=False),
        sa.Column("instructional_weekdays", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("default_open_time", sa.Time(), nullable=True),
        sa.Column("default_close_time", sa.Time(), nullable=True),
        sa.Column("default_student_attendance_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("default_workforce_attendance_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("cardinality(instructional_weekdays) > 0", name="ck_school_calendar_config_weekdays_not_empty"),
        sa.CheckConstraint("instructional_weekdays <@ ARRAY[0,1,2,3,4,5,6]", name="ck_school_calendar_config_weekdays_range"),
        sa.CheckConstraint(
            "default_open_time IS NULL OR default_close_time IS NULL OR default_close_time > default_open_time",
            name="ck_school_calendar_config_open_close_order",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_school_calendar_configurations_tenant"),
        schema="public",
    )

    op.create_table(
        "school_calendars",
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        sa.Column("status", calendar_status, server_default="draft", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(status = 'draft' AND activated_at IS NULL AND archived_at IS NULL) "
            "OR (status = 'active' AND activated_at IS NOT NULL AND archived_at IS NULL) "
            "OR (status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_school_calendars_status_timestamps",
        ),
        sa.ForeignKeyConstraint(["academic_session_id"], ["public.academic_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activated_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["archived_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", "academic_term_id", name="uq_school_calendars_tenant_term"),
        schema="public",
    )
    op.create_index("ix_school_calendars_tenant_status", "school_calendars", ["tenant_id", "status"], schema="public")
    op.create_index("ix_public_school_calendars_academic_session_id", "school_calendars", ["academic_session_id"], schema="public")
    op.create_index("ix_public_school_calendars_academic_term_id", "school_calendars", ["academic_term_id"], schema="public")
    op.create_index(
        "uq_school_calendars_active_term",
        "school_calendars",
        ["tenant_id", "academic_term_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        schema="public",
    )

    op.create_table(
        "school_calendar_days",
        sa.Column("calendar_id", sa.UUID(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("day_type", day_type, nullable=False),
        sa.Column("title", sa.String(length=150), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("school_open", sa.Boolean(), nullable=False),
        sa.Column("student_activity_allowed", sa.Boolean(), nullable=False),
        sa.Column("student_attendance_required", sa.Boolean(), nullable=False),
        sa.Column("workforce_attendance_required", sa.Boolean(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=True),
        sa.Column("closes_at", sa.Time(), nullable=True),
        sa.Column("source", day_source, server_default="generated", nullable=False),
        sa.Column("is_manual_override", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("opens_at IS NULL OR closes_at IS NULL OR closes_at > opens_at", name="ck_school_calendar_days_open_close_order"),
        sa.CheckConstraint("student_attendance_required = false OR student_activity_allowed = true", name="ck_school_calendar_days_attendance_requires_activity"),
        sa.CheckConstraint("school_open = true OR student_attendance_required = false", name="ck_school_calendar_days_closed_no_student_attendance"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["public.academic_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["calendar_id"], ["public.school_calendars.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", "calendar_id", "calendar_date", name="uq_school_calendar_days_tenant_calendar_date"),
        schema="public",
    )
    op.create_index("ix_school_calendar_days_tenant_date", "school_calendar_days", ["tenant_id", "calendar_date"], schema="public")
    op.create_index("ix_school_calendar_days_tenant_term_date", "school_calendar_days", ["tenant_id", "academic_term_id", "calendar_date"], schema="public")
    op.create_index("ix_public_school_calendar_days_calendar_id", "school_calendar_days", ["calendar_id"], schema="public")

    op.create_table(
        "school_calendar_events",
        sa.Column("calendar_id", sa.UUID(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("event_type", event_type, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_all_day", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("audience", event_audience, server_default="all", nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("status", event_status, server_default="draft", nullable=False),
        sa.Column("created_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_school_calendar_events_ends_after_start"),
        sa.CheckConstraint("status <> 'published' OR published_at IS NOT NULL", name="ck_school_calendar_events_published_at"),
        sa.CheckConstraint("status <> 'cancelled' OR cancelled_at IS NOT NULL", name="ck_school_calendar_events_cancelled_at"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["public.academic_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["calendar_id"], ["public.school_calendars.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index("ix_school_calendar_events_tenant_status_start", "school_calendar_events", ["tenant_id", "status", "starts_at"], schema="public")

    op.create_table(
        "school_calendar_lifecycle_audits",
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acting_admin_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["acting_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index("ix_school_calendar_lifecycle_audits_tenant_action", "school_calendar_lifecycle_audits", ["tenant_id", "action"], schema="public")
    op.create_index("ix_school_calendar_lifecycle_audits_tenant_entity", "school_calendar_lifecycle_audits", ["tenant_id", "entity_type", "entity_id"], schema="public")


def downgrade() -> None:
    op.drop_index("ix_school_calendar_lifecycle_audits_tenant_entity", table_name="school_calendar_lifecycle_audits", schema="public")
    op.drop_index("ix_school_calendar_lifecycle_audits_tenant_action", table_name="school_calendar_lifecycle_audits", schema="public")
    op.drop_table("school_calendar_lifecycle_audits", schema="public")
    op.drop_index("ix_school_calendar_events_tenant_status_start", table_name="school_calendar_events", schema="public")
    op.drop_table("school_calendar_events", schema="public")
    op.drop_index("ix_public_school_calendar_days_calendar_id", table_name="school_calendar_days", schema="public")
    op.drop_index("ix_school_calendar_days_tenant_term_date", table_name="school_calendar_days", schema="public")
    op.drop_index("ix_school_calendar_days_tenant_date", table_name="school_calendar_days", schema="public")
    op.drop_table("school_calendar_days", schema="public")
    op.drop_index("uq_school_calendars_active_term", table_name="school_calendars", schema="public")
    op.drop_index("ix_public_school_calendars_academic_term_id", table_name="school_calendars", schema="public")
    op.drop_index("ix_public_school_calendars_academic_session_id", table_name="school_calendars", schema="public")
    op.drop_index("ix_school_calendars_tenant_status", table_name="school_calendars", schema="public")
    op.drop_table("school_calendars", schema="public")
    op.drop_table("school_calendar_configurations", schema="public")
    for enum_name in (
        "school_calendar_event_status",
        "school_calendar_event_audience",
        "school_calendar_event_type",
        "school_calendar_day_source",
        "school_calendar_day_type",
        "school_calendar_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS public.{enum_name}")
    op.drop_constraint("ck_academic_term_status_timestamps", "academic_terms", schema="public", type_="check")
    op.create_check_constraint(
        "ck_academic_term_status_timestamps",
        "academic_terms",
        """
        (status = 'draft' AND opened_at IS NULL AND closed_at IS NULL)
        OR (status = 'open' AND opened_at IS NOT NULL AND closed_at IS NULL)
        OR (status = 'closed' AND opened_at IS NOT NULL AND closed_at IS NOT NULL)
        """,
        schema="public",
    )
    op.drop_column("academic_terms", "closing_started_at", schema="public")
    # PostgreSQL cannot remove enum values safely without recreating the type;
    # leave 'closing' in place on downgrade to avoid corrupting existing data.
