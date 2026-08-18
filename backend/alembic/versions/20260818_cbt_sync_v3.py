"""Cut durable CBT synchronization metadata to the v3 contract.

Revision ID: 20260818_cbt_sync_v3
Revises: 20260818_academic_schema_parity
"""

from alembic import op

revision = "20260818_cbt_sync_v3"
down_revision = "20260818_academic_schema_parity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.cbt_sync_changes "
        "ALTER COLUMN schema_version SET DEFAULT 3"
    )


def downgrade() -> None:
    raise RuntimeError("CBT sync v3 is intentionally irreversible before launch.")
