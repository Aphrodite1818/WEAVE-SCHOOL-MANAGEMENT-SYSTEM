"""Align student progression schema with the runtime accounting model.

Revision ID: 20260818_academic_schema_parity
Revises: 20260817_academic_cbt_completion
"""

from alembic import op

revision = "20260818_academic_schema_parity"
down_revision = "20260817_academic_cbt_completion"
branch_labels = None
depends_on = None
SCHEMA = "public"


def upgrade() -> None:
    # Some pre-launch development databases already received this column while
    # the branch was being refactored under an earlier Alembic revision.
    # Converge both those databases and clean databases to the same final shape.
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "ADD COLUMN IF NOT EXISTS pending_students INTEGER DEFAULT 0"
    )
    op.execute(
        "UPDATE public.student_progression_runs "
        "SET pending_students = 0 WHERE pending_students IS NULL"
    )
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "ALTER COLUMN pending_students SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "ALTER COLUMN pending_students SET DEFAULT 0"
    )

    # Rebuild the progression-count constraints so the database matches the
    # current StudentProgressionRun ORM contract. There is intentionally no
    # processed_students column in the v2 model.
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "DROP CONSTRAINT IF EXISTS ck_progression_run_nonnegative_counts"
    )
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "DROP CONSTRAINT IF EXISTS ck_progression_run_count_accounting"
    )
    op.execute(
        "ALTER TABLE public.student_progression_runs "
        "DROP CONSTRAINT IF EXISTS ck_progression_run_count_total"
    )
    op.create_check_constraint(
        "ck_progression_run_nonnegative_counts",
        "student_progression_runs",
        "total_students >= 0 AND promoted_students >= 0 "
        "AND graduated_students >= 0 AND skipped_students >= 0 "
        "AND pending_students >= 0 AND failed_students >= 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_progression_run_count_total",
        "student_progression_runs",
        "promoted_students + graduated_students + skipped_students "
        "+ pending_students + failed_students <= total_students",
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260818_academic_schema_parity is intentionally irreversible before launch."
    )
