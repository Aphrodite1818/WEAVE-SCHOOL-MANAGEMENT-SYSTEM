"""Replace announcements feed with canonical communications schema.

Revision ID: 20260731_comms_redesign
Revises: 20260729_deleted_notif_status
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
from sqlalchemy import inspect, text

from app.modules.communications.models import (
    Announcement,
    AnnouncementAudience,
    Conversation,
    ConversationParticipant,
    Message,
    NotificationDelivery,
)

revision: str = "20260731_comms_redesign"
down_revision: str | Sequence[str] | None = "20260729_deleted_notif_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COMMUNICATION_TABLES = [
    Conversation.__table__,
    ConversationParticipant.__table__,
    Message.__table__,
    Announcement.__table__,
    AnnouncementAudience.__table__,
    NotificationDelivery.__table__,
]

OLD_ANNOUNCEMENT_TABLES = [
    "import_notifications",
    "announcement_reads",
    "announcement_targets",
    "announcements",
]

OLD_ANNOUNCEMENT_TYPES = [
    "import_notification_status",
    "import_notification_channel",
    "announcement_read_status",
    "announcement_read_actor_type",
    "announcement_recipient_role",
    "announcement_target_type",
    "announcement_actor_type",
    "announcement_status",
    "announcement_priority",
    "announcement_category",
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table_name in OLD_ANNOUNCEMENT_TABLES:
        if inspector.has_table(table_name, schema="public"):
            op.execute(text(f"DROP TABLE public.{table_name} CASCADE"))
    for type_name in OLD_ANNOUNCEMENT_TYPES:
        op.execute(text(f"DROP TYPE IF EXISTS public.{type_name} CASCADE"))
    for table in COMMUNICATION_TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(COMMUNICATION_TABLES):
        table.drop(bind=bind, checkfirst=True)
