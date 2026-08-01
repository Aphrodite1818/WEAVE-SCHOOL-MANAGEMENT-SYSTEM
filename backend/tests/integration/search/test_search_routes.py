from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import create_access_token
from app.core.dependencies.db import get_db
from app.main import app
from app.modules.auth.models import AuthSession, AuthSessionActorType
from tests.integration.test_stabilization_flows import (
    create_parent,
    create_student,
    create_teacher,
    create_tenant,
    create_tenant_admin,
)


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def auth_headers(
    db_session: AsyncSession,
    *,
    actor_id,
    actor_type: str,
    role: str,
    email: str,
    tenant_id=None,
) -> dict[str, str]:
    session_jti = f"test-{actor_type}-{actor_id}"
    db_session.add(
        AuthSession(
            tenant_id=tenant_id,
            actor_type=AuthSessionActorType(actor_type),
            actor_id=actor_id,
            session_jti=session_jti,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    await db_session.flush()

    payload = {
        "sub": str(actor_id),
        "actor_type": actor_type,
        "account_type": actor_type,
        "role": role,
        "email": email,
    }
    if tenant_id is not None:
        payload["tenant_id"] = str(tenant_id)

    token = create_access_token(data=payload, session_jti=session_jti)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_student_workspace_search_route_is_not_available(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="student-search")
    student = await create_student(
        db_session,
        tenant=tenant,
        admission_number=f"{tenant.admission_number_prefix}-001",
    )
    await db_session.commit()

    response = await api_client.get(
        "/api/v1/students/me/search?q=math",
        headers=await auth_headers(
            db_session,
            actor_id=student.id,
            actor_type="student",
            role="student",
            email=student.admission_number,
            tenant_id=tenant.id,
        ),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_parent_workspace_search_route_is_not_available(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="parent-search")
    parent_email = "parent-search@example.com"
    parent = await create_parent(
        db_session,
        tenant=tenant,
        email=parent_email,
    )
    await db_session.commit()

    response = await api_client.get(
        "/api/v1/parents/me/search?q=ada",
        headers=await auth_headers(
            db_session,
            actor_id=parent.id,
            actor_type="parent",
            role="parent",
            email=parent_email,
            tenant_id=tenant.id,
        ),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_teacher_workspace_search_route_remains_available(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="teacher-search")
    teacher_email = "teacher-search@example.com"
    teacher = await create_teacher(
        db_session,
        tenant=tenant,
        email=teacher_email,
    )
    await db_session.commit()

    response = await api_client.get(
        "/api/v1/teachers/me/search?q=tola",
        headers=await auth_headers(
            db_session,
            actor_id=teacher.id,
            actor_type="teacher",
            role="teacher",
            email=teacher_email,
            tenant_id=tenant.id,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload


@pytest.mark.asyncio
async def test_tenant_admin_workspace_search_route_remains_available(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    tenant = await create_tenant(db_session, suffix="admin-search")
    admin = await create_tenant_admin(
        db_session,
        tenant=tenant,
        email="admin-search@example.com",
    )
    await db_session.commit()

    response = await api_client.get(
        "/api/v1/tenant-admin/search?q=ada",
        headers=await auth_headers(
            db_session,
            actor_id=admin.id,
            actor_type="tenant_admin",
            role="admin",
            email=admin.email,
            tenant_id=tenant.id,
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "total" in payload
