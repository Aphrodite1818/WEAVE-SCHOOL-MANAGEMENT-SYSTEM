"""Replace fixed result columns with tenant assessment schemes.

Revision ID: 20260810_dynamic_assessments
Revises: 20260731_clean_baseline
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260810_dynamic_assessments"
down_revision: Union[str, Sequence[str], None] = "20260731_clean_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The fixed score and report-card records are development-only and cannot be
    # represented faithfully without knowing the tenant's intended component names.
    op.execute("DELETE FROM public.report_cards")
    op.execute("DELETE FROM public.student_subject_results")

    assessment_scheme_status = postgresql.ENUM(
        "draft",
        "active",
        "archived",
        name="assessment_scheme_status",
        schema="public",
        create_type=False,
    )
    assessment_scheme_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assessment_schemes",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            assessment_scheme_status,
            server_default="draft",
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND activated_at IS NULL AND archived_at IS NULL) OR "
            "(status = 'active' AND activated_at IS NOT NULL AND archived_at IS NULL) OR "
            "(status = 'archived' AND archived_at IS NOT NULL)",
            name="ck_assessment_scheme_status_timestamps",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_assessment_scheme_tenant_name"),
        schema="public",
    )
    op.create_index(
        "uq_assessment_scheme_active_tenant",
        "assessment_schemes",
        ["tenant_id"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "assessment_components",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("assessment_scheme_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("maximum_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "maximum_score > 0 AND maximum_score <= 100",
            name="ck_assessment_component_maximum",
        ),
        sa.CheckConstraint("position >= 0", name="ck_assessment_component_position"),
        sa.ForeignKeyConstraint(
            ["assessment_scheme_id"], ["public.assessment_schemes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_scheme_id", "name", name="uq_assessment_component_scheme_name"
        ),
        sa.UniqueConstraint(
            "assessment_scheme_id", "position", name="uq_assessment_component_scheme_position"
        ),
        schema="public",
    )
    op.create_index(
        "ix_assessment_components_tenant_scheme_position",
        "assessment_components",
        ["tenant_id", "assessment_scheme_id", "position"],
        schema="public",
    )

    op.add_column(
        "student_subject_results",
        sa.Column("assessment_scheme_id", sa.UUID(), nullable=False),
        schema="public",
    )
    op.create_foreign_key(
        "fk_result_assessment_scheme",
        "student_subject_results",
        "assessment_schemes",
        ["assessment_scheme_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_public_student_subject_results_assessment_scheme_id",
        "student_subject_results",
        ["assessment_scheme_id"],
        schema="public",
    )
    for column in ("test_score", "assessment_score", "exam_score"):
        op.drop_column("student_subject_results", column, schema="public")

    op.create_table(
        "student_assessment_scores",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("student_subject_result_id", sa.UUID(), nullable=False),
        sa.Column("assessment_component_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("score >= 0", name="ck_student_assessment_score_nonnegative"),
        sa.ForeignKeyConstraint(
            ["assessment_component_id"],
            ["public.assessment_components.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_subject_result_id"],
            ["public.student_subject_results.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_subject_result_id",
            "assessment_component_id",
            name="uq_student_assessment_score_result_component",
        ),
        schema="public",
    )
    op.create_index(
        "ix_student_assessment_scores_tenant_result",
        "student_assessment_scores",
        ["tenant_id", "student_subject_result_id"],
        schema="public",
    )
    op.create_index(
        "ix_student_assessment_scores_tenant_component",
        "student_assessment_scores",
        ["tenant_id", "assessment_component_id"],
        schema="public",
    )

    for column in ("test_score", "assessment_score", "exam_score"):
        op.drop_column("report_card_subject_lines", column, schema="public")
    op.create_table(
        "report_card_subject_components",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("report_card_subject_line_id", sa.UUID(), nullable=False),
        sa.Column("assessment_component_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("maximum_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "score >= 0 AND maximum_score > 0 AND score <= maximum_score",
            name="ck_report_card_component_score",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_component_id"],
            ["public.assessment_components.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["report_card_subject_line_id"],
            ["public.report_card_subject_lines.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "report_card_subject_line_id",
            "assessment_component_id",
            name="uq_report_card_component_line_component",
        ),
        schema="public",
    )
    op.create_index(
        "ix_report_card_subject_components_tenant_line_position",
        "report_card_subject_components",
        ["tenant_id", "report_card_subject_line_id", "position"],
        schema="public",
    )
    op.drop_table("school_assessment_configs", schema="public")


def downgrade() -> None:
    op.execute("DELETE FROM public.report_cards")
    op.execute("DELETE FROM public.student_subject_results")
    op.create_table(
        "school_assessment_configs",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("test_max", sa.Integer(), server_default="20", nullable=False),
        sa.Column("assessment_max", sa.Integer(), server_default="20", nullable=False),
        sa.Column("exam_max", sa.Integer(), server_default="60", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint(
            "test_max + assessment_max + exam_max = 100",
            name="ck_school_assessment_config_total",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_school_assessment_config_tenant"),
        schema="public",
    )
    op.drop_table("report_card_subject_components", schema="public")
    for column in ("test_score", "assessment_score", "exam_score"):
        op.add_column(
            "report_card_subject_lines",
            sa.Column(column, sa.Numeric(5, 2), nullable=False),
            schema="public",
        )
    op.drop_table("student_assessment_scores", schema="public")
    op.drop_index(
        "ix_public_student_subject_results_assessment_scheme_id",
        table_name="student_subject_results",
        schema="public",
    )
    op.drop_constraint(
        "fk_result_assessment_scheme",
        "student_subject_results",
        type_="foreignkey",
        schema="public",
    )
    op.drop_column("student_subject_results", "assessment_scheme_id", schema="public")
    for column in ("test_score", "assessment_score", "exam_score"):
        op.add_column(
            "student_subject_results",
            sa.Column(column, sa.Numeric(5, 2), nullable=True),
            schema="public",
        )
    op.drop_table("assessment_components", schema="public")
    op.drop_table("assessment_schemes", schema="public")
    postgresql.ENUM(name="assessment_scheme_status", schema="public").drop(
        op.get_bind(), checkfirst=True
    )
