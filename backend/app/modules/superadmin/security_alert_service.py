from __future__ import annotations

import asyncio
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import func, select

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.config.settings import settings
from app.core.email.enums import EmailCategory
from app.core.utils.email import send_email
from app.core.utils.email_templates import get_security_alert_email_html
from app.modules.auth.models import AuthRefreshToken
from app.modules.superadmin.models import SuperAdmin


logger = get_logger(__name__)

_pending_security_background_tasks: ContextVar[BackgroundTasks | None] = ContextVar(
    "pending_security_background_tasks",
    default=None,
)


class SecurityAlertService:
    """Queue high-signal security alerts for post-response delivery."""

    @staticmethod
    def _enabled() -> bool:
        return bool(settings.SECURITY_ALERTS_ENABLED and settings.SECURITY_ALERT_EMAIL)

    @classmethod
    async def _execute_alert(
        cls,
        title: str,
        rows: dict[str, Any],
        throttle_refresh_reuse: bool = False,
    ) -> None:
        """Fetch recipients and send a security alert after the response is sent."""

        if not cls._enabled():
            return

        try:
            async with AsyncSessionLocal() as db:
                if throttle_refresh_reuse:
                    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
                    reuse_count = (
                        await db.execute(
                            select(func.count(AuthRefreshToken.id)).where(
                                AuthRefreshToken.reuse_detected_at.is_not(None),
                                AuthRefreshToken.reuse_detected_at >= window_start,
                            )
                        )
                    ).scalar_one()

                    if reuse_count == 0 or reuse_count % 5 != 0:
                        logger.info(
                            "Security alert throttled",
                            extra={"reuse_count": reuse_count},
                        )
                        return

                    rows["Reuses in last 24h"] = reuse_count

                superadmins = await db.execute(
                    select(SuperAdmin.email).where(SuperAdmin.is_active.is_(True))
                )
                recipients = {str(settings.SECURITY_ALERT_EMAIL)}
                recipients.update(
                    email
                    for email in superadmins.scalars().all()
                    if isinstance(email, str) and email.strip()
                )

                html_body = get_security_alert_email_html(
                    title,
                    {
                        "Event time": datetime.now(timezone.utc).isoformat(),
                        **rows,
                    },
                )

                results = await asyncio.gather(
                    *(
                        send_email(
                            to_email=email,
                            subject=f"[Weave Security] {title}",
                            body=html_body,
                            is_html=True,
                            category=EmailCategory.SECURITY,
                            tags=(("email_type", "security_alert"),),
                        )
                        for email in recipients
                    ),
                    return_exceptions=True,
                )

                failures = [
                    result
                    for result in results
                    if isinstance(result, Exception) or result is False
                ]
                if failures:
                    logger.error(
                        "One or more security alert emails failed",
                        extra={
                            "title": title,
                            "recipient_count": len(recipients),
                            "failure_count": len(failures),
                        },
                    )

        except Exception as exc:
            logger.exception(
                "Failed to execute security alert background task",
                extra={"error": str(exc), "title": title},
            )

    @classmethod
    def send_security_alert(
        cls,
        *,
        background_tasks: BackgroundTasks,
        title: str,
        rows: dict[str, Any],
        throttle_refresh_reuse: bool = False,
    ) -> None:
        """Queue an alert and expose it to exception responses when necessary."""

        if not cls._enabled():
            logger.info(
                "Security alert skipped because alerts are disabled or no recipient is configured"
            )
            return

        background_tasks.add_task(
            cls._execute_alert,
            title=title,
            rows=dict(rows),
            throttle_refresh_reuse=throttle_refresh_reuse,
        )

        # FastAPI normally attaches BackgroundTasks to successful route responses.
        # Security detections often raise AppException instead, so the global
        # exception handler needs access to the same task collection.
        _pending_security_background_tasks.set(background_tasks)

    @staticmethod
    def take_pending_background_tasks() -> BackgroundTasks | None:
        """Return and clear security tasks queued by the current request context."""

        pending = _pending_security_background_tasks.get()
        _pending_security_background_tasks.set(None)
        return pending

    @classmethod
    def notify_refresh_token_reuse(
        cls,
        *,
        background_tasks: BackgroundTasks | None = None,
        actor_type: str,
        actor_id: object,
        tenant_id: object | None,
        session_jti: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Alert when refresh-token reuse marks a session compromised."""

        # Compatibility guard for the legacy router path that scheduled this
        # method itself as a background task without passing BackgroundTasks.
        # The authoritative alert is queued by mark_session_compromised().
        if background_tasks is None:
            logger.debug("Skipped duplicate refresh-reuse alert scheduling")
            return

        cls.send_security_alert(
            background_tasks=background_tasks,
            title="Refresh-token reuse detected",
            rows={
                "Actor type": actor_type,
                "Actor ID": actor_id,
                "Tenant ID": tenant_id,
                "Session JTI": session_jti,
                "IP address": ip_address or "unknown",
                "User agent": user_agent or "unknown",
                "Recommended action": (
                    "Review security analytics, block the IP if suspicious, "
                    "and revoke affected sessions."
                ),
            },
            throttle_refresh_reuse=True,
        )

    @classmethod
    def notify_platform_lockdown_change(
        cls,
        *,
        background_tasks: BackgroundTasks,
        enabled: bool,
        superadmin_id: object,
        reason: str | None,
    ) -> None:
        """Alert when platform lockdown is enabled or disabled."""

        cls.send_security_alert(
            background_tasks=background_tasks,
            title="Platform lockdown enabled" if enabled else "Platform lockdown disabled",
            rows={
                "State": "enabled" if enabled else "disabled",
                "Superadmin ID": superadmin_id,
                "Reason": reason or "not supplied",
            },
        )

    @classmethod
    def notify_ip_block_created(
        cls,
        *,
        background_tasks: BackgroundTasks,
        ip_label: str,
        superadmin_id: object,
        reason: str,
        expires_at: object | None,
    ) -> None:
        """Alert when a manual IP containment rule is created."""

        cls.send_security_alert(
            background_tasks=background_tasks,
            title="Manual IP block created",
            rows={
                "IP label": ip_label,
                "Superadmin ID": superadmin_id,
                "Reason": reason,
                "Expires at": expires_at or "never",
            },
        )
