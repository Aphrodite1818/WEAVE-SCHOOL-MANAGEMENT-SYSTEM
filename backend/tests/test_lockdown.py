"""Contract tests for platform-lockdown middleware behavior."""

from __future__ import annotations

import json

from fastapi import status

from app.core.middleware.platform_lockdown import (
    PlatformLockdownMiddleware,
)


def test_lockdown_middleware_behavior() -> None:
    assert PlatformLockdownMiddleware._is_allowed_path("/api/v1/nonexistent-normal-route") is False
    assert (
        PlatformLockdownMiddleware._is_allowed_path("/api/v1/superadmin/analytics/overview") is True
    )
    assert PlatformLockdownMiddleware._is_allowed_path("/api/v1/auth/me") is True

    response = PlatformLockdownMiddleware._maintenance_response(
        {
            "lockdown_enabled": True,
            "lockdown_message": "Testing",
            "lockdown_reason": "Test lockdown",
        }
    )
    payload = json.loads(response.body)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.headers["retry-after"] == "60"
    assert payload["maintenance_mode"] is True
    assert payload["platform_lockdown"] is True
    assert payload["retryable"] is True
    assert payload["maintenance_reason"] == "Test lockdown"
