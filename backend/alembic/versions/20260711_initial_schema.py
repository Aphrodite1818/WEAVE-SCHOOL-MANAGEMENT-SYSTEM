"""Create the complete Weave database schema from current ORM metadata.

Revision ID: 20260711_initial_schema
Revises: None
Create Date: 2026-07-16

This migration is intentionally a clean-slate baseline. It assumes the target
PostgreSQL database is empty. Existing databases must be recreated before this
migration is applied.
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.shared.base_model import Base

revision: str = "20260711_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _load_schema_metadata() -> None:
    """Import all models and validate ORM mappings before running DDL."""

    
    configure_mappers()


def upgrade() -> None:
    """Create every table, enum, constraint, and index in dependency order."""

    _load_schema_metadata()
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Drop every application table represented by the current ORM metadata."""

    _load_schema_metadata()
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
