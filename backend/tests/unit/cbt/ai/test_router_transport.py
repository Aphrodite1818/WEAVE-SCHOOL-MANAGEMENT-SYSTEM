from __future__ import annotations

from fastapi.routing import APIRoute

from app.modules.cbt.ai.router import router
from app.modules.cbt.ai.transport import CBTGZipRoute


def test_every_cbt_ai_route_uses_bidirectional_gzip_transport() -> None:
    api_routes = [route for route in router.routes if isinstance(route, APIRoute)]

    assert api_routes
    assert all(isinstance(route, CBTGZipRoute) for route in api_routes)
