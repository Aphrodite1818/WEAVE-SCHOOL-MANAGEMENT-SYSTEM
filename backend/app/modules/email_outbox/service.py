# =========================== #
#   email_outbox_service.py   #
# =========================== #

"""Service layer for safe email outbox delivery."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.email import send_email
from app.core.utils.email_templates import get_user_invite_email_html
from app.modules.email_outbox.models import EmailOutbox
from app.modules.email_outbox.repository import EmailOutboxRepository, utc_now
from app.modules.email_outbox.schemas import EmailOutboxCreate


USER_INVITE_TEMPLATE = "user_invite"


def build_retry_delay(*, attempts: int) -> timedelta:
    """Return retry delay based on current attempt count."""

    if attempts <= 1:
        return timedelta(minutes=1)

    if attempts == 2:
        return timedelta(minutes=5)

    if attempts == 3:
        return timedelta(minutes=15)

    return timedelta(minutes=30)


def build_user_invite_subject(*, school_name: str) -> str:
    """Build the user invite email subject."""

    return f"Set up your {school_name} account"


def build_user_invite_body(*, context: dict[str, Any]) -> str:
    """Build the user invite email body."""

    return get_user_invite_email_html(
        context["user_name"],
        context["school_name"],
        context["invite_link"],
    )


class EmailOutboxService:
    """Business logic for queueing and sending email outbox rows."""

    @staticmethod
    async def queue_user_invite_email(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        user_name: str,
        school_name: str,
        invite_link: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> EmailOutbox:
        """Queue one teacher/parent invite email."""

        context = {
            "user_name": user_name,
            "school_name": school_name,
            "invite_link": invite_link,
        }

        return await EmailOutboxRepository.create_email(
            db=db,
            tenant_id=tenant_id,
            email_data=EmailOutboxCreate(
                recipient_email=email,
                recipient_name=user_name,
                subject=build_user_invite_subject(school_name=school_name),
                template_name=USER_INVITE_TEMPLATE,
                template_context=context,
                metadata_json=metadata_json,
            ),
        )

    @staticmethod
    async def claim_pending_emails(
        db: AsyncSession,
        *,
        batch_size: int = 50,
    ) -> list[EmailOutbox]:
        """Claim pending emails for processing."""

        return await EmailOutboxRepository.claim_pending_batch(
            db=db,
            batch_size=batch_size,
        )

    @staticmethod
    async def send_claimed_email(
        db: AsyncSession,
        *,
        email_item: EmailOutbox,
    ) -> bool:
        """Send a claimed email item and update its delivery state."""

        try:
            if email_item.template_name != USER_INVITE_TEMPLATE:
                raise ValueError(f"Unsupported email template: {email_item.template_name}")

            html_body = build_user_invite_body(context=email_item.template_context)

            email_sent = await send_email(
                to_email=email_item.recipient_email,
                subject=email_item.subject,
                body=html_body,
                is_html=True,
            )

            if not email_sent:
                raise RuntimeError("Email provider returned a failed delivery response.")

            await EmailOutboxRepository.mark_sent(db=db, email_item=email_item)
            await db.commit()
            return True

        except Exception as exc:
            next_retry_at = utc_now() + build_retry_delay(attempts=email_item.attempts)
            await EmailOutboxRepository.mark_failed_or_retry(
                db=db,
                email_item=email_item,
                failure_reason=str(exc),
                next_retry_at=next_retry_at,
            )
            await db.commit()
            return False

    @staticmethod
    async def process_pending_batch(
        db: AsyncSession,
        *,
        batch_size: int = 50,
    ) -> dict[str, int]:
        """Process one batch of queued emails."""

        email_items = await EmailOutboxService.claim_pending_emails(
            db=db,
            batch_size=batch_size,
        )
        await db.commit()

        sent_count = 0
        failed_count = 0

        for email_item in email_items:
            was_sent = await EmailOutboxService.send_claimed_email(
                db=db,
                email_item=email_item,
            )

            if was_sent:
                sent_count += 1
            else:
                failed_count += 1

        remaining_count = await EmailOutboxRepository.count_pending(db=db)

        return {
            "claimed": len(email_items),
            "sent": sent_count,
            "failed": failed_count,
            "remaining": remaining_count,
        }
