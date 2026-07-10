"""Bridge the legacy staging chain into the current baseline.

Revision ID: 1db81d711bbc
Revises:
Create Date: 2026-06-30 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence


revision: str = "1db81d711bbc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op bridge revision.

    This revision intentionally performs no schema changes. It exists only to
    preserve the legacy staging Alembic chain as an explicit baseline root.
    """


def downgrade() -> None:
    """No-op downgrade for the bridge revision."""
