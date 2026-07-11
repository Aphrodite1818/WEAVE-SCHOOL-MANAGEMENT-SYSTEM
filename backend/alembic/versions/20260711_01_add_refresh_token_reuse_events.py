"""add append-only refresh token reuse events

Revision ID: 20260711_refresh_reuse_events
Revises: 20260710_optimize_model_indexes
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260711_refresh_reuse_events"
down_revision: str | Sequence[str] | None = "20260710_optimize_model_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_refresh_token_reuse_events",
        sa.Column("refresh_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["refresh_token_id"], ["public.auth_refresh_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["public.auth_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema="public",
    )
    op.create_index("ix_auth_refresh_token_reuse_events_refresh_token_id", "auth_refresh_token_reuse_events", ["refresh_token_id"], schema="public")
    op.create_index("ix_auth_refresh_token_reuse_events_session_id", "auth_refresh_token_reuse_events", ["session_id"], schema="public")
    op.create_index("ix_auth_refresh_token_reuse_events_detected_at", "auth_refresh_token_reuse_events", ["detected_at"], schema="public")
    op.create_index("ix_auth_refresh_token_reuse_events_window", "auth_refresh_token_reuse_events", ["detected_at", "id"], schema="public")


def downgrade() -> None:
    op.drop_index("ix_auth_refresh_token_reuse_events_window", table_name="auth_refresh_token_reuse_events", schema="public")
    op.drop_index("ix_auth_refresh_token_reuse_events_detected_at", table_name="auth_refresh_token_reuse_events", schema="public")
    op.drop_index("ix_auth_refresh_token_reuse_events_session_id", table_name="auth_refresh_token_reuse_events", schema="public")
    op.drop_index("ix_auth_refresh_token_reuse_events_refresh_token_id", table_name="auth_refresh_token_reuse_events", schema="public")
    op.drop_table("auth_refresh_token_reuse_events", schema="public")
