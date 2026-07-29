"""Add deleted announcement read status.

Revision ID: 20260729_deleted_notif_status
Revises: 20260729_student_import_type
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "20260729_deleted_notif_status"
down_revision: str | Sequence[str] | None = "20260729_student_import_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE public.announcement_read_status ADD VALUE IF NOT EXISTS 'DELETED';")


def downgrade() -> None:
    op.execute("UPDATE public.announcement_reads SET status = 'READ' WHERE status::text = 'DELETED';")
    op.execute("ALTER TYPE public.announcement_read_status RENAME TO announcement_read_status_old;")
    op.execute("CREATE TYPE public.announcement_read_status AS ENUM ('UNREAD', 'READ', 'ACKNOWLEDGED');")
    op.execute(
        """
        ALTER TABLE public.announcement_reads
            ALTER COLUMN status TYPE public.announcement_read_status
            USING status::text::public.announcement_read_status;
        """
    )
    op.execute("DROP TYPE public.announcement_read_status_old;")
