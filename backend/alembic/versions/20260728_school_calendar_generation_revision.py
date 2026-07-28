"""Add calendar generation revision tracking.

Revision ID: 20260728_calendar_revision
Revises: 20260728_school_calendar
Create Date: 2026-07-28
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_calendar_revision"
down_revision: str | Sequence[str] | None = "20260728_school_calendar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "school_calendar_configurations",
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        schema="public",
    )
    op.add_column(
        "school_calendars",
        sa.Column("generated_from_configuration_revision", sa.Integer(), nullable=True),
        schema="public",
    )
    op.execute(
        """
        UPDATE public.school_calendars AS calendar
        SET generated_from_configuration_revision = config.revision
        FROM public.school_calendar_configurations AS config
        WHERE calendar.tenant_id = config.tenant_id
          AND calendar.generated_at IS NOT NULL
          AND calendar.generated_from_configuration_revision IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("school_calendars", "generated_from_configuration_revision", schema="public")
    op.drop_column("school_calendar_configurations", "revision", schema="public")
