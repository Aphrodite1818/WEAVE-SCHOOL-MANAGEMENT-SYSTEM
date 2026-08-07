import pytest
from fastapi import BackgroundTasks

from app.tenant_management.router import register_tenant
from app.tenant_management.registration_service import TenantRegistrationService


@pytest.mark.asyncio
async def test_duplicate_registration_response_preserves_background_tasks(monkeypatch):
    background_tasks = BackgroundTasks()

    async def fake_register_tenant(db, payload, background_tasks=None):
        background_tasks.add_task(lambda: None)
        return {
            "created": False,
            "email": "admin@example.com",
            "verification_required": True,
        }

    monkeypatch.setattr(
        TenantRegistrationService, "register_tenant", fake_register_tenant
    )

    response = await register_tenant(
        payload=object(),
        db=object(),
        background_tasks=background_tasks,
    )

    assert response.status_code == 200
    assert response.background is background_tasks
