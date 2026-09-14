from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from app.core.exceptions import ConflictException
from app.modules.classes.models import ArmLabel
from app.modules.classes.repository import ArmLabelRepository
from app.modules.classes.schemas import ArmLabelUpdate
from app.modules.classes.service import ArmLabelService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes():
    with patch(
        "app.modules.classes.service.ensure_academic_write_window",
        new=AsyncMock(),
    ) as guard:
        yield guard


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


def _arm_label(
    tenant_id: uuid.UUID,
    *,
    label: str = "A",
    active: bool = True,
) -> ArmLabel:
    now = datetime.now(timezone.utc)
    return ArmLabel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        label=label,
        normalized_label=label.upper(),
        is_active=active,
        created_at=now,
        updated_at=now,
    )


def test_arm_label_model_has_archive_actor_metadata_contract() -> None:
    column = ArmLabel.__table__.columns.archived_by_admin_id
    assert column.nullable is True
    assert len(column.foreign_keys) == 1
    assert next(iter(column.foreign_keys)).ondelete == "SET NULL"

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in ArmLabel.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    archive_contract = constraints["ck_arm_labels_archive_metadata_consistency"]
    assert "archived_at IS NULL AND archived_by_admin_id IS NULL" in archive_contract
    assert "archived_at IS NOT NULL AND is_active = false" in archive_contract


def test_arm_label_patch_is_identity_only() -> None:
    assert set(ArmLabelUpdate.model_fields) == {"label"}
    with pytest.raises(ValidationError):
        ArmLabelUpdate(is_active=False)


@pytest.mark.asyncio
async def test_unused_arm_label_can_be_renamed() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 0, "classes_live": 0}),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_normalized_label",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        response = await ArmLabelService.update(
            db,
            _admin(tenant_id),
            row.id,
            ArmLabelUpdate(label="B"),
        )

    assert response.label == "B"
    assert row.normalized_label == "B"


@pytest.mark.asyncio
async def test_used_arm_label_cannot_be_renamed() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 2, "classes_live": 0}),
        ),
    ):
        with pytest.raises(ConflictException, match="can no longer be renamed") as exc_info:
            await ArmLabelService.update(
                AsyncMock(),
                _admin(tenant_id),
                row.id,
                ArmLabelUpdate(label="B"),
            )

    assert exc_info.value.payload == {"dependency_counts": {"classes_total": 2, "classes_live": 0}}


@pytest.mark.asyncio
async def test_duplicate_arm_label_rename_is_rejected() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)
    duplicate = _arm_label(tenant_id, label="B")

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 0, "classes_live": 0}),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_normalized_label",
            new=AsyncMock(return_value=duplicate),
        ),
    ):
        with pytest.raises(ConflictException, match="already exists"):
            await ArmLabelService.update(
                AsyncMock(),
                _admin(tenant_id),
                row.id,
                ArmLabelUpdate(label="B"),
            )


@pytest.mark.asyncio
async def test_non_admin_listing_is_forced_to_active_only() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)

    with patch(
        "app.modules.classes.service.ArmLabelRepository.list_for_tenant",
        new=AsyncMock(return_value=[]),
    ) as list_labels:
        await ArmLabelService.list(
            AsyncMock(),
            actor,
            active_only=False,
            include_archived=True,
        )

    list_labels.assert_awaited_once_with(
        ANY,
        tenant_id,
        active_only=True,
        include_archived=False,
    )


@pytest.mark.asyncio
async def test_admin_listing_can_explicitly_include_archived() -> None:
    tenant_id = uuid.uuid4()
    db = AsyncMock()

    with patch(
        "app.modules.classes.service.ArmLabelRepository.list_for_tenant",
        new=AsyncMock(return_value=[]),
    ) as list_labels:
        await ArmLabelService.list(
            db,
            _admin(tenant_id),
            active_only=False,
            include_archived=True,
        )

    list_labels.assert_awaited_once_with(
        db,
        tenant_id,
        active_only=False,
        include_archived=True,
    )


@pytest.mark.asyncio
async def test_active_classrooms_block_arm_label_deactivation() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 3, "classes_live": 1}),
        ),
    ):
        with pytest.raises(ConflictException, match="active classrooms") as exc_info:
            await ArmLabelService.deactivate(AsyncMock(), _admin(tenant_id), row.id)

    assert exc_info.value.payload == {"dependency_counts": {"classes_live": 1}}


@pytest.mark.asyncio
async def test_historical_classes_do_not_block_deactivation() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 3, "classes_live": 0}),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        response = await ArmLabelService.deactivate(db, _admin(tenant_id), row.id)

    assert response.is_active is False


@pytest.mark.asyncio
async def test_archive_requires_arm_label_to_be_inactive() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=True)

    with patch(
        "app.modules.classes.service.ArmLabelRepository.get_by_id",
        new=AsyncMock(return_value=row),
    ):
        with pytest.raises(ConflictException, match="Deactivate the arm label"):
            await ArmLabelService.archive(AsyncMock(), _admin(tenant_id), row.id)


@pytest.mark.asyncio
async def test_historical_usage_can_be_archived_and_records_actor() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=False)
    admin = _admin(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 4, "classes_live": 0}),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        response = await ArmLabelService.archive(db, admin, row.id)

    assert response.is_active is False
    assert response.archived_at is not None
    assert response.archived_by_admin_id == admin.id


@pytest.mark.asyncio
async def test_restore_clears_archive_metadata_and_remains_inactive() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=False)
    row.archived_at = datetime.now(timezone.utc)
    row.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        response = await ArmLabelService.restore(db, _admin(tenant_id), row.id)

    assert response.archived_at is None
    assert response.archived_by_admin_id is None
    assert response.is_active is False


@pytest.mark.asyncio
async def test_archived_arm_label_cannot_activate_directly() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=False)
    row.archived_at = datetime.now(timezone.utc)

    with patch(
        "app.modules.classes.service.ArmLabelRepository.get_by_id",
        new=AsyncMock(return_value=row),
    ):
        with pytest.raises(ConflictException, match="Restore this arm label"):
            await ArmLabelService.activate(AsyncMock(), _admin(tenant_id), row.id)


@pytest.mark.asyncio
async def test_unused_arm_label_can_be_hard_deleted() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 0, "classes_live": 0}),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.delete",
            new=AsyncMock(),
        ) as delete_label,
    ):
        response = await ArmLabelService.hard_delete(db, _admin(tenant_id), row.id)

    assert response.id == row.id
    delete_label.assert_awaited_once_with(db, row)


@pytest.mark.asyncio
async def test_historical_usage_permanently_blocks_hard_delete() -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=False)

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.count_dependencies",
            new=AsyncMock(return_value={"classes_total": 1, "classes_live": 0}),
        ),
    ):
        with pytest.raises(ConflictException, match="permanently deleted"):
            await ArmLabelService.hard_delete(AsyncMock(), _admin(tenant_id), row.id)


@pytest.mark.asyncio
async def test_repository_dependency_snapshot_distinguishes_total_and_live_classes() -> None:
    tenant_id = uuid.uuid4()
    arm_label_id = uuid.uuid4()
    result = MagicMock()
    result.one.return_value = SimpleNamespace(classes_total=5, classes_live=2)
    db = AsyncMock()
    db.execute.return_value = result

    dependencies = await ArmLabelRepository.count_dependencies(
        db,
        tenant_id,
        arm_label_id,
    )

    assert dependencies == {"classes_total": 5, "classes_live": 2}


def test_arm_label_routes_expose_explicit_lifecycle() -> None:
    from app.modules.classes.router import router

    route_methods = {(route.path, frozenset(route.methods or set())) for route in router.routes}
    expected = {
        ("/classes/arm-labels/{arm_label_id}/activate", frozenset({"POST"})),
        ("/classes/arm-labels/{arm_label_id}/deactivate", frozenset({"POST"})),
        ("/classes/arm-labels/{arm_label_id}/archive", frozenset({"POST"})),
        ("/classes/arm-labels/{arm_label_id}/restore", frozenset({"POST"})),
        ("/classes/arm-labels/{arm_label_id}", frozenset({"DELETE"})),
    }
    assert expected <= route_methods


@pytest.mark.asyncio
async def test_arm_label_mutations_use_academic_write_guard(_allow_academic_writes) -> None:
    tenant_id = uuid.uuid4()
    row = _arm_label(tenant_id, active=False)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        await ArmLabelService.activate(db, _admin(tenant_id), row.id)

    _allow_academic_writes.assert_awaited_once_with(db, tenant_id=tenant_id)
