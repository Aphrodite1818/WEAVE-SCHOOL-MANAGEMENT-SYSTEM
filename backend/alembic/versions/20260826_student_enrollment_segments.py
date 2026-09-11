"""Make student enrollments the sole immutable placement authority.

Revision ID: student_enrollment_segments
Revises: teacher_assignment_temporal
Create Date: 2026-08-26

This pre-launch cutover removes the duplicated students.class_id pointer and the
persisted student_enrollments.is_current flag. Enrollment rows become immutable
placement segments with explicit entry/exit metadata and non-overlapping date
ranges.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "student_enrollment_segments"
down_revision: Union[str, Sequence[str], None] = "teacher_assignment_temporal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("ALTER TYPE public.student_enrollment_outcome ADD VALUE IF NOT EXISTS 'demoted'")
    op.execute("ALTER TYPE public.student_enrollment_outcome ADD VALUE IF NOT EXISTS 'reinstated'")

    # Enrollment metadata: preserve the existing entry information before
    # introducing explicit exit metadata.
    op.alter_column(
        "student_enrollments",
        "outcome",
        new_column_name="entry_outcome",
        schema=SCHEMA,
    )
    op.alter_column(
        "student_enrollments",
        "reason",
        new_column_name="entry_reason",
        schema=SCHEMA,
    )
    op.alter_column(
        "student_enrollments",
        "changed_by_admin_id",
        new_column_name="created_by_admin_id",
        schema=SCHEMA,
    )
    enrollment_outcome = sa.Enum(
        "enrolled",
        "promoted",
        "repeated",
        "demoted",
        "reclassified",
        "reinstated",
        "withdrawn",
        "expelled",
        "graduated",
        name="student_enrollment_outcome",
        schema=SCHEMA,
        create_type=False,
    )
    op.add_column(
        "student_enrollments",
        sa.Column("exit_outcome", enrollment_outcome, nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "student_enrollments",
        sa.Column("exit_reason", sa.String(length=500), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "student_enrollments",
        sa.Column(
            "ended_by_admin_id",
            sa.UUID(),
            sa.ForeignKey("public.tenant_admins.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    # Existing ended rows used the single outcome/reason pair as their final
    # lifecycle event, so preserve it as exit metadata too.
    op.execute(
        """
        UPDATE public.student_enrollments
        SET exit_outcome = entry_outcome,
            exit_reason = COALESCE(entry_reason, 'Enrollment ended before segment cutover'),
            ended_by_admin_id = created_by_admin_id
        WHERE ended_on IS NOT NULL
        """
    )

    op.drop_constraint(
        "ck_student_enrollment_current_end_consistency",
        "student_enrollments",
        schema=SCHEMA,
        type_="check",
    )
    op.drop_index(
        "uq_student_enrollments_one_current",
        table_name="student_enrollments",
        schema=SCHEMA,
    )
    op.drop_column("student_enrollments", "is_current", schema=SCHEMA)

    op.create_check_constraint(
        "ck_student_enrollment_exit_consistency",
        "student_enrollments",
        """
        (
            ended_on IS NULL
            AND exit_outcome IS NULL
            AND exit_reason IS NULL
            AND ended_by_admin_id IS NULL
        )
        OR
        (
            ended_on IS NOT NULL
            AND exit_outcome IS NOT NULL
            AND exit_reason IS NOT NULL
        )
        """,
        schema=SCHEMA,
    )
    op.create_index(
        "uq_student_enrollments_one_current",
        "student_enrollments",
        ["tenant_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("ended_on IS NULL"),
        schema=SCHEMA,
    )

    # Reject invalid history rather than silently rewriting overlapping segments.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.student_enrollments AS left_enrollment
                JOIN public.student_enrollments AS right_enrollment
                  ON right_enrollment.tenant_id = left_enrollment.tenant_id
                 AND right_enrollment.student_id = left_enrollment.student_id
                 AND right_enrollment.id > left_enrollment.id
                 AND daterange(left_enrollment.started_on, left_enrollment.ended_on, '[]')
                     && daterange(right_enrollment.started_on, right_enrollment.ended_on, '[]')
            ) THEN
                RAISE EXCEPTION
                    'student_enrollments contains overlapping placement ranges; clean development data before migration';
            END IF;
        END $$;
        """
    )
    op.create_exclude_constraint(
        "excl_student_enrollments_effective_overlap",
        "student_enrollments",
        ("tenant_id", "="),
        ("student_id", "="),
        (
            sa.func.daterange(
                sa.column("started_on"),
                sa.column("ended_on"),
                "[]",
            ),
            "&&",
        ),
        schema=SCHEMA,
        using="gist",
    )

    # StudentEnrollment is now the only persisted class-placement authority.
    op.drop_constraint(
        "ck_students_terminal_status_has_no_current_class",
        "students",
        schema=SCHEMA,
        type_="check",
    )
    op.drop_index("ix_students_tenant_class_status_archived", table_name="students", schema=SCHEMA)
    op.drop_index("ix_students_tenant_class", table_name="students", schema=SCHEMA)
    op.drop_constraint("students_class_id_fkey", "students", schema=SCHEMA, type_="foreignkey")
    op.drop_column("students", "class_id", schema=SCHEMA)


def downgrade() -> None:
    raise RuntimeError(
        "student_enrollment_segments is an intentional pre-launch authority cutover; "
        "restore a pre-migration development database if rollback is required."
    )
