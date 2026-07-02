"""enforce one active teacher assignment per class subject

Revision ID: 20260702_teacher_assignment_unique
Revises: 20260702_academic_consolidation
Create Date: 2026-07-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260702_teacher_assignment_unique"
down_revision: Union[str, Sequence[str], None] = "20260702_academic_consolidation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize any bad active duplicates before enforcing the real invariant.
    # Keep the newest active assignment per class-subject and retire older active rows.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY class_subject_id
                    ORDER BY created_at DESC, id DESC
                ) AS row_number
            FROM teacher_assignments
            WHERE is_active = true
        )
        UPDATE teacher_assignments AS teacher_assignment
        SET
            is_active = false,
            effective_to = COALESCE(teacher_assignment.effective_to, CURRENT_DATE),
            updated_at = now()
        FROM ranked
        WHERE teacher_assignment.id = ranked.id
          AND ranked.row_number > 1
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_teacher_assignment_active_class_subject_teacher")
    op.create_index(
        "uq_teacher_assignment_active_class_subject",
        "teacher_assignments",
        ["class_subject_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_teacher_assignment_active_class_subject",
        table_name="teacher_assignments",
    )
    op.create_index(
        "uq_teacher_assignment_active_class_subject_teacher",
        "teacher_assignments",
        ["class_subject_id", "teacher_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
