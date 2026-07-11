"""Create the complete Learnly database schema from the current model registry.

Revision ID: 20260711_initial_schema
Revises: None
Create Date: 2026-07-11

This is the new migration baseline after the development database was reset.
All application model modules are imported before creating metadata so every
registered table, constraint, enum, and model-defined index is included.
"""

from __future__ import annotations

from alembic import op

from app.modules import import_model_modules
from app.shared.base_model import Base


revision = "20260711_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables, constraints, enums, and model-defined indexes."""

    import_model_modules()
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=False)


def downgrade() -> None:
    """Drop all application tables represented by the baseline metadata."""

    import_model_modules()
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
