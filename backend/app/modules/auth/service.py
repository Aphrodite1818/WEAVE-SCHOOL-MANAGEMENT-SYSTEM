"""Public authentication service facade.

The implementation is split by responsibility to keep account authentication,
OTP flows, and persistent sessions independently testable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.login_service import AuthService, _tenant_allows_login
from app.modules.auth.otp_service import OTPService, TenantActivationService
from app.modules.auth.session_service import (
    AuthenticatedActor,
    AuthSessionService,
    AuthSessionTokenPair,
)

LAST_LOGIN_UPDATE_INTERVAL = timedelta(minutes=10)


def _enum_value(value: object | None) -> str | None:
    """Return a stable string value for enum-like values."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "value", str(value))


async def _update_last_login_if_due(
    db: AsyncSession,
    actor: object,
    now: datetime | None = None,
) -> bool:
    """Avoid rewriting last-login timestamps on every token operation."""

    now = now or datetime.now(timezone.utc)
    last_login_at = getattr(actor, "last_login_at", None)
    if last_login_at is not None:
        if last_login_at.tzinfo is None:
            last_login_at = last_login_at.replace(tzinfo=timezone.utc)
        if now - last_login_at < LAST_LOGIN_UPDATE_INTERVAL:
            return False
    setattr(actor, "last_login_at", now)
    db.add(actor)
    await db.flush()
    return True


__all__ = [
    "AuthenticatedActor",
    "AuthService",
    "AuthSessionService",
    "AuthSessionTokenPair",
    "OTPService",
    "TenantActivationService",
    "_enum_value",
    "_tenant_allows_login",
    "_update_last_login_if_due",
]
