"""CBT AI idempotent authoring metadata.

Revision ID: 20261001_cbt_ai_idempotency
Revises: 20260930_component_examinable
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261001_cbt_ai_idempotency"
down_revision: Union[str, Sequence[str], None] = "20260930_component_examinable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cbt_ai_idempotency_records",
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="in_progress",
            nullable=False,
        ),
        sa.Column("reservation_id", sa.UUID(), nullable=True),
        sa.Column("credits_charged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("credits_released", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_detail", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replay_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
            ["reservation_id"],
            ["public.cbt_ai_credit_reservations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "actor_type",
            "actor_id",
            "operation",
            "idempotency_key",
            name="uq_cbt_ai_idempotency_actor_operation_key",
        ),
        schema="public",
    )
    op.create_index(
        "ix_cbt_ai_idempotency_tenant_status",
        "cbt_ai_idempotency_records",
        ["tenant_id", "status", "created_at"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "ix_cbt_ai_idempotency_reservation",
        "cbt_ai_idempotency_records",
        ["reservation_id"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cbt_ai_idempotency_reservation",
        table_name="cbt_ai_idempotency_records",
        schema="public",
    )
    op.drop_index(
        "ix_cbt_ai_idempotency_tenant_status",
        table_name="cbt_ai_idempotency_records",
        schema="public",
    )
    op.drop_table("cbt_ai_idempotency_records", schema="public")
