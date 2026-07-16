"""Create the complete Weave database schema from current ORM metadata.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-07-16

This migration is intentionally a clean-slate baseline. It assumes the target
PostgreSQL database is empty. Existing databases must be recreated before this
migration is applied.
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

from app.modules import import_model_modules
from app.shared.base_model import Base

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create every table, enum, constraint, and index in dependency order."""

    import_model_modules()
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=False)


def downgrade() -> None:
    """Drop the complete schema represented by the current ORM metadata."""

    import_model_modules()
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=False)
