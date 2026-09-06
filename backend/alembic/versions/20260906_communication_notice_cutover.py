"""Cut communications from announcements to hierarchy-aware notices.

Revision ID: 20260906_communication_notices
Revises: 20260905_placement_comments
Create Date: 2026-09-06
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260906_communication_notices"
down_revision: Union[str, Sequence[str], None] = "20260905_placement_comments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _rename_constraint(table: str, old: str, new: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public' AND t.relname = '{table}' AND c.conname = '{old}'
            ) THEN
                EXECUTE 'ALTER TABLE public.{table} RENAME CONSTRAINT {old} TO {new}';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.communication_announcements RENAME TO communication_notices"
    )
    op.execute(
        "ALTER TABLE public.communication_announcement_audiences "
        "RENAME TO communication_notice_audiences"
    )
    op.execute(
        "ALTER TABLE public.communication_notice_audiences "
        "RENAME COLUMN announcement_id TO notice_id"
    )
    op.execute(
        "ALTER TYPE public.communication_announcement_category "
        "RENAME TO communication_notice_category"
    )
    op.execute(
        "ALTER TYPE public.communication_announcement_priority "
        "RENAME TO communication_notice_priority"
    )
    op.execute(
        "ALTER TYPE public.communication_announcement_status "
        "RENAME TO communication_notice_status"
    )
    op.execute(
        "ALTER TYPE public.communication_audience_type "
        "RENAME TO communication_notice_audience_type"
    )
    op.execute(
        "ALTER TYPE public.communication_notification_source_type "
        "RENAME VALUE 'announcement' TO 'notice'"
    )
    op.execute(
        "ALTER INDEX IF EXISTS public.ix_comm_announcements_tenant_status "
        "RENAME TO ix_comm_notices_tenant_status"
    )
    _rename_constraint(
        "communication_notice_audiences",
        "uq_comm_announcement_audience",
        "uq_comm_notice_audience",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TYPE public.communication_notification_source_type "
        "RENAME VALUE 'notice' TO 'announcement'"
    )
    op.execute(
        "ALTER TYPE public.communication_notice_audience_type "
        "RENAME TO communication_audience_type"
    )
    op.execute(
        "ALTER TYPE public.communication_notice_status "
        "RENAME TO communication_announcement_status"
    )
    op.execute(
        "ALTER TYPE public.communication_notice_priority "
        "RENAME TO communication_announcement_priority"
    )
    op.execute(
        "ALTER TYPE public.communication_notice_category "
        "RENAME TO communication_announcement_category"
    )
    _rename_constraint(
        "communication_notice_audiences",
        "uq_comm_notice_audience",
        "uq_comm_announcement_audience",
    )
    op.execute(
        "ALTER INDEX IF EXISTS public.ix_comm_notices_tenant_status "
        "RENAME TO ix_comm_announcements_tenant_status"
    )
    op.execute(
        "ALTER TABLE public.communication_notice_audiences "
        "RENAME COLUMN notice_id TO announcement_id"
    )
    op.execute(
        "ALTER TABLE public.communication_notice_audiences "
        "RENAME TO communication_announcement_audiences"
    )
    op.execute(
        "ALTER TABLE public.communication_notices RENAME TO communication_announcements"
    )
