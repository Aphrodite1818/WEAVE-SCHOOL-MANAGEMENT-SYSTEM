"""Security response headers for browser-facing surfaces."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self' https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

DOCS_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https:; "
    "font-src 'self' data: https://cdn.jsdelivr.net; "
    "connect-src 'self' https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

DOCS_PATHS = ("/docs", "/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative browser security headers to every response."""

    def __init__(
        self,
        app,
        allow_docs_cdn: bool = False,
        strict_transport_security: bool = False,
    ):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.allow_docs_cdn = allow_docs_cdn
        self.strict_transport_security = strict_transport_security

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        policy = CONTENT_SECURITY_POLICY
        if self.allow_docs_cdn and request.url.path.startswith(DOCS_PATHS):
            policy = DOCS_CONTENT_SECURITY_POLICY

        response.headers.setdefault("Content-Security-Policy", policy)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), payment=(), usb=()",
        )
        if self.strict_transport_security:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000",
            )
        return response
