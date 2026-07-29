"""Add assessment configuration, assignment audit, and result constraints.

Revision ID: 270287aab63d
Revises: 20260727_academic_lifecycle
Create Date: 2026-07-27 16:19:20.026144
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "270287aab63d"
down_revision: str | Sequence[str] | None = "20260727_academic_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "public"


def _constraint_names(inspector, table_name: str) -> set[str]:
    names = {
        item.get("name")
        for item in inspector.get_check_constraints(table_name, schema=SCHEMA)
    }
    names.update(
        item.get("name")
        for item in inspector.get_unique_constraints(table_name, schema=SCHEMA)
    )
    return {name for name in names if name}


def _index_names(inspector, table_name: str) -> set[str]:
    return {
        item.get("name")
        for item in inspector.get_indexes(table_name, schema=SCHEMA)
        if item.get("name")
    }


def _create_school_assessment_configs() -> None:
    op.create_table(
        "school_assessment_configs",
        sa.Column("test_max", sa.Integer(), server_default="20", nullable=False),
        sa.Column(
            "assessment_max",
            sa.Integer(),
            server_default="20",
            nullable=False,
        ),
        sa.Column("exam_max", sa.Integer(), server_default="60", nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "test_max + assessment_max + exam_max = 100",
            name="ck_school_assessment_config_total",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            name="uq_school_assessment_config_tenant",
        ),
        schema=SCHEMA,
    )


def _create_teacher_assignment_lifecycle_audits() -> None:
    op.create_table(
        "teacher_assignment_lifecycle_audits",
        sa.Column("assignment_id", sa.UUID(), nullable=True),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("previous_teacher_membership_id", sa.UUID(), nullable=True),
        sa.Column("new_teacher_membership_id", sa.UUID(), nullable=True),
        sa.Column("previous_state", sa.String(length=30), nullable=True),
        sa.Column("new_state", sa.String(length=30), nullable=True),
        sa.Column("previous_effective_from", sa.Date(), nullable=True),
        sa.Column("previous_effective_to", sa.Date(), nullable=True),
        sa.Column("new_effective_from", sa.Date(), nullable=True),
        sa.Column("new_effective_to", sa.Date(), nullable=True),
        sa.Column("acting_admin_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["acting_admin_id"],
            ["public.tenant_admins.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["public.teacher_assignments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["class_subject_id"],
            ["public.class_subjects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["new_teacher_membership_id"],
            ["public.teacher_memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["previous_teacher_membership_id"],
            ["public.teacher_memberships.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_public_teacher_assignment_lifecycle_audits_assignment_id",
        "teacher_assignment_lifecycle_audits",
        ["assignment_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_public_teacher_assignment_lifecycle_audits_class_subject_id",
        "teacher_assignment_lifecycle_audits",
        ["class_subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_assignment_lifecycle_audits_tenant_assignment",
        "teacher_assignment_lifecycle_audits",
        ["tenant_id", "assignment_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_assignment_lifecycle_audits_tenant_class_subject",
        "teacher_assignment_lifecycle_audits",
        ["tenant_id", "class_subject_id"],
        schema=SCHEMA,
    )


def _ensure_student_result_constraints(inspector) -> None:
    table_name = "student_subject_results"
    if not inspector.has_table(table_name, schema=SCHEMA):
        raise RuntimeError(
            "student_subject_results must exist before applying revision 270287aab63d"
        )

    columns = {
        item["name"] for item in inspector.get_columns(table_name, schema=SCHEMA)
    }
    required_columns = {
        "tenant_id",
        "student_id",
        "class_subject_teacher_id",
        "academic_session_id",
        "academic_term_id",
        "status",
        "submitted_at",
        "submitted_by_actor_type",
        "submitted_by_actor_id",
        "total_score",
        "grade",
        "grading_scale_id",
        "approved_at",
        "approved_by_admin_id",
        "locked_at",
        "locked_by_admin_id",
    }
    missing_columns = sorted(required_columns - columns)
    if missing_columns:
        raise RuntimeError(
            "student_subject_results is missing required columns: "
            + ", ".join(missing_columns)
        )

    constraints = _constraint_names(inspector, table_name)
    if "uq_student_subject_result_scope" not in constraints:
        op.create_unique_constraint(
            "uq_student_subject_result_scope",
            table_name,
            [
                "tenant_id",
                "student_id",
                "class_subject_teacher_id",
                "academic_session_id",
                "academic_term_id",
            ],
            schema=SCHEMA,
        )
    if "ck_student_subject_results_submitted_metadata" not in constraints:
        op.create_check_constraint(
            "ck_student_subject_results_submitted_metadata",
            table_name,
            "status = 'draft' OR "
            "(submitted_at IS NOT NULL AND submitted_by_actor_type IS NOT NULL "
            "AND submitted_by_actor_id IS NOT NULL)",
            schema=SCHEMA,
        )
    if "ck_student_subject_results_completeness" not in constraints:
        op.create_check_constraint(
            "ck_student_subject_results_completeness",
            table_name,
            "status = 'draft' OR "
            "(total_score IS NOT NULL AND grade IS NOT NULL "
            "AND grading_scale_id IS NOT NULL)",
            schema=SCHEMA,
        )
    if "ck_student_subject_results_approved_metadata" not in constraints:
        op.create_check_constraint(
            "ck_student_subject_results_approved_metadata",
            table_name,
            "status NOT IN ('approved', 'locked') OR "
            "(approved_at IS NOT NULL AND approved_by_admin_id IS NOT NULL)",
            schema=SCHEMA,
        )
    if "ck_student_subject_results_locked_metadata" not in constraints:
        op.create_check_constraint(
            "ck_student_subject_results_locked_metadata",
            table_name,
            "status <> 'locked' OR "
            "(locked_at IS NOT NULL AND locked_by_admin_id IS NOT NULL)",
            schema=SCHEMA,
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("school_assessment_configs", schema=SCHEMA):
        _create_school_assessment_configs()
    if not inspector.has_table(
        "teacher_assignment_lifecycle_audits",
        schema=SCHEMA,
    ):
        _create_teacher_assignment_lifecycle_audits()

    inspector = sa.inspect(bind)
    _ensure_student_result_constraints(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("student_subject_results", schema=SCHEMA):
        constraint_names = _constraint_names(inspector, "student_subject_results")
        for constraint_name in (
            "ck_student_subject_results_locked_metadata",
            "ck_student_subject_results_approved_metadata",
            "ck_student_subject_results_completeness",
            "ck_student_subject_results_submitted_metadata",
            "uq_student_subject_result_scope",
        ):
            if constraint_name in constraint_names:
                constraint_type = (
                    "unique"
                    if constraint_name == "uq_student_subject_result_scope"
                    else "check"
                )
                op.drop_constraint(
                    constraint_name,
                    "student_subject_results",
                    schema=SCHEMA,
                    type_=constraint_type,
                )

    inspector = sa.inspect(bind)
    if inspector.has_table(
        "teacher_assignment_lifecycle_audits",
        schema=SCHEMA,
    ):
        op.drop_table("teacher_assignment_lifecycle_audits", schema=SCHEMA)
    if inspector.has_table("school_assessment_configs", schema=SCHEMA):
        op.drop_table("school_assessment_configs", schema=SCHEMA)
