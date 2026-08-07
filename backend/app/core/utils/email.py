"""Backward-compatible email sending helper.

New code should prefer ``EmailService`` and ``EmailRequest`` directly. This
module remains as a compatibility boundary for existing application callers.
"""

from __future__ import annotations

from app.config.logging import get_logger
from app.core.email.contracts import EmailRequest
from app.core.email.enums import EmailCategory
from app.core.email.exceptions import EmailError
from app.core.email.service import email_service

logger = get_logger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
    *,
    category: EmailCategory = EmailCategory.TRANSACTIONAL,
    reply_to: str | None = None,
    tags: tuple[tuple[str, str], ...] = (),
) -> bool:
    """Send an email through the configured provider.

    The boolean return value preserves the contract used by existing callers.
    Provider-aware code should call ``EmailService.send`` directly so it can
    inspect delivery metadata and structured provider exceptions.
    """

    try:
        request = EmailRequest(
            to_email=to_email,
            subject=subject,
            body=body,
            category=category,
            is_html=is_html,
            reply_to=reply_to,
            tags=tags,
        )

        result = await email_service.send(request=request)
        return result.accepted

    except EmailError:
        logger.exception(
            "Email delivery failed for recipient %s in category %s.",
            to_email,
            category.value,
        )
        return False
