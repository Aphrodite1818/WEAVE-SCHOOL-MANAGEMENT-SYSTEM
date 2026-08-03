from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from app.core.middleware.security_headers import SecurityHeadersMiddleware


async def _app(scope, receive, send):
    response = Response("ok")
    await response(scope, receive, send)


async def _call_next(request: Request) -> Response:
    _ = request
    return Response("ok")


async def test_production_security_headers_include_hsts() -> None:
    middleware = SecurityHeadersMiddleware(
        _app,
        strict_transport_security=True,
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 1234),
            "scheme": "https",
            "root_path": "",
            "http_version": "1.1",
        }
    )

    response = await middleware.dispatch(request, _call_next)

    assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "camera=()" in response.headers["Permissions-Policy"]
