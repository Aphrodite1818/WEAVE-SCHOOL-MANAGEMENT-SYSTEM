"""Fresh Weave schema baseline for the pre-customer reset.

Revision ID: 20260811_fresh_schema
Revises:
Create Date: 2026-08-11

This revision intentionally assumes an empty/reset PostgreSQL database. During
the current pre-customer phase, development, staging, and production databases
are disposable and are rebuilt from the current canonical SQLAlchemy model
registry instead of carrying transitional migration compatibility forward.
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.shared.base_model import Base

revision: str = "20260811_fresh_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the complete current Weave schema on an empty database."""

    configure_mappers()
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Drop the application schema objects created by this fresh baseline."""

    configure_mappers()
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
