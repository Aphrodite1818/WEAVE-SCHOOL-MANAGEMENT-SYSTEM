"""Linearize the level-scoped department constraint cutover.

Revision ID: 20260817_department_level_scope
Revises: 20260817_academic_cleanup

The academic cleanup revision owns the destructive hierarchy cutover. This
revision remains as a stable migration identifier for development databases that
may already have stamped it, while making the graph single-headed and asserting
the final level-scoped department invariant idempotently.
"""

from alembic import op

revision = "20260817_department_level_scope"
down_revision = "20260817_academic_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.departments "
        "DROP CONSTRAINT IF EXISTS uq_departments_tenant_name"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_departments_tenant_level_name'
                  AND conrelid = 'public.departments'::regclass
            ) THEN
                ALTER TABLE public.departments
                ADD CONSTRAINT uq_departments_tenant_level_name
                UNIQUE (tenant_id, academic_level_id, normalized_name);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "The level-scoped academic cutover is intentionally irreversible before launch."
    )
