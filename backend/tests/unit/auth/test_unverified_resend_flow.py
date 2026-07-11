import pytest
from fastapi import BackgroundTasks

from app.core.exceptions import AccountNotVerifiedException
from app.modules.auth.models import AuthPurpose
from app.modules.auth.service import AuthService, OTPService
from app.tenant_management.router import register_tenant
from app.tenant_management.service import TenantService


@pytest.mark.asyncio
async def test_verification_required_sends_otp_before_raising(monkeypatch):
    calls = []
    route_background_tasks = BackgroundTasks()

    async def fake_generate_otp(db, payload, background_tasks=None, *, commit=True):
        calls.append(
            {
                "db": db,
                "email": payload.email,
                "purpose": payload.purpose,
                "background_tasks": background_tasks,
                "commit": commit,
            }
        )

    monkeypatch.setattr(OTPService, "generate_otp", fake_generate_otp)

    with pytest.raises(AccountNotVerifiedException) as exc_info:
        await AuthService._raise_verification_required(
            object(),
            email="Admin@Example.com",
            background_tasks=route_background_tasks,
        )

    assert calls == [
        {
            "db": calls[0]["db"],
            "email": "admin@example.com",
            "purpose": AuthPurpose.VERIFICATION.value,
            "background_tasks": route_background_tasks,
            "commit": True,
        }
    ]
    assert exc_info.value.payload["verification_required"] is True
    assert exc_info.value.payload["resend_otp_available"] is True


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

    monkeypatch.setattr(TenantService, "register_tenant", fake_register_tenant)

    response = await register_tenant(
        payload=object(),
        db=object(),
        background_tasks=background_tasks,
    )

    assert response.status_code == 200
    assert response.background is background_tasks
