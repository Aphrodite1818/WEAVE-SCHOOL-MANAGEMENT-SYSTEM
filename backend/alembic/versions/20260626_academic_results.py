"""academic results and report cards (legacy revision stub)

Revision ID: 20260626_academic_results_report_cards
Revises: 20260630_add_auth_identities
Create Date: 2026-06-26 00:00:00.000000

This revision existed on deployed databases before the consolidation branch.
The schema it introduced is covered by the staging baseline; this stub restores
Alembic history continuity only.

"""

from typing import Sequence, Union

revision: str = "20260626_academic_results"
down_revision: Union[str, Sequence[str], None] = "20260630_add_auth_identities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
