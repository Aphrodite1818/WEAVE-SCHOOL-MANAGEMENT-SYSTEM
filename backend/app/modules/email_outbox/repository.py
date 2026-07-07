# =============================== #
#   email_outbox_repository.py    #
# =============================== #

"""Repository layer for queued email delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_outbox.models import EmailOutbox, EmailOutboxStatus
from app.modules.email_outbox.schemas import EmailOutboxCreate


def utc_now() -> datetime:
    """Return timezone-aware UTC now."""

    return datetime.now(timezone.utc)


class EmailOutboxRepository:
    """Database operations for email outbox rows."""

    @staticmethod
    async def create_email(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        email_data: EmailOutboxCreate,
    ) -> EmailOutbox:
        """Queue one email for background delivery."""

        email_item = EmailOutbox(
            tenant_id=tenant_id,
            recipient_email=str(email_data.recipient_email).strip().lower(),
            recipient_name=email_data.recipient_name,
            subject=email_data.subject,
            template_name=email_data.template_name,
            template_context=email_data.template_context,
            max_attempts=email_data.max_attempts,
            metadata_json=email_data.metadata_json or {},
        )

        db.add(email_item)
        await db.flush()
        await db.refresh(email_item)
        return email_item

    @staticmethod
    async def create_many(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        email_items: list[EmailOutboxCreate],
    ) -> list[EmailOutbox]:
        """Queue multiple emails for background delivery."""

        created_items: list[EmailOutbox] = []

        for email_data in email_items:
            created_items.append(
                EmailOutbox(
                    tenant_id=tenant_id,
                    recipient_email=str(email_data.recipient_email).strip().lower(),
                    recipient_name=email_data.recipient_name,
                    subject=email_data.subject,
                    template_name=email_data.template_name,
                    template_context=email_data.template_context,
                    max_attempts=email_data.max_attempts,
                    metadata_json=email_data.metadata_json or {},
                )
            )

        if not created_items:
            return []

        db.add_all(created_items)
        await db.flush()

        for email_item in created_items:
            await db.refresh(email_item)

        return created_items

    @staticmethod
    async def claim_pending_batch(
        db: AsyncSession,
        *,
        batch_size: int = 50,
    ) -> list[EmailOutbox]:
        """Claim pending email rows for processing."""

        now = utc_now()

        result = await db.execute(
            select(EmailOutbox)
            .where(
                EmailOutbox.status == EmailOutboxStatus.PENDING,
                (EmailOutbox.next_retry_at.is_(None) | (EmailOutbox.next_retry_at <= now)),
                EmailOutbox.attempts < EmailOutbox.max_attempts,
            )
            .order_by(EmailOutbox.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        email_items = list(result.scalars().all())

        for email_item in email_items:
            email_item.status = EmailOutboxStatus.PROCESSING
            email_item.processing_started_at = now
            email_item.attempts += 1
            email_item.failure_reason = None

        await db.flush()
        return email_items

    @staticmethod
    async def mark_sent(
        db: AsyncSession,
        *,
        email_item: EmailOutbox,
    ) -> EmailOutbox:
        """Mark a claimed email as sent."""

        email_item.status = EmailOutboxStatus.SENT
        email_item.sent_at = utc_now()
        email_item.next_retry_at = None
        email_item.failure_reason = None

        db.add(email_item)
        await db.flush()
        await db.refresh(email_item)
        return email_item

    @staticmethod
    async def mark_failed_or_retry(
        db: AsyncSession,
        *,
        email_item: EmailOutbox,
        failure_reason: str,
        next_retry_at: datetime | None,
    ) -> EmailOutbox:
        """Mark an email as failed or pending retry."""

        if email_item.attempts >= email_item.max_attempts:
            email_item.status = EmailOutboxStatus.FAILED
            email_item.next_retry_at = None
        else:
            email_item.status = EmailOutboxStatus.PENDING
            email_item.next_retry_at = next_retry_at

        email_item.failure_reason = failure_reason[:2000]

        db.add(email_item)
        await db.flush()
        await db.refresh(email_item)
        return email_item

    @staticmethod
    async def count_pending(
        db: AsyncSession,
    ) -> int:
        """Count pending emails ready for worker processing."""

        now = utc_now()
        result = await db.execute(
            select(func.count())
            .select_from(EmailOutbox)
            .where(
                EmailOutbox.status == EmailOutboxStatus.PENDING,
                (EmailOutbox.next_retry_at.is_(None) | (EmailOutbox.next_retry_at <= now)),
                EmailOutbox.attempts < EmailOutbox.max_attempts,
            )
        )
        return int(result.scalar_one())
