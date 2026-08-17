"""Align student progression schema with the runtime accounting model.

Revision ID: 20260818_academic_schema_parity
Revises: 20260817_academic_cbt_completion
"""

from alembic import op
import sqlalchemy as sa

revision = "20260818_academic_schema_parity"
down_revision = "20260817_academic_cbt_completion"
branch_labels = None
depends_on = None
SCHEMA = "public"


def upgrade() -> None:
    op.add_column(
        "student_progression_runs",
        sa.Column(
            "pending_students",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema=SCHEMA,
    )

    # Rebuild both accounting constraints so database invariants match the
    # runtime model. Pending students are intentionally counted as processed:
    # the run examined them, but an administrator action is still required.
    op.drop_constraint(
        "ck_progression_run_nonnegative_counts",
        "student_progression_runs",
        type_="check",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "ck_progression_run_count_accounting",
        "student_progression_runs",
        type_="check",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_progression_run_nonnegative_counts",
        "student_progression_runs",
        "promoted_students >= 0 AND graduated_students >= 0 "
        "AND skipped_students >= 0 AND pending_students >= 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_progression_run_count_accounting",
        "student_progression_runs",
        "processed_students = promoted_students + graduated_students "
        "+ skipped_students + pending_students",
        schema=SCHEMA,
    )

    # The default is only needed to make the destructive pre-launch migration
    # safe for any existing development rows; application defaults own new rows.
    op.alter_column(
        "student_progression_runs",
        "pending_students",
        server_default=None,
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260818_academic_schema_parity is intentionally irreversible before launch."
    )
