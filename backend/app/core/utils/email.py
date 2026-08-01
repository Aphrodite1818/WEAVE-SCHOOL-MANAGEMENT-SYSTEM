import email.utils
import re
import httpx
import aiosmtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config.settings import settings
from app.config.logging import get_logger

logger = get_logger(__name__)


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = False,
) -> bool:
    """Send email via Google Apps Script first, then SMTP as a fallback."""

    # ==========================================================
    # BASIC VALIDATION
    # ==========================================================
    if not to_email or not subject or not body:
        logger.warning("Invalid email parameters")
        return False

    # ==========================================================
    # 1. GOOGLE APP SCRIPT (PRIMARY)
    # ==========================================================
    if settings.APP_SCRIPT_URL:
        try:
            payload = {
                "to": to_email,
                "subject": subject,
                "body": body,
                "html": body if is_html else None,
            }

            timeout = httpx.Timeout(12.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                res = await client.post(
                    settings.APP_SCRIPT_URL,
                    json=payload,
                )

            if res.status_code == 200:
                try:
                    response_payload = res.json()
                except ValueError:
                    response_payload = None

                if isinstance(response_payload, dict) and response_payload.get("success") is False:
                    logger.warning(f"App Script failed with success=false: {res.text}")
                    return False

                logger.info(f"Email sent via App Script → {to_email}")
                return True

            logger.warning(
                f"App Script failed ({res.status_code}): {res.text}"
            )

        except Exception as e:
            logger.exception(f"App Script error: {e}")

    # ==========================================================
    # 2. SMTP FALLBACK
    # ==========================================================
    required = [
        settings.SMTP_HOST,
        settings.SMTP_PORT,
        settings.SMTP_FROM_EMAIL,
        settings.SMTP_PASSWORD,
    ]

    if not all(required):
        logger.warning("SMTP not configured")
        return False

    # Build email message
    msg = (
        MIMEMultipart("alternative")
        if is_html
        else MIMEMultipart()
    )

    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=True)

    msg["Message-ID"] = email.utils.make_msgid(
        domain=settings.SMTP_FROM_EMAIL.split("@")[-1]
    )

    if is_html:
        plain_text = re.sub(r"<[^>]+>", " ", body)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    smtp = aiosmtplib.SMTP(
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        start_tls=(settings.SMTP_PORT == 587),
        use_tls=(settings.SMTP_PORT == 465),
        timeout=15,
    )

    try:
        await smtp.connect()

        # NOTE: using FROM_EMAIL as auth identity
        await smtp.login(
            settings.SMTP_FROM_EMAIL,
            settings.SMTP_PASSWORD,
        )

        await smtp.send_message(msg)

        logger.info(f"Email sent via SMTP fallback → {to_email}")
        return True

    except Exception as e:
        logger.exception(f"SMTP fallback error: {e}")
        return False

    finally:
        try:
            if smtp.is_connected:
                await smtp.quit()
        except Exception:
            pass

