"""Clean baseline schema for Weave.

This revision intentionally replaces the previous development migration chain.
It is for fresh databases only: drop/recreate or migrate data manually before
using it against an existing database.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

import app.models  # noqa: F401
from app.shared.base_model import Base


revision: str = "20260731_clean_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
