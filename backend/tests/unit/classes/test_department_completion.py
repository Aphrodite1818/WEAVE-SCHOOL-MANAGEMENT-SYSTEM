from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import NotFoundException
from app.modules.classes.schemas import DepartmentUpdate
from app.modules.classes.service import DepartmentService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin-department-completion@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def test_department_update_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError, match="at least one department field must be provided"):
        DepartmentUpdate()


def test_department_update_rejects_explicit_null_name() -> None:
    with pytest.raises(ValidationError, match="name cannot be null"):
        DepartmentUpdate(name=None)


def test_department_update_preserves_name_length_limit() -> None:
    with pytest.raises(ValidationError):
        DepartmentUpdate(name="D" * 101)


@pytest.mark.asyncio
async def test_department_update_returns_not_found_for_missing_department() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(NotFoundException, match="Department not found"):
            await DepartmentService.update(
                db=AsyncMock(),
                actor=actor,
                department_id=uuid.uuid4(),
                payload=DepartmentUpdate(name="Science"),
            )


@pytest.mark.asyncio
async def test_non_admin_department_listing_is_forced_active_only() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    list_for_level = AsyncMock(return_value=[])

    with patch(
        "app.modules.classes.service.DepartmentRepository.list_for_level",
        new=list_for_level,
    ):
        await DepartmentService.list(
            db=AsyncMock(),
            actor=actor,
            academic_level_id=level_id,
            active_only=False,
            include_archived=True,
        )

    list_for_level.assert_awaited_once()
    kwargs = list_for_level.await_args.kwargs
    assert kwargs["active_only"] is True
    assert kwargs["include_archived"] is False


@pytest.mark.asyncio
async def test_admin_department_listing_keeps_inactive_visible_by_default() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    list_for_level = AsyncMock(return_value=[])

    with patch(
        "app.modules.classes.service.DepartmentRepository.list_for_level",
        new=list_for_level,
    ):
        await DepartmentService.list(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            academic_level_id=level_id,
        )

    kwargs = list_for_level.await_args.kwargs
    assert kwargs["active_only"] is False
    assert kwargs["include_archived"] is False


@pytest.mark.asyncio
async def test_admin_can_explicitly_include_archived_departments() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    list_for_level = AsyncMock(return_value=[])

    with patch(
        "app.modules.classes.service.DepartmentRepository.list_for_level",
        new=list_for_level,
    ):
        await DepartmentService.list(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            academic_level_id=level_id,
            include_archived=True,
        )

    kwargs = list_for_level.await_args.kwargs
    assert kwargs["active_only"] is False
    assert kwargs["include_archived"] is True
