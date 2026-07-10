from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import BackgroundTasks
from sqlalchemy import select, func

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.config.settings import settings
from app.core.utils.email import send_email
from app.core.utils.email_templates import get_security_alert_email_html
from app.modules.superadmin.models import SuperAdmin
from app.modules.auth.models import AuthRefreshToken


logger = get_logger(__name__)


class SecurityAlertService:
    """Send high-signal security alerts to the platform owner/developer and superadmins."""

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
        """Background task to fetch superadmins and send emails."""
        if not cls._enabled():
            return

        try:
            async with AsyncSessionLocal() as db:
                if throttle_refresh_reuse:
                    # Throttle token reuse alerts (e.g. only alert if hitting multiples of 5 within 24h)
                    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
                    reuse_count = (
                        await db.execute(
                            select(func.count(AuthRefreshToken.id))
                            .where(
                                AuthRefreshToken.reuse_detected_at.is_not(None),
                                AuthRefreshToken.reuse_detected_at >= window_start,
                            )
                        )
                    ).scalar_one()

                    if reuse_count == 0 or reuse_count % 5 != 0:
                        logger.info("Security alert throttled", extra={"reuse_count": reuse_count})
                        return
                    
                    rows["Reuses in last 24h"] = reuse_count

                # Fetch active superadmins
                superadmins = await db.execute(
                    select(SuperAdmin.email).where(SuperAdmin.is_active.is_(True))
                )
                recipients = {str(settings.SECURITY_ALERT_EMAIL)}
                for sa_email in superadmins.scalars().all():
                    recipients.add(sa_email)

                html_body = get_security_alert_email_html(
                    title,
                    {
                        "Event time": datetime.now(timezone.utc).isoformat(),
                        **rows,
                    },
                )

                # Send to all recipients concurrently
                tasks = [
                    send_email(
                        to_email=email,
                        subject=f"[LearnlyAI Security] {title}",
                        body=html_body,
                        is_html=True,
                    )
                    for email in recipients
                ]
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as exc:
            logger.exception("Failed to execute security alert background task", extra={"error": str(exc), "title": title})

    @classmethod
    def send_security_alert(
        cls,
        *,
        background_tasks: BackgroundTasks,
        title: str,
        rows: dict[str, Any],
        throttle_refresh_reuse: bool = False,
    ) -> None:
        """Queue a security alert email to be sent in the background."""
        if not cls._enabled():
            logger.info("Security alert skipped because SECURITY_ALERT_EMAIL is not configured or alerts are disabled")
            return

        background_tasks.add_task(
            cls._execute_alert,
            title=title,
            rows=rows,
            throttle_refresh_reuse=throttle_refresh_reuse,
        )

    @classmethod
    def notify_refresh_token_reuse(
        cls,
        *,
        background_tasks: BackgroundTasks,
        actor_type: str,
        actor_id: object,
        tenant_id: object | None,
        session_jti: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        """Alert when refresh-token reuse marks a session compromised."""

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
                "Recommended action": "Review security analytics, block the IP if suspicious, and revoke affected sessions.",
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
