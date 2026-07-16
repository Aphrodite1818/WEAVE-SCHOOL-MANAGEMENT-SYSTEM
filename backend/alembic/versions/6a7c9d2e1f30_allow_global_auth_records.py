"""Allow tenantless auth records for global account OTPs.

Revision ID: 6a7c9d2e1f30
Revises: 4d8a2c1f5b90
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7c9d2e1f30"
down_revision: Union[str, Sequence[str], None] = "4d8a2c1f5b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "auth",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=True,
        schema="public",
    )


def downgrade() -> None:
    op.alter_column(
        "auth",
        "tenant_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema="public",
    )
