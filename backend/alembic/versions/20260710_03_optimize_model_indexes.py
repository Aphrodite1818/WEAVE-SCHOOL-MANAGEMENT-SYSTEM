"""optimize workload-backed model indexes

Revision ID: 20260710_optimize_model_indexes
Revises: 90f4e3429a7c
Create Date: 2026-07-10 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_optimize_model_indexes"
down_revision = "90f4e3429a7c"
branch_labels = None
depends_on = None

PUBLIC_SCHEMA = "public"


def upgrade() -> None:
    """Add workload-specific indexes and remove exact duplicates."""

    # Keep one deterministic active/current session and term per tenant before
    # enforcing the partial unique indexes.
    op.execute(
        """
        WITH ranked_sessions AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_number
            FROM public.academic_sessions
            WHERE is_current = true AND is_active = true
        )
        UPDATE public.academic_sessions AS academic_session
        SET is_current = false
        FROM ranked_sessions
        WHERE academic_session.id = ranked_sessions.id
          AND ranked_sessions.row_number > 1
        """
    )
    op.execute(
        """
        WITH ranked_terms AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY tenant_id
                    ORDER BY updated_at DESC, created_at DESC, id DESC
                ) AS row_number
            FROM public.academic_terms
            WHERE is_current = true AND is_active = true
        )
        UPDATE public.academic_terms AS academic_term
        SET is_current = false
        FROM ranked_terms
        WHERE academic_term.id = ranked_terms.id
          AND ranked_terms.row_number > 1
        """
    )

    op.create_index(
        "ix_email_outbox_pending_claim",
        "email_outbox",
        ["next_retry_at", "created_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_email_outbox_processing_recovery",
        "email_outbox",
        ["processing_started_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("status = 'processing'"),
    )

    op.create_index(
        "uq_academic_sessions_current_per_tenant",
        "academic_sessions",
        ["tenant_id"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("is_current = true AND is_active = true"),
    )
    op.create_index(
        "uq_academic_terms_current_per_tenant",
        "academic_terms",
        ["tenant_id"],
        unique=True,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("is_current = true AND is_active = true"),
    )
    op.create_index(
        "ix_class_subject_teachers_tenant_teacher_active",
        "class_subject_teachers",
        ["tenant_id", "teacher_id", "is_active"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_student_subject_results_student_period",
        "student_subject_results",
        ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_student_subject_results_class_period_status",
        "student_subject_results",
        ["tenant_id", "class_id", "academic_session_id", "academic_term_id", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_student_subject_results_teacher_period",
        "student_subject_results",
        ["tenant_id", "teacher_id", "academic_session_id", "academic_term_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    op.create_index(
        "ix_announcements_tenant_status_feed",
        "announcements",
        ["tenant_id", "status", "is_pinned", "created_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_announcement_reads_actor_status",
        "announcement_reads",
        ["tenant_id", "actor_type", "actor_id", "status"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    op.create_index(
        "ix_auth_active_email_purpose",
        "auth",
        ["tenant_id", "email", "purpose", "expires_at"],
        unique=False,
        schema=PUBLIC_SCHEMA,
        postgresql_where=sa.text("is_used = false"),
    )

    op.drop_index(
        "ix_classes_tenant_normalized_lookup",
        table_name="classes",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_auth_identities_actor",
        table_name="auth_identities",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_report_card_lines_tenant_card",
        table_name="report_card_subject_lines",
        schema=PUBLIC_SCHEMA,
    )


def downgrade() -> None:
    """Restore the previous index layout."""

    op.create_index(
        "ix_report_card_lines_tenant_card",
        "report_card_subject_lines",
        ["tenant_id", "report_card_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_auth_identities_actor",
        "auth_identities",
        ["actor_type", "actor_id"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )
    op.create_index(
        "ix_classes_tenant_normalized_lookup",
        "classes",
        ["tenant_id", "normalized_name", "normalized_arm"],
        unique=False,
        schema=PUBLIC_SCHEMA,
    )

    op.drop_index(
        "ix_auth_active_email_purpose",
        table_name="auth",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_announcement_reads_actor_status",
        table_name="announcement_reads",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_announcements_tenant_status_feed",
        table_name="announcements",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_student_subject_results_teacher_period",
        table_name="student_subject_results",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_student_subject_results_class_period_status",
        table_name="student_subject_results",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_student_subject_results_student_period",
        table_name="student_subject_results",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_class_subject_teachers_tenant_teacher_active",
        table_name="class_subject_teachers",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "uq_academic_terms_current_per_tenant",
        table_name="academic_terms",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "uq_academic_sessions_current_per_tenant",
        table_name="academic_sessions",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_email_outbox_processing_recovery",
        table_name="email_outbox",
        schema=PUBLIC_SCHEMA,
    )
    op.drop_index(
        "ix_email_outbox_pending_claim",
        table_name="email_outbox",
        schema=PUBLIC_SCHEMA,
    )
