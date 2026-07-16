"""Allow global parent and teacher account sessions.

Revision ID: 4d8a2c1f5b90
Revises: 9c1f2a8e4b77
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op


revision: str = "4d8a2c1f5b90"
down_revision: Union[str, Sequence[str], None] = "9c1f2a8e4b77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE public.auth_session_actor_type ADD VALUE IF NOT EXISTS 'teacher_account'")
    op.execute("ALTER TYPE public.auth_session_actor_type ADD VALUE IF NOT EXISTS 'parent_account'")
    op.execute("COMMIT")
    op.drop_constraint(
        "ck_auth_sessions_tenant_scope",
        "auth_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_sessions_tenant_scope",
        "auth_sessions",
        """
        (
            actor_type = 'superadmin'
            AND tenant_id IS NULL
        )
        OR
        (
            actor_type IN ('teacher_account', 'parent_account')
            AND tenant_id IS NULL
        )
        OR
        (
            actor_type NOT IN ('superadmin', 'teacher_account', 'parent_account')
            AND tenant_id IS NOT NULL
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_auth_sessions_tenant_scope",
        "auth_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_auth_sessions_tenant_scope",
        "auth_sessions",
        """
        (
            actor_type = 'superadmin'
            AND tenant_id IS NULL
        )
        OR
        (
            actor_type <> 'superadmin'
            AND tenant_id IS NOT NULL
        )
        """,
    )
