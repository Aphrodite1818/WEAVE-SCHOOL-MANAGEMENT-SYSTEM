"""Add academic lifecycle audit and restrict term deletion.

Revision ID: 20260727_academic_lifecycle
Revises: 20260711_initial_schema
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260727_academic_lifecycle"
down_revision: str | Sequence[str] | None = "20260711_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academic_lifecycle_audits",
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=True),
        sa.Column("acting_admin_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["acting_admin_id"], ["tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_academic_lifecycle_audits_tenant_entity",
        "academic_lifecycle_audits",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.create_index(
        "ix_academic_lifecycle_audits_tenant_action",
        "academic_lifecycle_audits",
        ["tenant_id", "action"],
    )
    op.create_index(
        op.f("ix_academic_lifecycle_audits_entity_id"),
        "academic_lifecycle_audits",
        ["entity_id"],
    )

    op.drop_constraint(
        "academic_terms_academic_session_id_fkey",
        "academic_terms",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "academic_terms_academic_session_id_fkey",
        "academic_terms",
        "academic_sessions",
        ["academic_session_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "academic_terms_academic_session_id_fkey",
        "academic_terms",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "academic_terms_academic_session_id_fkey",
        "academic_terms",
        "academic_sessions",
        ["academic_session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index(op.f("ix_academic_lifecycle_audits_entity_id"), table_name="academic_lifecycle_audits")
    op.drop_index("ix_academic_lifecycle_audits_tenant_action", table_name="academic_lifecycle_audits")
    op.drop_index("ix_academic_lifecycle_audits_tenant_entity", table_name="academic_lifecycle_audits")
    op.drop_table("academic_lifecycle_audits")
