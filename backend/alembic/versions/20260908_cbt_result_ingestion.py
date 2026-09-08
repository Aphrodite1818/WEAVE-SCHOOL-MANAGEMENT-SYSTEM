"""Add immutable CBT result-ingestion audit ledger.

Revision ID: 20260908_cbt_result_ingestion
Revises: 20260906_communication_notices
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_cbt_result_ingestion"
down_revision: Union[str, Sequence[str], None] = "20260906_communication_notices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    ingestion_status = postgresql.ENUM(
        "processing",
        "completed",
        "completed_with_rejections",
        "rejected",
        "failed",
        name="cbt_result_ingestion_status",
        schema="public",
    )
    ingestion_outcome = postgresql.ENUM(
        "applied",
        "unchanged",
        "rejected",
        name="cbt_result_ingestion_outcome",
        schema="public",
    )

    ingestion_status.create(bind, checkfirst=True)
    ingestion_outcome.create(bind, checkfirst=True)

    status_type = postgresql.ENUM(
        "processing",
        "completed",
        "completed_with_rejections",
        "rejected",
        "failed",
        name="cbt_result_ingestion_status",
        schema="public",
        create_type=False,
    )
    outcome_type = postgresql.ENUM(
        "applied",
        "unchanged",
        "rejected",
        name="cbt_result_ingestion_outcome",
        schema="public",
        create_type=False,
    )

    op.create_table(
        "cbt_result_ingestion_batches",
        sa.Column("cbt_server_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("credential_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_exam_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("academic_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_term_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_level_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_component_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            status_type,
            server_default="processing",
            nullable=False,
        ),
        sa.Column("received_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("applied_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("batch_error_code", sa.String(length=100), nullable=True),
        sa.Column("batch_error_detail", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "received_count >= 0 AND applied_count >= 0 AND unchanged_count >= 0 AND rejected_count >= 0",
            name="ck_cbt_result_ingestion_nonnegative_counts",
        ),
        sa.CheckConstraint(
            "applied_count + unchanged_count + rejected_count <= received_count",
            name="ck_cbt_result_ingestion_processed_not_over_received",
        ),
        sa.CheckConstraint(
            "status = 'processing' OR processed_at IS NOT NULL",
            name="ck_cbt_result_ingestion_finished_has_processed_at",
        ),
        sa.CheckConstraint(
            "status NOT IN ('completed', 'completed_with_rejections', 'rejected') OR applied_count + unchanged_count + rejected_count = received_count",
            name="ck_cbt_result_ingestion_finished_counts_match",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["cbt_server_id"],
            ["public.cbt_servers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["public.cbt_server_credentials.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "cbt_server_id",
            "batch_id",
            name="uq_cbt_result_ingestion_tenant_server_batch",
        ),
        schema="public",
    )

    op.create_index(
        "ix_cbt_result_ingestion_tenant_status",
        "cbt_result_ingestion_batches",
        ["tenant_id", "status"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_tenant_server",
        "cbt_result_ingestion_batches",
        ["tenant_id", "cbt_server_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_tenant_source_exam",
        "cbt_result_ingestion_batches",
        ["tenant_id", "source_exam_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_tenant_component",
        "cbt_result_ingestion_batches",
        ["tenant_id", "assessment_component_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_tenant_period",
        "cbt_result_ingestion_batches",
        ["tenant_id", "academic_session_id", "academic_term_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_tenant_level_subject",
        "cbt_result_ingestion_batches",
        ["tenant_id", "academic_level_id", "curriculum_subject_id"],
        unique=False,
        schema="public",
    )

    op.create_table(
        "cbt_result_ingestion_items",
        sa.Column("ingestion_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_teacher_assignment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incoming_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("previous_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("resulting_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("student_subject_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", outcome_type, nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "incoming_score >= 0",
            name="ck_cbt_result_ingestion_item_incoming_score_nonnegative",
        ),
        sa.CheckConstraint(
            "previous_score IS NULL OR previous_score >= 0",
            name="ck_cbt_result_ingestion_item_previous_score_nonnegative",
        ),
        sa.CheckConstraint(
            "resulting_score IS NULL OR resulting_score >= 0",
            name="ck_cbt_result_ingestion_item_resulting_score_nonnegative",
        ),
        sa.CheckConstraint(
            "outcome <> 'rejected' OR error_code IS NOT NULL",
            name="ck_cbt_result_ingestion_item_rejection_has_error",
        ),
        sa.CheckConstraint(
            "outcome = 'rejected' OR resulting_score IS NOT NULL",
            name="ck_cbt_result_ingestion_item_success_has_resulting_score",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["public.tenants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_batch_id"],
            ["public.cbt_result_ingestion_batches.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_batch_id",
            "submitted_student_id",
            name="uq_cbt_result_ingestion_item_batch_student",
        ),
        schema="public",
    )

    op.create_index(
        "ix_cbt_result_ingestion_item_tenant_batch",
        "cbt_result_ingestion_items",
        ["tenant_id", "ingestion_batch_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_item_tenant_student",
        "cbt_result_ingestion_items",
        ["tenant_id", "submitted_student_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_item_tenant_outcome",
        "cbt_result_ingestion_items",
        ["tenant_id", "outcome"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_item_result",
        "cbt_result_ingestion_items",
        ["tenant_id", "student_subject_result_id"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_result_ingestion_item_teacher_assignment",
        "cbt_result_ingestion_items",
        ["tenant_id", "resolved_teacher_assignment_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cbt_result_ingestion_item_teacher_assignment",
        table_name="cbt_result_ingestion_items",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_item_result",
        table_name="cbt_result_ingestion_items",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_item_tenant_outcome",
        table_name="cbt_result_ingestion_items",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_item_tenant_student",
        table_name="cbt_result_ingestion_items",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_item_tenant_batch",
        table_name="cbt_result_ingestion_items",
        schema="public",
    )
    op.drop_table("cbt_result_ingestion_items", schema="public")

    op.drop_index(
        "ix_cbt_result_ingestion_tenant_level_subject",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_tenant_period",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_tenant_component",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_tenant_source_exam",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_tenant_server",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_result_ingestion_tenant_status",
        table_name="cbt_result_ingestion_batches",
        schema="public",
    )
    op.drop_table("cbt_result_ingestion_batches", schema="public")

    bind = op.get_bind()
    postgresql.ENUM(
        "applied",
        "unchanged",
        "rejected",
        name="cbt_result_ingestion_outcome",
        schema="public",
    ).drop(bind, checkfirst=True)
    postgresql.ENUM(
        "processing",
        "completed",
        "completed_with_rejections",
        "rejected",
        "failed",
        name="cbt_result_ingestion_status",
        schema="public",
    ).drop(bind, checkfirst=True)
