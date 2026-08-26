"""Add Department archive actor metadata.

Revision ID: 20260826_dept_archive_meta
Revises: 20260825_level_status
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260826_dept_archive_meta"
down_revision: Union[str, Sequence[str], None] = "20260825_level_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.add_column(
        "departments",
        sa.Column("archived_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_departments_archived_by_admin_id_tenant_admins",
        "departments",
        "tenant_admins",
        ["archived_by_admin_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    op.execute(
        "ALTER TABLE public.departments "
        "DROP CONSTRAINT IF EXISTS ck_departments_archived_requires_inactive"
    )
    op.create_check_constraint(
        "ck_departments_archive_metadata_consistency",
        "departments",
        """
        (archived_at IS NULL AND archived_by_admin_id IS NULL)
        OR (archived_at IS NOT NULL AND is_active = false)
        """,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_departments_archive_metadata_consistency",
        "departments",
        type_="check",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_departments_archived_requires_inactive",
        "departments",
        "archived_at IS NULL OR is_active = false",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_departments_archived_by_admin_id_tenant_admins",
        "departments",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_column("departments", "archived_by_admin_id", schema=SCHEMA)
