"""Add ArmLabel archive actor metadata and lifecycle constraint.

Revision ID: 20260826_arm_label_lifecycle
Revises: 20260826_dept_archive_meta
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260826_arm_label_lifecycle"
down_revision: Union[str, Sequence[str], None] = "20260826_dept_archive_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.add_column(
        "arm_labels",
        sa.Column("archived_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_arm_labels_archived_by_admin_id_tenant_admins",
        "arm_labels",
        "tenant_admins",
        ["archived_by_admin_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="SET NULL",
    )
    op.execute(
        "ALTER TABLE public.arm_labels "
        "DROP CONSTRAINT IF EXISTS ck_arm_labels_archived_requires_inactive"
    )
    op.create_check_constraint(
        "ck_arm_labels_archive_metadata_consistency",
        "arm_labels",
        """
        (archived_at IS NULL AND archived_by_admin_id IS NULL)
        OR (archived_at IS NOT NULL AND is_active = false)
        """,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_arm_labels_archive_metadata_consistency",
        "arm_labels",
        type_="check",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_arm_labels_archived_requires_inactive",
        "arm_labels",
        "archived_at IS NULL OR is_active = false",
        schema=SCHEMA,
    )
    op.drop_constraint(
        "fk_arm_labels_archived_by_admin_id_tenant_admins",
        "arm_labels",
        type_="foreignkey",
        schema=SCHEMA,
    )
    op.drop_column("arm_labels", "archived_by_admin_id", schema=SCHEMA)
