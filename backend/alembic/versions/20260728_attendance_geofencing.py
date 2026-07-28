"""Add attendance and geofencing system.

Revision ID: 20260728_attendance
Revises: 20260728_school_calendar
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from alembic import context
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "20260728_attendance"
down_revision: str | Sequence[str] | None = "20260728_school_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    postgresql.ENUM(*values, name=name, schema="public").create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*values, name=name, schema="public", create_type=False)


def _table_exists(table_name: str) -> bool:
    if context.is_offline_mode():
        return True
    return inspect(op.get_bind()).has_table(table_name, schema="public")


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _base_constraints() -> list:
    return [
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    ]


def upgrade() -> None:
    settings_status = _create_enum("attendance_settings_status", ("active", "archived"))
    actor_type = _create_enum("attendance_actor_type", ("tenant_admin", "teacher", "student", "parent", "system"))
    geofence_status = _create_enum("school_geofence_status", ("active", "inactive", "archived"))
    geofence_decision = _create_enum("geofence_decision", ("inside", "outside", "inaccurate", "unavailable", "invalid"))
    sheet_status = _create_enum("student_attendance_sheet_status", ("draft", "submitted", "approved", "locked", "cancelled"))
    student_status = _create_enum("student_attendance_status", ("unmarked", "present", "absent", "late", "excused"))
    marked_by_type = _create_enum("student_attendance_marked_by_type", ("tenant_admin", "teacher", "student", "parent", "system"))
    workforce_status = _create_enum("workforce_attendance_status", ("checked_in", "checked_out", "absent", "excused", "corrected"))
    assignment_status = _create_enum("temporary_attendance_assignment_status", ("active", "ended", "cancelled"))
    correction_target = _create_enum("attendance_correction_target", ("student_record", "workforce_record"))
    correction_status = _create_enum("attendance_correction_status", ("pending", "approved", "rejected", "cancelled"))
    correction_actor = _create_enum("attendance_correction_actor_type", ("tenant_admin", "teacher", "student", "parent", "system"))
    notification_channel = _create_enum("attendance_notification_channel", ("email", "in_app"))
    notification_status = _create_enum("attendance_notification_status", ("pending", "sent", "skipped", "failed"))
    notification_actor = _create_enum("attendance_notification_actor_type", ("tenant_admin", "teacher", "student", "parent", "system"))
    audit_actor = _create_enum("attendance_audit_actor_type", ("tenant_admin", "teacher", "student", "parent", "system"))

    if _table_exists("attendance_settings"):
        return

    op.create_table(
        "attendance_settings",
        sa.Column("status", settings_status, server_default="active", nullable=False),
        sa.Column("timezone", sa.String(length=80), server_default="Africa/Lagos", nullable=False),
        sa.Column("student_marking_opens_at", sa.Time(), nullable=True),
        sa.Column("student_marking_closes_at", sa.Time(), nullable=True),
        sa.Column("workforce_check_in_opens_at", sa.Time(), nullable=True),
        sa.Column("workforce_check_in_closes_at", sa.Time(), nullable=True),
        sa.Column("workforce_check_out_opens_at", sa.Time(), nullable=True),
        sa.Column("workforce_check_out_closes_at", sa.Time(), nullable=True),
        sa.Column("late_after_time", sa.Time(), nullable=True),
        sa.Column("require_geofence_for_workforce", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("geofence_accuracy_threshold_m", sa.Integer(), server_default="100", nullable=False),
        sa.Column("geofence_tolerance_m", sa.Integer(), server_default="25", nullable=False),
        sa.Column("location_raw_retention_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column("location_evidence_retention_days", sa.Integer(), server_default="365", nullable=False),
        sa.Column("require_student_sheet_submission", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notify_absent_parents", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notify_absent_staff", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("configuration_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_admin_id", sa.UUID(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("student_marking_opens_at IS NULL OR student_marking_closes_at IS NULL OR student_marking_closes_at > student_marking_opens_at", name="ck_attendance_settings_student_window"),
        sa.CheckConstraint("workforce_check_in_opens_at IS NULL OR workforce_check_in_closes_at IS NULL OR workforce_check_in_closes_at > workforce_check_in_opens_at", name="ck_attendance_settings_workforce_in_window"),
        sa.CheckConstraint("workforce_check_out_opens_at IS NULL OR workforce_check_out_closes_at IS NULL OR workforce_check_out_closes_at > workforce_check_out_opens_at", name="ck_attendance_settings_workforce_out_window"),
        sa.CheckConstraint("geofence_accuracy_threshold_m > 0", name="ck_attendance_settings_accuracy_positive"),
        sa.CheckConstraint("geofence_tolerance_m >= 0", name="ck_attendance_settings_tolerance_nonnegative"),
        sa.CheckConstraint("location_raw_retention_days BETWEEN 0 AND 90", name="ck_attendance_settings_raw_retention_range"),
        sa.CheckConstraint("location_evidence_retention_days BETWEEN 30 AND 2555", name="ck_attendance_settings_evidence_retention_range"),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        sa.UniqueConstraint("tenant_id", name="uq_attendance_settings_tenant"),
        schema="public",
    )

    op.create_table(
        "school_geofences",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("radius_m", sa.Integer(), nullable=False),
        sa.Column("status", geofence_status, server_default="active", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_admin_id", sa.UUID(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_school_geofences_latitude_range"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_school_geofences_longitude_range"),
        sa.CheckConstraint("radius_m > 0", name="ck_school_geofences_radius_positive"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["archived_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        schema="public",
    )
    op.create_index("ix_school_geofences_tenant_status", "school_geofences", ["tenant_id", "status"], schema="public")
    op.create_index("uq_school_geofences_primary_active", "school_geofences", ["tenant_id"], unique=True, schema="public", postgresql_where=sa.text("is_primary = true AND status = 'active'"))

    op.create_table(
        "geofence_evaluations",
        sa.Column("geofence_id", sa.UUID(), nullable=True),
        sa.Column("actor_type", actor_type, nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("decision", geofence_decision, nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("accuracy_m", sa.Integer(), nullable=True),
        sa.Column("tolerance_m", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude_raw", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude_raw", sa.Numeric(9, 6), nullable=True),
        sa.Column("raw_location_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_context", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("latitude_raw IS NULL OR latitude_raw BETWEEN -90 AND 90", name="ck_geofence_evaluations_latitude_range"),
        sa.CheckConstraint("longitude_raw IS NULL OR longitude_raw BETWEEN -180 AND 180", name="ck_geofence_evaluations_longitude_range"),
        sa.CheckConstraint("accuracy_m IS NULL OR accuracy_m > 0", name="ck_geofence_evaluations_accuracy_positive"),
        sa.CheckConstraint("distance_m IS NULL OR distance_m >= 0", name="ck_geofence_evaluations_distance_nonnegative"),
        sa.ForeignKeyConstraint(["geofence_id"], ["public.school_geofences.id"], ondelete="SET NULL"),
        *_base_constraints(),
        schema="public",
    )
    op.create_index("ix_geofence_evaluations_tenant_actor", "geofence_evaluations", ["tenant_id", "actor_type", "actor_id", "created_at"], schema="public")
    op.create_index("ix_geofence_evaluations_tenant_decision", "geofence_evaluations", ["tenant_id", "decision", "created_at"], schema="public")
    op.create_index("ix_geofence_evaluations_tenant_expiry", "geofence_evaluations", ["tenant_id", "raw_location_expires_at", "evidence_expires_at"], schema="public")

    op.create_table(
        "student_attendance_sheets",
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=False),
        sa.Column("academic_term_id", sa.UUID(), nullable=True),
        sa.Column("calendar_id", sa.UUID(), nullable=True),
        sa.Column("status", sheet_status, server_default="draft", nullable=False),
        sa.Column("opened_by_teacher_membership_id", sa.UUID(), nullable=True),
        sa.Column("submitted_by_teacher_membership_id", sa.UUID(), nullable=True),
        sa.Column("approved_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("locked_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["public.academic_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["calendar_id"], ["public.school_calendars.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["opened_by_teacher_membership_id"], ["public.teacher_memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_teacher_membership_id"], ["public.teacher_memberships.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["locked_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        sa.UniqueConstraint("tenant_id", "class_id", "attendance_date", name="uq_student_attendance_sheet_class_date"),
        schema="public",
    )
    op.create_index("ix_student_attendance_sheets_tenant_date", "student_attendance_sheets", ["tenant_id", "attendance_date"], schema="public")
    op.create_index("ix_student_attendance_sheets_tenant_status", "student_attendance_sheets", ["tenant_id", "status", "attendance_date"], schema="public")

    op.create_table(
        "student_attendance_records",
        sa.Column("sheet_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("student_enrollment_id", sa.UUID(), nullable=True),
        sa.Column("status", student_status, server_default="unmarked", nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marked_by_actor_type", marked_by_type, nullable=True),
        sa.Column("marked_by_actor_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["sheet_id"], ["public.student_attendance_sheets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["public.students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_enrollment_id"], ["public.student_enrollments.id"], ondelete="SET NULL"),
        *_base_constraints(),
        sa.UniqueConstraint("tenant_id", "sheet_id", "student_id", name="uq_student_attendance_record_sheet_student"),
        schema="public",
    )
    op.create_index("ix_student_attendance_records_tenant_student", "student_attendance_records", ["tenant_id", "student_id"], schema="public")
    op.create_index("ix_student_attendance_records_tenant_status", "student_attendance_records", ["tenant_id", "status"], schema="public")

    op.create_table(
        "workforce_attendance_records",
        sa.Column("teacher_membership_id", sa.UUID(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("academic_session_id", sa.UUID(), nullable=True),
        sa.Column("academic_term_id", sa.UUID(), nullable=True),
        sa.Column("calendar_id", sa.UUID(), nullable=True),
        sa.Column("status", workforce_status, server_default="checked_in", nullable=False),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_in_geofence_evaluation_id", sa.UUID(), nullable=True),
        sa.Column("check_out_geofence_evaluation_id", sa.UUID(), nullable=True),
        sa.Column("check_in_notes", sa.Text(), nullable=True),
        sa.Column("check_out_notes", sa.Text(), nullable=True),
        sa.Column("corrected_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("corrected_at", sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at", name="ck_workforce_attendance_checkout_after_checkin"),
        sa.ForeignKeyConstraint(["teacher_membership_id"], ["public.teacher_memberships.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_session_id"], ["public.academic_sessions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["calendar_id"], ["public.school_calendars.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["check_in_geofence_evaluation_id"], ["public.geofence_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["check_out_geofence_evaluation_id"], ["public.geofence_evaluations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["corrected_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        sa.UniqueConstraint("tenant_id", "teacher_membership_id", "attendance_date", name="uq_workforce_attendance_teacher_date"),
        schema="public",
    )
    op.create_index("ix_workforce_attendance_tenant_date", "workforce_attendance_records", ["tenant_id", "attendance_date"], schema="public")
    op.create_index("ix_workforce_attendance_tenant_teacher", "workforce_attendance_records", ["tenant_id", "teacher_membership_id"], schema="public")

    op.create_table(
        "temporary_attendance_assignments",
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("teacher_membership_id", sa.UUID(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", assignment_status, server_default="active", nullable=False),
        sa.Column("assigned_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=300), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_temporary_attendance_assignment_date_order"),
        sa.ForeignKeyConstraint(["class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["teacher_membership_id"], ["public.teacher_memberships.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        schema="public",
    )
    op.create_index("ix_temporary_attendance_assignments_tenant_teacher", "temporary_attendance_assignments", ["tenant_id", "teacher_membership_id", "starts_on", "ends_on"], schema="public")
    op.create_index("ix_temporary_attendance_assignments_tenant_class", "temporary_attendance_assignments", ["tenant_id", "class_id", "starts_on", "ends_on"], schema="public")

    op.create_table(
        "attendance_corrections",
        sa.Column("target_type", correction_target, nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("status", correction_status, server_default="pending", nullable=False),
        sa.Column("requested_by_actor_type", correction_actor, nullable=False),
        sa.Column("requested_by_actor_id", sa.UUID(), nullable=False),
        sa.Column("reviewed_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("previous_state", postgresql.JSONB(), nullable=True),
        sa.Column("requested_state", postgresql.JSONB(), nullable=False),
        sa.Column("applied_state", postgresql.JSONB(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        *_base_constraints(),
        schema="public",
    )
    op.create_index("ix_attendance_corrections_tenant_status", "attendance_corrections", ["tenant_id", "status", "created_at"], schema="public")
    op.create_index("ix_attendance_corrections_tenant_target", "attendance_corrections", ["tenant_id", "target_type", "target_id"], schema="public")

    op.create_table(
        "attendance_notifications",
        sa.Column("notification_key", sa.String(length=220), nullable=False),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("status", notification_status, server_default="pending", nullable=False),
        sa.Column("recipient_actor_type", notification_actor, nullable=False),
        sa.Column("recipient_actor_id", sa.UUID(), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        *_base_columns(),
        *_base_constraints(),
        sa.UniqueConstraint("tenant_id", "notification_key", name="uq_attendance_notifications_tenant_key"),
        schema="public",
    )
    op.create_index("ix_attendance_notifications_tenant_status", "attendance_notifications", ["tenant_id", "status", "scheduled_for"], schema="public")

    op.create_table(
        "attendance_audit_logs",
        sa.Column("actor_type", audit_actor, nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        *_base_columns(),
        *_base_constraints(),
        schema="public",
    )
    op.create_index("ix_attendance_audit_logs_tenant_entity", "attendance_audit_logs", ["tenant_id", "entity_type", "entity_id", "created_at"], schema="public")
    op.create_index("ix_attendance_audit_logs_tenant_actor", "attendance_audit_logs", ["tenant_id", "actor_type", "actor_id", "created_at"], schema="public")


def downgrade() -> None:
    for table in (
        "attendance_audit_logs",
        "attendance_notifications",
        "attendance_corrections",
        "temporary_attendance_assignments",
        "workforce_attendance_records",
        "student_attendance_records",
        "student_attendance_sheets",
        "geofence_evaluations",
        "school_geofences",
        "attendance_settings",
    ):
        op.drop_table(table, schema="public")

    for enum_name in (
        "attendance_audit_actor_type",
        "attendance_notification_actor_type",
        "attendance_notification_status",
        "attendance_notification_channel",
        "attendance_correction_actor_type",
        "attendance_correction_status",
        "attendance_correction_target",
        "temporary_attendance_assignment_status",
        "workforce_attendance_status",
        "student_attendance_marked_by_type",
        "student_attendance_status",
        "student_attendance_sheet_status",
        "geofence_decision",
        "school_geofence_status",
        "attendance_actor_type",
        "attendance_settings_status",
    ):
        postgresql.ENUM(name=enum_name, schema="public").drop(op.get_bind(), checkfirst=True)
