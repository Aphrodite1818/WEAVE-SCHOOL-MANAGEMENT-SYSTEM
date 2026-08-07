from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware.cookie_request_protection import (
    CookieRequestProtectionMiddleware,
)


def _build_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(CookieRequestProtectionMiddleware)

    @app.post("/api/v1/auth/refresh")
    async def refresh() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/auth/logout")
    async def logout() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_rejects_missing_csrf_header() -> None:
    response = _build_client().post(
        "/api/v1/auth/refresh",
        headers={"Origin": "http://localhost:5174"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing CSRF protection header."


def test_rejects_untrusted_origin() -> None:
    response = _build_client().post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://attacker.example",
            "X-Weave-CSRF": "1",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted request origin."


def test_allows_development_local_origin() -> None:
    response = _build_client().post(
        "/api/v1/auth/refresh",
        headers={
            "Origin": "http://localhost:5174",
            "X-Weave-CSRF": "1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_does_not_protect_unrelated_routes() -> None:
    client = _build_client()
    response = client.get("/api/v1/auth/refresh")

    assert response.status_code == 405
