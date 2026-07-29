from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.modules.superadmin.platform_control_service import (
    DEFAULT_MAINTENANCE_MESSAGE,
    PlatformControlService,
)
from app.modules.superadmin.security_response_service import SecurityResponseService


logger = get_logger(__name__)

_ALLOWED_EXACT_PATHS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/auth/me/session",
}
_ALLOWED_PREFIXES = (
    "/api/v1/superadmin",
    "/api/v1/metrics/superadmin",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.client.host if request.client else None


class PlatformLockdownMiddleware:
    """Block non-superadmin platform traffic during emergency controls."""

    _last_known_lockdown_state: dict[str, object] | None = None

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _is_allowed_path(path: str) -> bool:
        if path in _ALLOWED_EXACT_PATHS:
            return True
        return any(path.startswith(prefix) for prefix in _ALLOWED_PREFIXES)

    @staticmethod
    def _maintenance_response(state: dict[str, object]) -> JSONResponse:
        message = str(state.get("lockdown_message") or DEFAULT_MAINTENANCE_MESSAGE)
        reason = state.get("lockdown_reason")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": "60"},
            content={
                "detail": message,
                "maintenance_mode": True,
                "platform_lockdown": True,
                "retryable": True,
                "maintenance_reason": reason,
            },
        )

    @staticmethod
    def _ip_block_response(state: dict[str, object]) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            headers={"Retry-After": "300"},
            content={
                "detail": "Access from this network has been temporarily blocked for security reasons.",
                "security_block": True,
                "ip_blocked": True,
                "ip_label": state.get("ip_label"),
                "reason": state.get("reason"),
                "expires_at": state.get("expires_at"),
            },
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if request.method == "OPTIONS" or self._is_allowed_path(request.url.path):
            await self.app(scope, receive, send)
            return

        try:
            async with AsyncSessionLocal() as db:
                ip_state = await SecurityResponseService.is_ip_blocked(db, _client_ip(request))
                if ip_state.get("blocked"):
                    response = self._ip_block_response(ip_state)
                    await response(scope, receive, send)
                    return

                lockdown_state = await PlatformControlService.get_state(db)
                self.__class__._last_known_lockdown_state = lockdown_state
        except Exception as exc:
            last_known_state = self.__class__._last_known_lockdown_state
            logger.critical(
                "Failed to read emergency control state",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client_ip": _client_ip(request),
                    "has_last_known_state": last_known_state is not None,
                    "last_known_lockdown_enabled": (
                        bool(last_known_state.get("lockdown_enabled"))
                        if last_known_state is not None
                        else None
                    ),
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            if last_known_state is not None and last_known_state.get("lockdown_enabled"):
                response = self._maintenance_response(last_known_state)
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        if not lockdown_state.get("lockdown_enabled"):
            await self.app(scope, receive, send)
            return

        response = self._maintenance_response(lockdown_state)
        await response(scope, receive, send)
