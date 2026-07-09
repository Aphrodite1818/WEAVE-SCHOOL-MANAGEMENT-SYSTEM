"""merge migration heads

Revision ID: 6b04beff875a
Revises: 20260708_normalize_classrooms, 5ea27fc0475b
Create Date: 2026-07-09 13:00:50.663541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b04beff875a'
down_revision: Union[str, Sequence[str], None] = ('20260708_normalize_classrooms', '5ea27fc0475b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
