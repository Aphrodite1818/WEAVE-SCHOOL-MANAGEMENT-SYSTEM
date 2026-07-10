from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

from app.config.logging import get_logger
from app.config.settings import settings
from app.core.utils.email import send_email


logger = get_logger(__name__)


class SecurityAlertService:
    """Send high-signal security alerts to the platform owner/developer."""

    @staticmethod
    def _enabled() -> bool:
        return bool(settings.SECURITY_ALERTS_ENABLED and settings.SECURITY_ALERT_EMAIL)

    @staticmethod
    def _html(title: str, rows: dict[str, Any]) -> str:
        row_markup = "".join(
            f"<tr><td style='padding:8px 12px;color:#64748b;font-weight:600'>{escape(str(key))}</td>"
            f"<td style='padding:8px 12px;color:#0f172a'>{escape(str(value))}</td></tr>"
            for key, value in rows.items()
            if value is not None and value != ""
        )
        return f"""
        <div style="font-family:Inter,Arial,sans-serif;line-height:1.6;color:#0f172a">
          <h2 style="margin:0 0 8px">{escape(title)}</h2>
          <p style="margin:0 0 16px;color:#475569">A high-signal LearnlyAI security event was detected.</p>
          <table style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden">
            {row_markup}
          </table>
        </div>
        """

    @classmethod
    async def send_security_alert(cls, *, title: str, rows: dict[str, Any]) -> bool:
        """Send a security alert email if alerts are configured."""

        if not cls._enabled():
            logger.info("Security alert skipped because SECURITY_ALERT_EMAIL is not configured or alerts are disabled")
            return False

        try:
            return await send_email(
                to_email=str(settings.SECURITY_ALERT_EMAIL),
                subject=f"[LearnlyAI Security] {title}",
                body=cls._html(
                    title,
                    {
                        "Event time": datetime.now(timezone.utc).isoformat(),
                        **rows,
                    },
                ),
                is_html=True,
            )
        except Exception as exc:
            logger.exception("Failed to send security alert email", extra={"error": str(exc), "title": title})
            return False

    @classmethod
    async def notify_refresh_token_reuse(
        cls,
        *,
        actor_type: str,
        actor_id: object,
        tenant_id: object | None,
        session_jti: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> bool:
        """Alert when refresh-token reuse marks a session compromised."""

        return await cls.send_security_alert(
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
        )

    @classmethod
    async def notify_platform_lockdown_change(
        cls,
        *,
        enabled: bool,
        superadmin_id: object,
        reason: str | None,
    ) -> bool:
        """Alert when platform lockdown is enabled or disabled."""

        return await cls.send_security_alert(
            title="Platform lockdown enabled" if enabled else "Platform lockdown disabled",
            rows={
                "State": "enabled" if enabled else "disabled",
                "Superadmin ID": superadmin_id,
                "Reason": reason or "not supplied",
            },
        )

    @classmethod
    async def notify_ip_block_created(
        cls,
        *,
        ip_label: str,
        superadmin_id: object,
        reason: str,
        expires_at: object | None,
    ) -> bool:
        """Alert when a manual IP containment rule is created."""

        return await cls.send_security_alert(
            title="Manual IP block created",
            rows={
                "IP label": ip_label,
                "Superadmin ID": superadmin_id,
                "Reason": reason,
                "Expires at": expires_at or "never",
            },
        )
