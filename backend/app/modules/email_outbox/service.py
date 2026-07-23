# =========================== #
#   email_outbox_service.py   #
# =========================== #

"""Service layer for safe email outbox delivery."""

from __future__ import annotations

from datetime import timedelta
from html import escape
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue.context import get_current_bulk_import_job_id
from app.core.utils.email import send_email
from app.modules.email_outbox.models import EmailOutbox
from app.modules.email_outbox.repository import EmailOutboxRepository, utc_now
from app.modules.email_outbox.schemas import EmailOutboxCreate, EmailOutboxSummaryResponse


TEACHER_INVITATION_TEMPLATE = "teacher_invitation"
PARENT_INVITATION_TEMPLATE = "parent_invitation"
DEFAULT_EMAIL_BATCH_SIZE = 20
STALE_PROCESSING_MINUTES = 10


def build_retry_delay(*, attempts: int) -> timedelta:
    """Return retry delay based on current attempt count."""

    if attempts <= 1:
        return timedelta(minutes=1)

    if attempts == 2:
        return timedelta(minutes=5)

    if attempts == 3:
        return timedelta(minutes=15)

    return timedelta(minutes=30)


def build_teacher_invitation_subject(*, school_name: str) -> str:
    """Build the teacher invitation email subject."""

    return f"Join {school_name} on Weave"


def build_teacher_invitation_body(*, context: dict[str, Any]) -> str:
    """Build the teacher invitation email body."""

    invite_link = escape(str(context["invite_link"]), quote=True)
    return (
        "<p>You were invited to join a school on Weave.</p>"
        f'<p><a href="{invite_link}">Review invitation</a></p>'
    )


def build_parent_invitation_subject(*, school_name: str) -> str:
    """Build the parent invitation email subject."""

    return f"Join {school_name} on Weave"


def build_parent_invitation_body(*, context: dict[str, Any]) -> str:
    """Build the parent invitation email body."""

    school_name = escape(str(context.get("school_name") or "your school"))
    student_name = escape(str(context.get("student_name") or "a student"))
    invite_link = escape(str(context["invite_link"]), quote=True)
    return (
        f"<p>You were invited to link to {student_name} at {school_name} on Weave.</p>"
        f'<p><a href="{invite_link}">Review invitation</a></p>'
        "<p>You will confirm the student's admission number "
        "before the link request is created.</p>"
    )


def resolve_outbox_metadata(metadata_json: dict[str, Any] | None) -> dict[str, Any]:
    """Attach the active import ID to bulk-import outbox rows."""

    metadata = dict(metadata_json or {})
    import_job_id = get_current_bulk_import_job_id()

    if metadata.get("source") == "bulk_import" and import_job_id:
        metadata.setdefault("import_job_id", import_job_id)

    return metadata


class EmailOutboxService:
    """Business logic for queueing and sending email outbox rows."""

    @staticmethod
    async def queue_teacher_invitation_email(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        school_name: str,
        invite_link: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> EmailOutbox:
        """Queue one canonical teacher invitation email."""

        context = {
            "school_name": school_name,
            "invite_link": invite_link,
        }

        return await EmailOutboxRepository.create_email(
            db=db,
            tenant_id=tenant_id,
            email_data=EmailOutboxCreate(
                recipient_email=email,
                recipient_name=email,
                subject=build_teacher_invitation_subject(school_name=school_name),
                template_name=TEACHER_INVITATION_TEMPLATE,
                template_context=context,
                metadata_json=resolve_outbox_metadata(metadata_json),
            ),
        )

    @staticmethod
    async def queue_parent_invitation_email(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        school_name: str,
        student_name: str,
        invite_link: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> EmailOutbox:
        """Queue one canonical parent invitation email."""

        context = {
            "school_name": school_name,
            "student_name": student_name,
            "invite_link": invite_link,
        }

        return await EmailOutboxRepository.create_email(
            db=db,
            tenant_id=tenant_id,
            email_data=EmailOutboxCreate(
                recipient_email=email,
                recipient_name=email,
                subject=build_parent_invitation_subject(school_name=school_name),
                template_name=PARENT_INVITATION_TEMPLATE,
                template_context=context,
                metadata_json=resolve_outbox_metadata(metadata_json),
            ),
        )

    @staticmethod
    async def recover_stale_processing_emails(
        db: AsyncSession,
        *,
        tenant_id: UUID | None = None,
        stale_minutes: int = STALE_PROCESSING_MINUTES,
    ) -> dict[str, int]:
        """Recover emails stuck in processing after a worker timeout or crash."""

        stale_before = utc_now() - timedelta(minutes=stale_minutes)
        result = await EmailOutboxRepository.recover_stale_processing(
            db=db,
            tenant_id=tenant_id,
            stale_before=stale_before,
        )
        await db.commit()
        return result

    @staticmethod
    async def claim_pending_emails(
        db: AsyncSession,
        *,
        batch_size: int = DEFAULT_EMAIL_BATCH_SIZE,
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
            if email_item.template_name == TEACHER_INVITATION_TEMPLATE:
                html_body = build_teacher_invitation_body(
                    context=email_item.template_context
                )
            elif email_item.template_name == PARENT_INVITATION_TEMPLATE:
                html_body = build_parent_invitation_body(
                    context=email_item.template_context
                )
            else:
                raise ValueError(
                    f"Unsupported email template: {email_item.template_name}"
                )

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
        batch_size: int = DEFAULT_EMAIL_BATCH_SIZE,
    ) -> dict[str, int]:
        """Process one batch of queued emails."""

        recovery_result = await EmailOutboxService.recover_stale_processing_emails(db=db)

        email_items = await EmailOutboxService.claim_pending_emails(
            db=db,
            batch_size=min(batch_size, DEFAULT_EMAIL_BATCH_SIZE),
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
            "recovered": recovery_result.get("recovered", 0),
            "stale_failed": recovery_result.get("failed", 0),
        }

    @staticmethod
    async def summarize_tenant_outbox(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        import_job_id: UUID | None = None,
        source: str | None = None,
    ) -> EmailOutboxSummaryResponse:
        """Return status counts for tenant email outbox rows."""

        counts = await EmailOutboxRepository.count_by_status(
            db=db,
            tenant_id=tenant_id,
            import_job_id=import_job_id,
            source=source,
        )

        total = sum(counts.values())
        return EmailOutboxSummaryResponse(
            total=total,
            pending=counts.get("pending", 0),
            processing=counts.get("processing", 0),
            sent=counts.get("sent", 0),
            failed=counts.get("failed", 0),
            cancelled=counts.get("cancelled", 0),
        )

    @staticmethod
    async def retry_failed_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> dict[str, int]:
        """Retry failed emails that still have attempts remaining."""

        retried = await EmailOutboxRepository.retry_failed(db=db, tenant_id=tenant_id)
        await db.commit()
        return {"retried": retried}
