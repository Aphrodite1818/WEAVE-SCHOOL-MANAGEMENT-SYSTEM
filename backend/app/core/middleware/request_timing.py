"""Lightweight request timing and correlation middleware."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from starlette.requests import Request

from app.config.logging import get_logger


logger = get_logger(__name__)


class RequestTimingMiddleware:
    """Log request duration without logging credentials or request bodies."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        started = time.perf_counter()
        status_code = 500

        async def send_with_status(message: dict) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = message.get("status", status_code)
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            log = logger.warning if duration_ms >= 500 else logger.info
            actor = getattr(request.state, "actor", None)
            log(
                "request.completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "actor_type": getattr(actor, "actor_type", None),
                    "tenant_id": getattr(actor, "tenant_id", None),
                },
            )
