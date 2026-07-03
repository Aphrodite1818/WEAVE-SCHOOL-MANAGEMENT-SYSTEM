"""enforce a single active teacher assignment per class subject

Revision ID: 20260702_teacher_assign_active
Revises: 20260702_academic_consolidation
Create Date: 2026-07-02 00:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_teacher_assign_active"
down_revision: Union[str, Sequence[str], None] = "20260702_academic_consolidation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY class_subject_id
                    ORDER BY
                        is_active DESC,
                        effective_from DESC NULLS LAST,
                        created_at DESC,
                        updated_at DESC,
                        id DESC
                ) AS rn
            FROM teacher_assignments
            WHERE is_active = true
        )
        UPDATE teacher_assignments AS ta
        SET is_active = false,
            effective_to = COALESCE(effective_to, CURRENT_DATE)
        FROM ranked
        WHERE ta.id = ranked.id
          AND ranked.rn > 1
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_teacher_assignment_active_class_subject_teacher")
    op.execute("DROP INDEX IF EXISTS uq_teacher_assignment_active_class_subject")
    op.create_index(
        "uq_teacher_assignment_active_class_subject",
        "teacher_assignments",
        ["class_subject_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_teacher_assignment_active_class_subject")
    op.execute("DROP INDEX IF EXISTS uq_teacher_assignment_active_class_subject_teacher")
    op.create_index(
        "uq_teacher_assignment_active_class_subject_teacher",
        "teacher_assignments",
        ["class_subject_id", "teacher_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
