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


def _academic_term_session_foreign_key(inspector) -> dict | None:
    for foreign_key in inspector.get_foreign_keys("academic_terms", schema="public"):
        if foreign_key.get("constrained_columns") == ["academic_session_id"]:
            return foreign_key
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("academic_lifecycle_audits", schema="public"):
        op.create_table(
            "academic_lifecycle_audits",
            sa.Column("entity_type", sa.String(length=20), nullable=False),
            sa.Column("entity_id", sa.UUID(), nullable=False),
            sa.Column("action", sa.String(length=60), nullable=False),
            sa.Column("previous_status", sa.String(length=30), nullable=True),
            sa.Column("new_status", sa.String(length=30), nullable=True),
            sa.Column("acting_admin_id", sa.UUID(), nullable=True),
            sa.Column("reason", sa.String(length=500), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["acting_admin_id"],
                ["public.tenant_admins.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"],
                ["public.tenants.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            schema="public",
        )
        op.create_index(
            "ix_academic_lifecycle_audits_tenant_entity",
            "academic_lifecycle_audits",
            ["tenant_id", "entity_type", "entity_id"],
            schema="public",
        )
        op.create_index(
            "ix_academic_lifecycle_audits_tenant_action",
            "academic_lifecycle_audits",
            ["tenant_id", "action"],
            schema="public",
        )
        op.create_index(
            "ix_public_academic_lifecycle_audits_entity_id",
            "academic_lifecycle_audits",
            ["entity_id"],
            schema="public",
        )

    inspector = sa.inspect(bind)
    foreign_key = _academic_term_session_foreign_key(inspector)
    options = (foreign_key or {}).get("options") or {}
    if str(options.get("ondelete") or "").upper() != "RESTRICT":
        if foreign_key and foreign_key.get("name"):
            op.drop_constraint(
                foreign_key["name"],
                "academic_terms",
                schema="public",
                type_="foreignkey",
            )
        op.create_foreign_key(
            "academic_terms_academic_session_id_fkey",
            "academic_terms",
            "academic_sessions",
            ["academic_session_id"],
            ["id"],
            source_schema="public",
            referent_schema="public",
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    foreign_key = _academic_term_session_foreign_key(inspector)
    if foreign_key and foreign_key.get("name"):
        op.drop_constraint(
            foreign_key["name"],
            "academic_terms",
            schema="public",
            type_="foreignkey",
        )
    op.create_foreign_key(
        "academic_terms_academic_session_id_fkey",
        "academic_terms",
        "academic_sessions",
        ["academic_session_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )

    inspector = sa.inspect(bind)
    if inspector.has_table("academic_lifecycle_audits", schema="public"):
        op.drop_table("academic_lifecycle_audits", schema="public")
