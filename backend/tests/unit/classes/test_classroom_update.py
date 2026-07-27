from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import ClassRoom
from app.modules.classes.schemas import ClassRoomUpdate
from app.modules.classes.service import ClassRoomService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def _classroom(tenant_id: uuid.UUID) -> ClassRoom:
    now = datetime.now(timezone.utc)
    return ClassRoom(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="PRIMARY1",
        normalized_name="PRIMARY1",
        arm="A",
        normalized_arm="A",
        teacher_membership_id=uuid.uuid4(),
        next_class_id=None,
        is_terminal=False,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_classroom_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ),
    ):
        response = await ClassRoomService.update_classroom(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
            payload=ClassRoomUpdate(
                name=None,
                arm=None,
                teacher_membership_id=None,
            ),
        )

    assert classroom.name == "PRIMARY1"
    assert classroom.arm == "A"
    assert classroom.teacher_membership_id is not None
    assert classroom.is_active is True
    assert response.name == "PRIMARY1"


@pytest.mark.asyncio
async def test_update_classroom_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_normalized_name_and_arm",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ),
    ):
        response = await ClassRoomService.update_classroom(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
            payload=ClassRoomUpdate(name="Primary 2"),
        )

    assert classroom.name == "PRIMARY2"
    assert classroom.normalized_name == "PRIMARY2"
    assert classroom.arm == "A"
    assert classroom.is_active is True
    assert response.name == "PRIMARY2"


@pytest.mark.asyncio
async def test_update_classroom_rejects_archived_classroom() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    classroom.archived_at = datetime.now(timezone.utc)
    classroom.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with patch(
        "app.modules.classes.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(ConflictException):
            await ClassRoomService.update_classroom(
                db=db,
                actor=_admin(tenant_id),
                class_id=classroom.id,
                payload=ClassRoomUpdate(name="Primary 2"),
            )
