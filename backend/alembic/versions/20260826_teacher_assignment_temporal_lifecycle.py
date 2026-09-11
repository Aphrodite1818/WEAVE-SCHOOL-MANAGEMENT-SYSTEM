"""Make teacher assignments date-effective and prevent overlapping ownership.

Revision ID: 20260826_teacher_assignment_temporal
Revises: 20260826_curr_subj_lifecycle
Create Date: 2026-08-26

TeacherAssignment is a persistent staffing-history record. Effective dates are the
single source of truth for whether an assignment is scheduled, current, or ended.
This pre-launch cutover removes the persisted is_active flag and rejects overlapping
teacher ownership for the same class and curriculum subject at the database layer.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ExcludeConstraint

revision: str = "teacher_assignment_temporal"
down_revision: Union[str, Sequence[str], None] = "20260826_curr_subj_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    # UUID/date equality and overlap operators need GiST operator classes.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.drop_index(
        "uq_teacher_assignment_active_class_curriculum_subject",
        table_name="teacher_assignments",
        schema=SCHEMA,
    )

    # Reject already-invalid development data explicitly instead of silently
    # choosing one teacher or rewriting historical effective ranges.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.teacher_assignments AS left_assignment
                JOIN public.teacher_assignments AS right_assignment
                  ON right_assignment.tenant_id = left_assignment.tenant_id
                 AND right_assignment.class_id = left_assignment.class_id
                 AND right_assignment.curriculum_subject_id = left_assignment.curriculum_subject_id
                 AND right_assignment.id > left_assignment.id
                 AND daterange(
                        left_assignment.effective_from,
                        left_assignment.effective_to,
                        '[]'
                     ) && daterange(
                        right_assignment.effective_from,
                        right_assignment.effective_to,
                        '[]'
                     )
            ) THEN
                RAISE EXCEPTION
                    'teacher_assignments contains overlapping effective ranges; clean development data before migration';
            END IF;
        END $$;
        """
    )

    op.drop_column("teacher_assignments", "is_active", schema=SCHEMA)

    op.create_exclude_constraint(
        "excl_teacher_assignments_effective_overlap",
        "teacher_assignments",
        ("tenant_id", "="),
        ("class_id", "="),
        ("curriculum_subject_id", "="),
        (
            sa.func.daterange(
                sa.column("effective_from"),
                sa.column("effective_to"),
                "[]",
            ),
            "&&",
        ),
        schema=SCHEMA,
        using="gist",
    )

    op.create_index(
        "ix_teacher_assignments_scope_effective_from",
        "teacher_assignments",
        ["tenant_id", "class_id", "curriculum_subject_id", "effective_from"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260826_teacher_assignment_temporal is an intentional pre-launch lifecycle cutover; "
        "restore a pre-migration development database if rollback is required."
    )
