"""add auth sessions and refresh tokens

Revision ID: 770a510b8cf9
Revises: 6b04beff875a
Create Date: 2026-07-09 13:01:17.279109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '770a510b8cf9'
down_revision: Union[str, Sequence[str], None] = '6b04beff875a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
