"""merge academic migration heads

Revision ID: 20260703_merge_acad_heads
Revises: 20260702_partial_results, 20260702_subject_identity
Create Date: 2026-07-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "20260703_merge_acad_heads"
down_revision: str | Sequence[str] | None = (
    "20260702_partial_results",
    "20260702_subject_identity",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
