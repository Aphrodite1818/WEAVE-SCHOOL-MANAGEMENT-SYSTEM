from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.students.admin_contracts import StudentAdminContractService
from app.modules.students.read_service import StudentReadService


@pytest.mark.asyncio
async def test_tenant_admin_list_materializes_due_returns_before_status_filtering() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.lifecycle_service.StudentLifecycleService.activate_due_returns_for_tenant",
            new=AsyncMock(return_value=1),
        ) as activate_due,
        patch(
            "app.modules.students.admin_contracts.StudentRepository.list_for_tenant",
            new=AsyncMock(return_value=([], 0)),
        ) as list_students,
    ):
        items, total = await StudentAdminContractService.list_students(
            db,
            actor=actor,
            status=None,
        )

    assert items == []
    assert total == 0
    activate_due.assert_awaited_once_with(db, tenant_id=tenant_id)
    list_students.assert_awaited_once()
    assert activate_due.await_count == 1


@pytest.mark.asyncio
async def test_general_student_list_materializes_due_returns_before_query() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.lifecycle_service.StudentLifecycleService.activate_due_returns_for_tenant",
            new=AsyncMock(return_value=1),
        ) as activate_due,
        patch(
            "app.modules.students.read_service.StudentRepository.list_for_tenant",
            new=AsyncMock(return_value=([], 0)),
        ) as list_students,
    ):
        items, total = await StudentReadService.list_students(db, actor)

    assert items == []
    assert total == 0
    activate_due.assert_awaited_once_with(db, tenant_id=tenant_id)
    list_students.assert_awaited_once()
