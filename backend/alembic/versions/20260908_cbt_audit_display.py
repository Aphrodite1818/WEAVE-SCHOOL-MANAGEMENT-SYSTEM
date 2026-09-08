"""Add human-facing CBT result-ingestion audit metadata.

Revision ID: 20260908_cbt_audit_display
Revises: 20260908_cbt_result_ingestion
Create Date: 2026-09-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_cbt_audit_display"
down_revision: Union[str, Sequence[str], None] = "20260908_cbt_result_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cbt_result_ingestion_batches",
        sa.Column("ingestion_reference", sa.String(length=32), nullable=True),
        schema="public",
    )
    op.add_column(
        "cbt_result_ingestion_batches",
        sa.Column("source_exam_title", sa.String(length=200), nullable=True),
        schema="public",
    )

    op.execute(
        sa.text(
            """
            UPDATE public.cbt_result_ingestion_batches
            SET ingestion_reference =
                'CBT-' || EXTRACT(YEAR FROM created_at)::int::text || '-' ||
                UPPER(SUBSTRING(REPLACE(id::text, '-', '') FROM 1 FOR 16))
            WHERE ingestion_reference IS NULL
            """
        )
    )

    op.alter_column(
        "cbt_result_ingestion_batches",
        "ingestion_reference",
        nullable=False,
        schema="public",
    )
    op.create_unique_constraint(
        "uq_cbt_result_ingestion_tenant_reference",
        "cbt_result_ingestion_batches",
        ["tenant_id", "ingestion_reference"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cbt_result_ingestion_tenant_reference",
        "cbt_result_ingestion_batches",
        type_="unique",
        schema="public",
    )
    op.drop_column(
        "cbt_result_ingestion_batches",
        "source_exam_title",
        schema="public",
    )
    op.drop_column(
        "cbt_result_ingestion_batches",
        "ingestion_reference",
        schema="public",
    )
