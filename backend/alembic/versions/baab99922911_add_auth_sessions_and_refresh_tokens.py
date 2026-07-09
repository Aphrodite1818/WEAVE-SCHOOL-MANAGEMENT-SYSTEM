"""add auth sessions and refresh tokens

Revision ID: baab99922911
Revises: 770a510b8cf9
Create Date: 2026-07-09 13:03:18.173399

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "baab99922911"
down_revision: Union[str, Sequence[str], None] = "770a510b8cf9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA_NAME = "public"

AUTH_SESSION_ACTOR_TYPE_ENUM_NAME = "auth_session_actor_type"

AUTH_SESSION_ACTOR_TYPE_VALUES = (
    "superadmin",
    "tenant_admin",
    "teacher",
    "staff",
    "parent",
    "student",
)


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name, schema=SCHEMA_NAME)


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = inspector.get_indexes(table_name, schema=SCHEMA_NAME)
    return any(index["name"] == index_name for index in indexes)


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if not _index_exists(table_name=table_name, index_name=index_name):
        op.create_index(
            index_name,
            table_name,
            columns,
            unique=False,
            schema=SCHEMA_NAME,
        )


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    auth_session_actor_type = postgresql.ENUM(
        *AUTH_SESSION_ACTOR_TYPE_VALUES,
        name=AUTH_SESSION_ACTOR_TYPE_ENUM_NAME,
        schema=SCHEMA_NAME,
    )
    auth_session_actor_type.create(bind, checkfirst=True)

    if not _table_exists("auth_sessions"):
        op.create_table(
            "auth_sessions",
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("public.tenants.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "actor_type",
                postgresql.ENUM(
                    *AUTH_SESSION_ACTOR_TYPE_VALUES,
                    name=AUTH_SESSION_ACTOR_TYPE_ENUM_NAME,
                    schema=SCHEMA_NAME,
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column(
                "actor_id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "session_jti",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "user_agent",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "ip_address",
                sa.String(length=45),
                nullable=True,
            ),
            sa.Column(
                "remember_me",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
            sa.Column(
                "last_used_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "revoked_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoked_reason",
                sa.String(length=100),
                nullable=True,
            ),
            sa.Column(
                "compromised_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
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
                name="ck_auth_sessions_tenant_scope",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_jti", name="uq_auth_sessions_session_jti"),
            schema=SCHEMA_NAME,
        )

    if not _table_exists("auth_refresh_tokens"):
        op.create_table(
            "auth_refresh_tokens",
            sa.Column(
                "session_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("public.auth_sessions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "token_hash",
                sa.String(length=255),
                nullable=False,
            ),
            sa.Column(
                "token_jti",
                sa.String(length=64),
                nullable=False,
            ),
            sa.Column(
                "issued_ip_address",
                sa.String(length=45),
                nullable=True,
            ),
            sa.Column(
                "issued_user_agent",
                sa.Text(),
                nullable=True,
            ),
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column(
                "used_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoked_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "revoked_reason",
                sa.String(length=100),
                nullable=True,
            ),
            sa.Column(
                "replaced_by_token_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(
                    "public.auth_refresh_tokens.id",
                    ondelete="SET NULL",
                ),
                nullable=True,
            ),
            sa.Column(
                "reuse_detected_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
            sa.UniqueConstraint("token_jti", name="uq_auth_refresh_tokens_token_jti"),
            schema=SCHEMA_NAME,
        )

    _create_index_if_missing(
        "ix_auth_sessions_tenant_id",
        "auth_sessions",
        ["tenant_id"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_actor_type",
        "auth_sessions",
        ["actor_type"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_actor_id",
        "auth_sessions",
        ["actor_id"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_session_jti",
        "auth_sessions",
        ["session_jti"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_expires_at",
        "auth_sessions",
        ["expires_at"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_revoked_at",
        "auth_sessions",
        ["revoked_at"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_actor",
        "auth_sessions",
        ["actor_type", "actor_id"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_tenant_actor",
        "auth_sessions",
        ["tenant_id", "actor_type", "actor_id"],
    )
    _create_index_if_missing(
        "ix_auth_sessions_active_lookup",
        "auth_sessions",
        ["actor_type", "actor_id", "revoked_at", "expires_at"],
    )

    _create_index_if_missing(
        "ix_auth_refresh_tokens_session_id",
        "auth_refresh_tokens",
        ["session_id"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_token_hash",
        "auth_refresh_tokens",
        ["token_hash"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_token_jti",
        "auth_refresh_tokens",
        ["token_jti"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_expires_at",
        "auth_refresh_tokens",
        ["expires_at"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_revoked_at",
        "auth_refresh_tokens",
        ["revoked_at"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_session_active",
        "auth_refresh_tokens",
        ["session_id", "revoked_at", "expires_at"],
    )
    _create_index_if_missing(
        "ix_auth_refresh_tokens_rotation_state",
        "auth_refresh_tokens",
        ["session_id", "used_at", "revoked_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_rotation_state")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_session_active")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_revoked_at")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_expires_at")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_token_jti")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_token_hash")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_refresh_tokens_session_id")

    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_active_lookup")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_tenant_actor")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_actor")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_revoked_at")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_expires_at")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_session_jti")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_actor_id")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_actor_type")
    op.execute("DROP INDEX IF EXISTS public.ix_auth_sessions_tenant_id")

    op.execute("DROP TABLE IF EXISTS public.auth_refresh_tokens")
    op.execute("DROP TABLE IF EXISTS public.auth_sessions")

    auth_session_actor_type = postgresql.ENUM(
        *AUTH_SESSION_ACTOR_TYPE_VALUES,
        name=AUTH_SESSION_ACTOR_TYPE_ENUM_NAME,
        schema=SCHEMA_NAME,
    )
    auth_session_actor_type.drop(op.get_bind(), checkfirst=True)