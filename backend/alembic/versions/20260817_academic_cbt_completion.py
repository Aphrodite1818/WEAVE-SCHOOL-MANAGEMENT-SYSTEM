"""Finish academic lifecycle and CBT sync contract invariants.

Revision ID: 20260817_academic_cbt_completion
Revises: 20260817_academic_cleanup
"""

from alembic import op
import sqlalchemy as sa

revision = "20260817_academic_cbt_completion"
down_revision = "20260817_academic_cleanup"
branch_labels = None
depends_on = None
SCHEMA = "public"


def upgrade() -> None:
    # The worker must be able to prove the administrator explicitly approved
    # terminal graduation without consulting a mutable audit trail.
    op.add_column(
        "student_progression_runs",
        sa.Column(
            "terminal_completion_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema=SCHEMA,
    )

    # PostgreSQL UNIQUE normally treats NULL as distinct. General curriculum
    # offerings use department_id=NULL, so NULLS NOT DISTINCT is required to
    # prevent two canonical General offerings for the same subject and term.
    op.execute(
        "ALTER TABLE public.curriculum_offerings "
        "DROP CONSTRAINT IF EXISTS uq_curriculum_offering_scope"
    )
    op.execute(
        """
        ALTER TABLE public.curriculum_offerings
        ADD CONSTRAINT uq_curriculum_offering_scope
        UNIQUE NULLS NOT DISTINCT (
            tenant_id,
            curriculum_subject_id,
            academic_term_id,
            department_id
        )
        """
    )

    # Bootstrap v2 now includes active tenant administrators so the local CBT
    # snapshot has the complete staff identity set required by the contract.
    op.execute("ALTER TYPE public.cbt_sync_entity_type ADD VALUE IF NOT EXISTS 'admin'")


def downgrade() -> None:
    raise RuntimeError(
        "20260817_academic_cbt_completion is intentionally irreversible before launch."
    )
