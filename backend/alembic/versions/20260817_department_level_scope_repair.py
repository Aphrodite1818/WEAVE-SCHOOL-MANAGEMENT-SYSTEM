"""Repair department uniqueness and level ownership.

Revision ID: 20260817_department_level_scope
Revises: 20260817_curriculum_cutover
"""

from alembic import op
import sqlalchemy as sa


revision = "20260817_department_level_scope"
down_revision = "20260817_curriculum_cutover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pre-v2 departments without a level cannot satisfy the new academic contract.
    # The product has not launched, so remove them instead of preserving ambiguity.
    # Current v2 department references use ON DELETE CASCADE.
    op.execute(sa.text("DELETE FROM public.departments WHERE academic_level_id IS NULL"))

    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_departments_tenant_name'
                      AND conrelid = 'public.departments'::regclass
                ) THEN
                    ALTER TABLE public.departments
                    DROP CONSTRAINT uq_departments_tenant_name;
                END IF;
            END $$;
            """
        )
    )

    op.alter_column(
        "departments",
        "academic_level_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema="public",
    )
    op.create_unique_constraint(
        "uq_departments_tenant_level_name",
        "departments",
        ["tenant_id", "academic_level_id", "normalized_name"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_departments_tenant_level_name",
        "departments",
        type_="unique",
        schema="public",
    )
    op.alter_column(
        "departments",
        "academic_level_id",
        existing_type=sa.UUID(),
        nullable=True,
        schema="public",
    )
    op.create_unique_constraint(
        "uq_departments_tenant_name",
        "departments",
        ["tenant_id", "normalized_name"],
        schema="public",
    )
