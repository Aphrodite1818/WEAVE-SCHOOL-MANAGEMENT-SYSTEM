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
    def _date_key(value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        return str(value)[:10]

    @staticmethod
    def _day_label(value: datetime) -> str:
        return value.strftime("%a")

    @staticmethod
    def _risk_level(score: int) -> str:
        if score >= 75:
            return "critical"
        if score >= 50:
            return "elevated"
        if score >= 25:
            return "guarded"
        return "calm"

    @staticmethod
    async def get_overview(db: AsyncSession) -> dict[str, object]:
        """Return security-focused platform analytics."""

        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        daily_window = [last_7d + timedelta(days=offset) for offset in range(8)]

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

        distinct_login_ips_7d = (
            await db.execute(
                select(func.count(func.distinct(AuthSession.ip_address))).select_from(AuthSession).where(
                    AuthSession.created_at >= last_7d,
                    AuthSession.ip_address.is_not(None),
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
                .limit(10)
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
                .limit(10)
            )
        ).all()

        session_day_rows = (
            await db.execute(
                select(
                    func.date_trunc("day", AuthSession.created_at).label("period"),
                    func.count(AuthSession.id).label("value"),
                )
                .where(AuthSession.created_at >= last_7d)
                .group_by(func.date_trunc("day", AuthSession.created_at))
                .order_by(func.date_trunc("day", AuthSession.created_at))
            )
        ).all()

        superadmin_day_rows = (
            await db.execute(
                select(
                    func.date_trunc("day", AuthSession.created_at).label("period"),
                    func.count(AuthSession.id).label("value"),
                )
                .where(
                    AuthSession.created_at >= last_7d,
                    AuthSession.actor_type == AuthSessionActorType.SUPERADMIN,
                )
                .group_by(func.date_trunc("day", AuthSession.created_at))
                .order_by(func.date_trunc("day", AuthSession.created_at))
            )
        ).all()

        reuse_day_rows = (
            await db.execute(
                select(
                    func.date_trunc("day", AuthRefreshToken.reuse_detected_at).label("period"),
                    func.count(AuthRefreshToken.id).label("value"),
                )
                .where(
                    AuthRefreshToken.reuse_detected_at.is_not(None),
                    AuthRefreshToken.reuse_detected_at >= last_7d,
                )
                .group_by(func.date_trunc("day", AuthRefreshToken.reuse_detected_at))
                .order_by(func.date_trunc("day", AuthRefreshToken.reuse_detected_at))
            )
        ).all()

        revoked_day_rows = (
            await db.execute(
                select(
                    func.date_trunc("day", AuthSession.revoked_at).label("period"),
                    func.count(AuthSession.id).label("value"),
                )
                .where(
                    AuthSession.revoked_at.is_not(None),
                    AuthSession.revoked_at >= last_7d,
                )
                .group_by(func.date_trunc("day", AuthSession.revoked_at))
                .order_by(func.date_trunc("day", AuthSession.revoked_at))
            )
        ).all()

        session_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in session_day_rows}
        superadmin_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in superadmin_day_rows}
        reuse_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in reuse_day_rows}
        revoked_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in revoked_day_rows}

        unusual_login_signals = len(unusual_rows)
        security_event_count = int(compromised_sessions or 0) + int(refresh_reuse_last_7d or 0) + unusual_login_signals
        platform_risk_score = min(
            100,
            int(compromised_sessions or 0) * 35
            + int(refresh_reuse_last_7d or 0) * 25
            + unusual_login_signals * 12
            + int(inactive_superadmins or 0) * 4
            + int(stale_superadmins or 0) * 3,
        )
        risk_level = SuperadminSecurityService._risk_level(platform_risk_score)
        session_pressure_score = min(100, int(sessions_last_24h or 0) * 4 + int(distinct_login_ips_7d or 0) * 3)

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
                    "description": "A reused refresh token can indicate token theft, replay, or duplicated session state.",
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
                    "title": "Unused superadmin accounts",
                    "description": "Superadmin accounts that have never logged in should be reviewed or revoked.",
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
                "distinct_login_ips_7d": int(distinct_login_ips_7d or 0),
                "compromised_sessions": int(compromised_sessions or 0),
                "refresh_reuse_last_7d": int(refresh_reuse_last_7d or 0),
                "revoked_sessions_last_7d": int(revoked_sessions_last_7d or 0),
                "unusual_login_signals": unusual_login_signals,
                "inactive_superadmins": int(inactive_superadmins or 0),
                "never_logged_in_superadmins": int(never_logged_in_superadmins or 0),
                "stale_superadmins": int(stale_superadmins or 0),
                "security_event_count": security_event_count,
                "platform_risk_score": platform_risk_score,
                "risk_level": risk_level,
                "session_pressure_score": session_pressure_score,
            },
            "charts": {
                "session_velocity_7d": [
                    {
                        "label": SuperadminSecurityService._day_label(day),
                        "fullLabel": day.strftime("%Y-%m-%d"),
                        "value": session_day_map.get(day.date().isoformat(), 0),
                    }
                    for day in daily_window
                ],
                "superadmin_session_velocity_7d": [
                    {
                        "label": SuperadminSecurityService._day_label(day),
                        "fullLabel": day.strftime("%Y-%m-%d"),
                        "value": superadmin_day_map.get(day.date().isoformat(), 0),
                    }
                    for day in daily_window
                ],
                "token_reuse_trend_7d": [
                    {
                        "label": SuperadminSecurityService._day_label(day),
                        "fullLabel": day.strftime("%Y-%m-%d"),
                        "value": reuse_day_map.get(day.date().isoformat(), 0),
                    }
                    for day in daily_window
                ],
                "revoked_session_trend_7d": [
                    {
                        "label": SuperadminSecurityService._day_label(day),
                        "fullLabel": day.strftime("%Y-%m-%d"),
                        "value": revoked_day_map.get(day.date().isoformat(), 0),
                    }
                    for day in daily_window
                ],
                "security_session_mix": [
                    {"label": "active_sessions", "value": int(active_sessions or 0)},
                    {"label": "revoked_7d", "value": int(revoked_sessions_last_7d or 0)},
                    {"label": "compromised", "value": int(compromised_sessions or 0)},
                    {"label": "token_reuse_7d", "value": int(refresh_reuse_last_7d or 0)},
                ],
                "risk_vector": [
                    {"label": "risk_score", "value": platform_risk_score},
                    {"label": "session_pressure", "value": session_pressure_score},
                    {"label": "unusual_login_spread", "value": min(100, unusual_login_signals * 20)},
                    {"label": "token_reuse_pressure", "value": min(100, int(refresh_reuse_last_7d or 0) * 25)},
                    {"label": "admin_staleness", "value": min(100, int(stale_superadmins or 0) * 20)},
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
