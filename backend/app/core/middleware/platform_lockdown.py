from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.modules.superadmin.platform_control_service import (
    DEFAULT_MAINTENANCE_MESSAGE,
    PlatformControlService,
)


logger = get_logger(__name__)

_ALLOWED_EXACT_PATHS = {
    "/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/me/session",
}
_ALLOWED_PREFIXES = (
    "/api/v1/superadmin",
    "/docs",
    "/redoc",
    "/openapi.json",
)


class PlatformLockdownMiddleware:
    """Block non-superadmin platform traffic during emergency lockdown."""

    def __init__(self, app: Callable[[Request], Awaitable[Response]]) -> None:
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

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if request.method == "OPTIONS" or self._is_allowed_path(request.url.path):
            await self.app(scope, receive, send)
            return

        try:
            async with AsyncSessionLocal() as db:
                state = await PlatformControlService.get_state(db)
        except Exception as exc:
            logger.exception(
                "Failed to read platform lockdown state; allowing request to avoid self-lockout",
                extra={"path": request.url.path, "error": str(exc)},
            )
            await self.app(scope, receive, send)
            return

        if not state.get("lockdown_enabled"):
            await self.app(scope, receive, send)
            return

        response = self._maintenance_response(state)
        await response(scope, receive, send)
