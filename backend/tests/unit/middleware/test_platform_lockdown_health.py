from app.core.middleware.platform_lockdown import PlatformLockdownMiddleware


def test_health_routes_bypass_lockdown_database_checks() -> None:
    assert PlatformLockdownMiddleware._is_allowed_path("/health") is True
    assert PlatformLockdownMiddleware._is_allowed_path("/health/live") is True
    assert PlatformLockdownMiddleware._is_allowed_path("/health/ready") is True
