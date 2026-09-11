"""Replace AcademicLevel is_active with explicit status lifecycle.

Revision ID: 20260825_level_status
Revises: 99c9e8ec3bb4
Create Date: 2026-08-25

This is an intentional active-development cleanup. AcademicLevel lifecycle is
now represented only by status; is_active is removed instead of retained as a
compatibility alias.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260825_level_status"
down_revision: Union[str, Sequence[str], None] = "99c9e8ec3bb4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    academic_level_status = postgresql.ENUM(
        "draft",
        "active",
        "inactive",
        "archived",
        name="academic_level_status",
        schema=SCHEMA,
    )
    academic_level_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "academic_levels",
        sa.Column(
            "status",
            postgresql.ENUM(
                "draft",
                "active",
                "inactive",
                "archived",
                name="academic_level_status",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE public.academic_levels
        SET status = CASE
            WHEN archived_at IS NOT NULL THEN 'archived'::public.academic_level_status
            WHEN is_active IS TRUE THEN 'active'::public.academic_level_status
            ELSE 'inactive'::public.academic_level_status
        END
        """
    )
    op.execute(
        "ALTER TABLE public.academic_levels ALTER COLUMN status SET DEFAULT "
        "'draft'::public.academic_level_status"
    )
    op.alter_column("academic_levels", "status", nullable=False, schema=SCHEMA)

    op.execute("DROP INDEX IF EXISTS public.ix_academic_levels_tenant_active")
    op.execute(
        "ALTER TABLE public.academic_levels "
        "DROP CONSTRAINT IF EXISTS ck_academic_levels_archived_requires_inactive"
    )
    op.execute("ALTER TABLE public.academic_levels DROP COLUMN IF EXISTS is_active")

    op.create_check_constraint(
        "ck_academic_levels_archive_metadata_matches_status",
        "academic_levels",
        """
        (status = 'archived' AND archived_at IS NOT NULL)
        OR (status <> 'archived' AND archived_at IS NULL AND archived_by_admin_id IS NULL)
        """,
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_levels_tenant_status",
        "academic_levels",
        ["tenant_id", "status"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_academic_levels_tenant_status", table_name="academic_levels", schema=SCHEMA)
    op.drop_constraint(
        "ck_academic_levels_archive_metadata_matches_status",
        "academic_levels",
        type_="check",
        schema=SCHEMA,
    )
    op.add_column(
        "academic_levels",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE public.academic_levels
        SET is_active = CASE
            WHEN status = 'active'::public.academic_level_status THEN true
            ELSE false
        END
        """
    )
    op.create_check_constraint(
        "ck_academic_levels_archived_requires_inactive",
        "academic_levels",
        "archived_at IS NULL OR is_active = false",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_levels_tenant_active",
        "academic_levels",
        ["tenant_id", "is_active"],
        schema=SCHEMA,
    )
    op.drop_column("academic_levels", "status", schema=SCHEMA)
    postgresql.ENUM(name="academic_level_status", schema=SCHEMA).drop(
        op.get_bind(), checkfirst=True
    )
