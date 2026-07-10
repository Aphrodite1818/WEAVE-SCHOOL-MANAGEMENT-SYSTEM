"""merge migration heads

Revision ID: 644a6ebe31fe
Revises: 20260710_add_security_ip_blocks, baab99922911
Create Date: 2026-07-10 12:02:51.420886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '644a6ebe31fe'
down_revision: Union[str, Sequence[str], None] = ('20260710_add_security_ip_blocks', 'baab99922911')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
