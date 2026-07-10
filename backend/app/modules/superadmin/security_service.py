from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.config.logging import get_logger
from app.modules.auth.models import AuthRefreshToken, AuthSession, AuthSessionActorType
from app.modules.superadmin.models import SuperAdmin


logger = get_logger(__name__)


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
    async def _safe_scalar(
        db: AsyncSession,
        statement: Select[Any],
        *,
        default: int = 0,
        label: str,
        warnings: list[str],
    ) -> int:
        """Execute a scalar security query without allowing telemetry failure to break the endpoint."""

        try:
            value = (await db.execute(statement)).scalar_one()
            return int(value or 0)
        except (SQLAlchemyError, RuntimeError, ValueError) as exc:
            await db.rollback()
            warnings.append(label)
            logger.warning(
                "Superadmin security analytics query failed",
                extra={"query_label": label, "error": str(exc)},
            )
            return default

    @staticmethod
    async def _safe_rows(
        db: AsyncSession,
        statement: Select[Any],
        *,
        label: str,
        warnings: list[str],
    ) -> list[Any]:
        """Execute a row-list security query without allowing telemetry failure to break the endpoint."""

        try:
            return list((await db.execute(statement)).all())
        except (SQLAlchemyError, RuntimeError, ValueError) as exc:
            await db.rollback()
            warnings.append(label)
            logger.warning(
                "Superadmin security analytics row query failed",
                extra={"query_label": label, "error": str(exc)},
            )
            return []

    @staticmethod
    async def get_overview(db: AsyncSession) -> dict[str, object]:
        """Return security-focused platform analytics.

        Security telemetry must never take the whole superadmin dashboard down. If the
        deployed database is missing a newer auth telemetry table/column, the endpoint
        returns partial defaults and records which query failed in `meta.partial`.
        """

        warnings: list[str] = []
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)
        daily_window = [last_7d + timedelta(days=offset) for offset in range(8)]

        active_sessions = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(
                AuthSession.revoked_at.is_(None),
                AuthSession.compromised_at.is_(None),
                AuthSession.expires_at > now,
            ),
            label="active_sessions",
            warnings=warnings,
        )

        sessions_last_24h = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(AuthSession.created_at >= last_24h),
            label="sessions_last_24h",
            warnings=warnings,
        )

        sessions_last_7d = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(AuthSession.created_at >= last_7d),
            label="sessions_last_7d",
            warnings=warnings,
        )

        superadmin_sessions_last_24h = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(
                AuthSession.actor_type == AuthSessionActorType.SUPERADMIN,
                AuthSession.created_at >= last_24h,
            ),
            label="superadmin_sessions_last_24h",
            warnings=warnings,
        )

        distinct_login_ips_7d = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count(AuthSession.ip_address.distinct())).select_from(AuthSession).where(
                AuthSession.created_at >= last_7d,
                AuthSession.ip_address.is_not(None),
            ),
            label="distinct_login_ips_7d",
            warnings=warnings,
        )

        compromised_sessions = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(AuthSession.compromised_at.is_not(None)),
            label="compromised_sessions",
            warnings=warnings,
        )

        refresh_reuse_last_7d = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthRefreshToken).where(
                AuthRefreshToken.reuse_detected_at.is_not(None),
                AuthRefreshToken.reuse_detected_at >= last_7d,
            ),
            label="refresh_reuse_last_7d",
            warnings=warnings,
        )

        revoked_sessions_last_7d = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(AuthSession).where(
                AuthSession.revoked_at.is_not(None),
                AuthSession.revoked_at >= last_7d,
            ),
            label="revoked_sessions_last_7d",
            warnings=warnings,
        )

        inactive_superadmins = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(SuperAdmin).where(SuperAdmin.is_active.is_(False)),
            label="inactive_superadmins",
            warnings=warnings,
        )

        never_logged_in_superadmins = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(SuperAdmin).where(SuperAdmin.last_login_at.is_(None)),
            label="never_logged_in_superadmins",
            warnings=warnings,
        )

        stale_superadmins = await SuperadminSecurityService._safe_scalar(
            db,
            select(func.count()).select_from(SuperAdmin).where(
                SuperAdmin.last_login_at.is_not(None),
                SuperAdmin.last_login_at < last_30d,
            ),
            label="stale_superadmins",
            warnings=warnings,
        )

        sessions_by_actor_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                AuthSession.actor_type.label("actor_type"),
                func.count(AuthSession.id).label("value"),
            )
            .where(AuthSession.created_at >= last_7d)
            .group_by(AuthSession.actor_type)
            .order_by(func.count(AuthSession.id).desc()),
            label="sessions_by_actor_type_7d",
            warnings=warnings,
        )

        top_ip_rows = await SuperadminSecurityService._safe_rows(
            db,
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
            .limit(10),
            label="top_login_ips_7d",
            warnings=warnings,
        )

        distinct_ip_count = func.count(AuthSession.ip_address.distinct())
        unusual_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                AuthSession.actor_type.label("actor_type"),
                AuthSession.actor_id.label("actor_id"),
                distinct_ip_count.label("ip_count"),
                func.count(AuthSession.id).label("session_count"),
            )
            .where(
                AuthSession.created_at >= last_7d,
                AuthSession.ip_address.is_not(None),
            )
            .group_by(AuthSession.actor_type, AuthSession.actor_id)
            .having(distinct_ip_count >= 3)
            .order_by(distinct_ip_count.desc(), func.count(AuthSession.id).desc())
            .limit(10),
            label="unusual_login_signals",
            warnings=warnings,
        )

        session_day_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                func.date_trunc("day", AuthSession.created_at).label("period"),
                func.count(AuthSession.id).label("value"),
            )
            .where(AuthSession.created_at >= last_7d)
            .group_by(func.date_trunc("day", AuthSession.created_at))
            .order_by(func.date_trunc("day", AuthSession.created_at)),
            label="session_velocity_7d",
            warnings=warnings,
        )

        superadmin_day_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                func.date_trunc("day", AuthSession.created_at).label("period"),
                func.count(AuthSession.id).label("value"),
            )
            .where(
                AuthSession.created_at >= last_7d,
                AuthSession.actor_type == AuthSessionActorType.SUPERADMIN,
            )
            .group_by(func.date_trunc("day", AuthSession.created_at))
            .order_by(func.date_trunc("day", AuthSession.created_at)),
            label="superadmin_session_velocity_7d",
            warnings=warnings,
        )

        reuse_day_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                func.date_trunc("day", AuthRefreshToken.reuse_detected_at).label("period"),
                func.count(AuthRefreshToken.id).label("value"),
            )
            .where(
                AuthRefreshToken.reuse_detected_at.is_not(None),
                AuthRefreshToken.reuse_detected_at >= last_7d,
            )
            .group_by(func.date_trunc("day", AuthRefreshToken.reuse_detected_at))
            .order_by(func.date_trunc("day", AuthRefreshToken.reuse_detected_at)),
            label="token_reuse_trend_7d",
            warnings=warnings,
        )

        revoked_day_rows = await SuperadminSecurityService._safe_rows(
            db,
            select(
                func.date_trunc("day", AuthSession.revoked_at).label("period"),
                func.count(AuthSession.id).label("value"),
            )
            .where(
                AuthSession.revoked_at.is_not(None),
                AuthSession.revoked_at >= last_7d,
            )
            .group_by(func.date_trunc("day", AuthSession.revoked_at))
            .order_by(func.date_trunc("day", AuthSession.revoked_at)),
            label="revoked_session_trend_7d",
            warnings=warnings,
        )

        session_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in session_day_rows}
        superadmin_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in superadmin_day_rows}
        reuse_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in reuse_day_rows}
        revoked_day_map = {SuperadminSecurityService._date_key(row.period): int(row.value or 0) for row in revoked_day_rows}

        unusual_login_signals = len(unusual_rows)
        security_event_count = compromised_sessions + refresh_reuse_last_7d + unusual_login_signals
        platform_risk_score = min(
            100,
            compromised_sessions * 35
            + refresh_reuse_last_7d * 25
            + unusual_login_signals * 12
            + inactive_superadmins * 4
            + stale_superadmins * 3,
        )
        risk_level = SuperadminSecurityService._risk_level(platform_risk_score)
        session_pressure_score = min(100, sessions_last_24h * 4 + distinct_login_ips_7d * 3)

        findings: list[dict[str, object]] = []
        if compromised_sessions:
            findings.append(
                {
                    "title": "Compromised sessions detected",
                    "description": "One or more sessions were marked compromised, usually after refresh-token reuse.",
                    "severity": "danger",
                    "value": compromised_sessions,
                }
            )
        if refresh_reuse_last_7d:
            findings.append(
                {
                    "title": "Refresh-token reuse detected",
                    "description": "A reused refresh token can indicate token theft, replay, or duplicated session state.",
                    "severity": "danger",
                    "value": refresh_reuse_last_7d,
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
                    "value": never_logged_in_superadmins,
                }
            )
        if warnings:
            findings.append(
                {
                    "title": "Security telemetry partially unavailable",
                    "description": "Some auth analytics queries failed. Run the latest database migrations and check Railway logs for the listed query labels.",
                    "severity": "warning",
                    "value": len(set(warnings)),
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
                "active_sessions": active_sessions,
                "sessions_last_24h": sessions_last_24h,
                "sessions_last_7d": sessions_last_7d,
                "superadmin_sessions_last_24h": superadmin_sessions_last_24h,
                "distinct_login_ips_7d": distinct_login_ips_7d,
                "compromised_sessions": compromised_sessions,
                "refresh_reuse_last_7d": refresh_reuse_last_7d,
                "revoked_sessions_last_7d": revoked_sessions_last_7d,
                "unusual_login_signals": unusual_login_signals,
                "inactive_superadmins": inactive_superadmins,
                "never_logged_in_superadmins": never_logged_in_superadmins,
                "stale_superadmins": stale_superadmins,
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
                    {"label": "active_sessions", "value": active_sessions},
                    {"label": "revoked_7d", "value": revoked_sessions_last_7d},
                    {"label": "compromised", "value": compromised_sessions},
                    {"label": "token_reuse_7d", "value": refresh_reuse_last_7d},
                ],
                "risk_vector": [
                    {"label": "risk_score", "value": platform_risk_score},
                    {"label": "session_pressure", "value": session_pressure_score},
                    {"label": "unusual_login_spread", "value": min(100, unusual_login_signals * 20)},
                    {"label": "token_reuse_pressure", "value": min(100, refresh_reuse_last_7d * 25)},
                    {"label": "admin_staleness", "value": min(100, stale_superadmins * 20)},
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
                    {"label": "inactive", "value": inactive_superadmins},
                    {"label": "never_logged_in", "value": never_logged_in_superadmins},
                    {"label": "stale_30d", "value": stale_superadmins},
                ],
            },
            "findings": findings,
            "meta": {
                "partial": bool(warnings),
                "failed_query_labels": sorted(set(warnings)),
            },
        }
