import pytest
from httpx import AsyncClient

from app.modules.superadmin.platform_control_service import PlatformControlService
from app.config.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_lockdown_middleware_behavior(app_client: AsyncClient):
    # 1. Enable lockdown
    async with AsyncSessionLocal() as db:
        await PlatformControlService.enable_lockdown(
            db, 
            reason="Test lockdown", 
            message="Testing", 
            confirmation="LOCKDOWN"
        )
    
    # 2. Test standard route (should be 503)
    resp = await app_client.get("/api/v1/health") # Wait, /health is in _ALLOWED_EXACT_PATHS
    # Let's test a non-allowed route, e.g. /api/v1/some-tenant-route or /api/v1/auth/login? (Wait, login is allowed)
    # Let's try /api/v1/users/profile or similar. Since we don't know the exact routes, let's just try /api/v1/invalid
    resp = await app_client.get("/api/v1/nonexistent-normal-route")
    assert resp.status_code == 503
    assert resp.json()["maintenance_mode"] == True
    
    # 3. Test superadmin route (should NOT be 503, maybe 401 if unauthenticated, or 404 if not found)
    resp = await app_client.get("/api/v1/superadmin/analytics/overview")
    assert resp.status_code != 503 # Likely 401 unauthorized
    
    # 4. Test auth me route (should NOT be 503)
    resp = await app_client.get("/api/v1/auth/me")
    assert resp.status_code != 503 # Likely 401 unauthorized
    
    # 5. Disable lockdown to clean up
    async with AsyncSessionLocal() as db:
        await PlatformControlService.disable_lockdown(db, confirmation="UNLOCK")

