from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AuthRefreshToken, AuthSession, AuthSessionActorType
from app.modules.superadmin.models import SuperAdmin


class SuperadminSecurityService:
    """Security analytics for platform-level superadmin visibility."""

    @staticmethod
    def _enum_label(value: object) -> str:
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _actor_label(actor_type: object, actor_id: object) -> str:
        actor = SuperadminSecurityService._enum_label(actor_type).replace("_", " ")
        return f"{actor} · {str(actor_id)[:8]}"

    @staticmethod
    def _risk_tone(count: int) -> str:
        if count <= 0:
            return "success"
        if count <= 2:
            return "warning"
        return "danger"

    @staticmethod
    async def get_overview(db: AsyncSession) -> dict[str, object]:
        """Return security-focused platform analytics."""

        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        active_sessions = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(
                    AuthSession.revoked_at.is_(None),
                    AuthSession.compromised_at.is_(None),
                    AuthSession.expires_at > now,
                )
            )
        ).scalar_one()

        sessions_last_24h = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(AuthSession.created_at >= last_24h)
            )
        ).scalar_one()

        sessions_last_7d = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(AuthSession.created_at >= last_7d)
            )
        ).scalar_one()

        superadmin_sessions_last_24h = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(
                    AuthSession.actor_type == AuthSessionActorType.SUPERADMIN,
                    AuthSession.created_at >= last_24h,
                )
            )
        ).scalar_one()

        compromised_sessions = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(AuthSession.compromised_at.is_not(None))
            )
        ).scalar_one()

        refresh_reuse_last_7d = (
            await db.execute(
                select(func.count()).select_from(AuthRefreshToken).where(
                    AuthRefreshToken.reuse_detected_at.is_not(None),
                    AuthRefreshToken.reuse_detected_at >= last_7d,
                )
            )
        ).scalar_one()

        revoked_sessions_last_7d = (
            await db.execute(
                select(func.count()).select_from(AuthSession).where(
                    AuthSession.revoked_at.is_not(None),
                    AuthSession.revoked_at >= last_7d,
                )
            )
        ).scalar_one()

        inactive_superadmins = (
            await db.execute(
                select(func.count()).select_from(SuperAdmin).where(SuperAdmin.is_active.is_(False))
            )
        ).scalar_one()

        never_logged_in_superadmins = (
            await db.execute(
                select(func.count()).select_from(SuperAdmin).where(SuperAdmin.last_login_at.is_(None))
            )
        ).scalar_one()

        stale_superadmins = (
            await db.execute(
                select(func.count()).select_from(SuperAdmin).where(
                    SuperAdmin.last_login_at.is_not(None),
                    SuperAdmin.last_login_at < last_30d,
                )
            )
        ).scalar_one()

        sessions_by_actor_rows = (
            await db.execute(
                select(
                    AuthSession.actor_type.label("actor_type"),
                    func.count(AuthSession.id).label("value"),
                )
                .where(AuthSession.created_at >= last_7d)
                .group_by(AuthSession.actor_type)
                .order_by(func.count(AuthSession.id).desc())
            )
        ).all()

        top_ip_rows = (
            await db.execute(
                select(
                    AuthSession.ip_address.label("ip_address"),
                    func.count(AuthSession.id).label("value"),
                )
                .where(
                    AuthSession.created_at >= last_7d,
                    AuthSession.ip_address.is_not(None),
                )
                .group_by(AuthSession.ip_address)
                .order_by(func.count(AuthSession.id).desc())
                .limit(8)
            )
        ).all()

        distinct_ip_count = func.count(func.distinct(AuthSession.ip_address))
        unusual_rows = (
            await db.execute(
                select(
                    AuthSession.actor_type.label("actor_type"),
                    AuthSession.actor_id.label("actor_id"),
                    distinct_ip_count.label("ip_count"),
                    func.count(AuthSession.id).label("session_count"),
                    func.max(func.coalesce(AuthSession.last_used_at, AuthSession.created_at)).label("last_seen"),
                )
                .where(
                    AuthSession.created_at >= last_7d,
                    AuthSession.ip_address.is_not(None),
                )
                .group_by(AuthSession.actor_type, AuthSession.actor_id)
                .having(distinct_ip_count >= 3)
                .order_by(distinct_ip_count.desc(), func.count(AuthSession.id).desc())
                .limit(8)
            )
        ).all()

        unusual_login_signals = len(unusual_rows)
        security_event_count = int(compromised_sessions or 0) + int(refresh_reuse_last_7d or 0) + unusual_login_signals

        findings: list[dict[str, object]] = []
        if compromised_sessions:
            findings.append(
                {
                    "title": "Compromised sessions detected",
                    "description": "One or more sessions were marked compromised, usually after refresh-token reuse.",
                    "severity": "danger",
                    "value": int(compromised_sessions),
                }
            )
        if refresh_reuse_last_7d:
            findings.append(
                {
                    "title": "Refresh-token reuse detected",
                    "description": "A reused refresh token can indicate token theft or duplicated sessions.",
                    "severity": "danger",
                    "value": int(refresh_reuse_last_7d),
                }
            )
        if unusual_login_signals:
            findings.append(
                {
                    "title": "Unusual login spread",
                    "description": "Some actors used three or more IP addresses within seven days.",
                    "severity": "warning",
                    "value": unusual_login_signals,
                }
            )
        if never_logged_in_superadmins:
            findings.append(
                {
                    "title": "Unused superadmin invites/accounts",
                    "description": "Superadmin accounts that have never logged in should be reviewed.",
                    "severity": "warning",
                    "value": int(never_logged_in_superadmins),
                }
            )
        if not findings:
            findings.append(
                {
                    "title": "Security posture looks calm",
                    "description": "No compromised sessions, token reuse, or unusual IP spread is currently visible.",
                    "severity": "success",
                    "value": 0,
                }
            )

        return {
            "stats": {
                "active_sessions": int(active_sessions or 0),
                "sessions_last_24h": int(sessions_last_24h or 0),
                "sessions_last_7d": int(sessions_last_7d or 0),
                "superadmin_sessions_last_24h": int(superadmin_sessions_last_24h or 0),
                "compromised_sessions": int(compromised_sessions or 0),
                "refresh_reuse_last_7d": int(refresh_reuse_last_7d or 0),
                "revoked_sessions_last_7d": int(revoked_sessions_last_7d or 0),
                "unusual_login_signals": unusual_login_signals,
                "inactive_superadmins": int(inactive_superadmins or 0),
                "never_logged_in_superadmins": int(never_logged_in_superadmins or 0),
                "stale_superadmins": int(stale_superadmins or 0),
                "security_event_count": security_event_count,
            },
            "charts": {
                "security_session_mix": [
                    {"label": "active_sessions", "value": int(active_sessions or 0)},
                    {"label": "revoked_7d", "value": int(revoked_sessions_last_7d or 0)},
                    {"label": "compromised", "value": int(compromised_sessions or 0)},
                    {"label": "token_reuse_7d", "value": int(refresh_reuse_last_7d or 0)},
                ],
                "sessions_by_actor_type_7d": [
                    {
                        "label": SuperadminSecurityService._enum_label(row.actor_type),
                        "value": int(row.value or 0),
                    }
                    for row in sessions_by_actor_rows
                ],
                "top_login_ips_7d": [
                    {"label": row.ip_address or "unknown", "value": int(row.value or 0)}
                    for row in top_ip_rows
                ],
                "unusual_login_signals": [
                    {
                        "label": SuperadminSecurityService._actor_label(row.actor_type, row.actor_id),
                        "value": int(row.ip_count or 0),
                    }
                    for row in unusual_rows
                ],
                "superadmin_account_posture": [
                    {"label": "inactive", "value": int(inactive_superadmins or 0)},
                    {"label": "never_logged_in", "value": int(never_logged_in_superadmins or 0)},
                    {"label": "stale_30d", "value": int(stale_superadmins or 0)},
                ],
            },
            "findings": findings,
        }
