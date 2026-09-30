"""add assessment component examinability

Revision ID: 20260930_component_examinable
Revises: 20260930_cbt_actor_auth
Create Date: 2026-09-30 23:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_component_examinable"
down_revision: Union[str, Sequence[str], None] = "20260930_cbt_actor_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing assessment components historically flowed to CBT, so defaulting
    # to true preserves deployed behaviour. Schools opt manual components out.
    op.add_column(
        "assessment_components",
        sa.Column(
            "is_examinable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column(
        "assessment_components",
        "is_examinable",
        schema="public",
    )
