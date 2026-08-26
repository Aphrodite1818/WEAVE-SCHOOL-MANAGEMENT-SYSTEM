from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    AcademicLevelStatus,
    Department,
)
from app.modules.classes.schemas import DepartmentCreate, DepartmentUpdate
from app.modules.classes.service import DepartmentService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes_for_department_unit_tests():
    with patch(
        "app.modules.classes.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


@pytest.mark.asyncio
async def test_newly_created_department_is_active_and_not_archived() -> None:
    tenant_id = uuid.uuid4()
    level = _level(tenant_id)
    created: dict[str, Department] = {}

    async def add(_db, department):
        department.id = uuid.uuid4()
        department.created_at = datetime.now(timezone.utc)
        department.updated_at = department.created_at
        created["department"] = department
        return department

    with (
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service._tenant_institution_type",
            new=AsyncMock(return_value="secondary"),
        ),
        patch(
            "app.modules.classes.service.category_supports_departments",
            return_value=True,
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch("app.modules.classes.service.DepartmentRepository.add", new=add),
    ):
        response = await DepartmentService.create(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            academic_level_id=level.id,
            payload=DepartmentCreate(name=" Science "),
        )

    assert created["department"].is_active is True
    assert response.is_active is True
    assert response.archived_at is None
    assert response.archived_by_admin_id is None


@pytest.mark.asyncio
async def test_unused_department_can_be_renamed() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        response = await DepartmentService.update(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            department_id=department.id,
            payload=DepartmentUpdate(name=" Applied Science "),
        )

    assert department.name == "Applied Science"
    assert department.normalized_name == "applied science"
    assert response.name == "Applied Science"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependency_counts",
    [
        {
            "class_assignments_total": 1,
            "class_assignments_live": 0,
            "offerings_total": 0,
            "offerings_live": 0,
        },
        {
            "class_assignments_total": 0,
            "class_assignments_live": 0,
            "offerings_total": 1,
            "offerings_live": 0,
        },
    ],
)
async def test_department_with_any_usage_cannot_be_renamed(
    dependency_counts: dict[str, int],
) -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=dependency_counts),
        ),
    ):
        with pytest.raises(ConflictException, match="can no longer be renamed"):
            await DepartmentService.update(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
                payload=DepartmentUpdate(name="Commercial"),
            )


@pytest.mark.asyncio
async def test_duplicate_department_name_inside_same_level_is_rejected() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)
    existing = _department(tenant_id, level_id=department.academic_level_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_normalized_name",
            new=AsyncMock(return_value=existing),
        ),
    ):
        with pytest.raises(ConflictException, match="already exists"):
            await DepartmentService.update(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
                payload=DepartmentUpdate(name="Commercial"),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("dependency_counts", "expected_key"),
    [
        (
            {
                "class_assignments_total": 0,
                "class_assignments_live": 1,
                "offerings_total": 0,
                "offerings_live": 0,
            },
            "class_assignments_live",
        ),
        (
            {
                "class_assignments_total": 0,
                "class_assignments_live": 0,
                "offerings_total": 0,
                "offerings_live": 1,
            },
            "offerings_live",
        ),
    ],
)
async def test_live_dependencies_block_deactivation(
    dependency_counts: dict[str, int],
    expected_key: str,
) -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=dependency_counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await DepartmentService.deactivate(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
            )

    assert exc_info.value.payload == {"dependency_counts": {expected_key: 1}}


@pytest.mark.asyncio
async def test_historical_dependencies_do_not_block_deactivation_or_archive() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    department = _department(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts(class_assignments_total=1, offerings_total=1)),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        deactivated = await DepartmentService.deactivate(db, actor, department.id)
        archived = await DepartmentService.archive(db, actor, department.id)

    assert deactivated.is_active is False
    assert archived.archived_at is not None
    assert archived.archived_by_admin_id == actor.id


@pytest.mark.asyncio
async def test_deactivation_sets_department_inactive() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        response = await DepartmentService.deactivate(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            department_id=department.id,
        )

    assert department.is_active is False
    assert response.is_active is False


@pytest.mark.asyncio
async def test_inactive_department_can_activate_when_parent_level_is_active() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id, active=False)
    level = _level(tenant_id, level_id=department.academic_level_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service._tenant_institution_type",
            new=AsyncMock(return_value="secondary"),
        ),
        patch(
            "app.modules.classes.service.category_supports_departments",
            return_value=True,
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        response = await DepartmentService.activate(
            db=AsyncMock(),
            actor=_admin(tenant_id),
            department_id=department.id,
        )

    assert response.is_active is True


@pytest.mark.asyncio
async def test_department_activation_fails_when_parent_level_is_not_active() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id, active=False)
    level = _level(
        tenant_id,
        level_id=department.academic_level_id,
        status=AcademicLevelStatus.INACTIVE,
    )

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
    ):
        with pytest.raises(ConflictException, match="academic level must be active"):
            await DepartmentService.activate(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
            )


@pytest.mark.asyncio
async def test_archived_department_cannot_activate_directly() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id, active=False, archived=True)

    with patch(
        "app.modules.classes.service.DepartmentRepository.get_by_id",
        new=AsyncMock(return_value=department),
    ):
        with pytest.raises(ConflictException, match="Restore this department"):
            await DepartmentService.activate(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
            )


@pytest.mark.asyncio
async def test_archive_requires_department_to_already_be_inactive() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id, active=True)

    with patch(
        "app.modules.classes.service.DepartmentRepository.get_by_id",
        new=AsyncMock(return_value=department),
    ):
        with pytest.raises(ConflictException, match="Deactivate the department"):
            await DepartmentService.archive(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
            )


@pytest.mark.asyncio
async def test_archive_stores_timestamp_and_actor_metadata() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    department = _department(tenant_id, active=False)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        response = await DepartmentService.archive(
            db=AsyncMock(),
            actor=actor,
            department_id=department.id,
        )

    assert response.is_active is False
    assert response.archived_at is not None
    assert response.archived_by_admin_id == actor.id


@pytest.mark.asyncio
async def test_restore_clears_archive_metadata_and_leaves_department_inactive() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    department = _department(tenant_id, active=False, archived=True, archived_by=actor.id)
    level = _level(tenant_id, level_id=department.academic_level_id)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
    ):
        response = await DepartmentService.restore(
            db=AsyncMock(),
            actor=actor,
            department_id=department.id,
        )

    assert response.is_active is False
    assert response.archived_at is None
    assert response.archived_by_admin_id is None


@pytest.mark.asyncio
async def test_hard_delete_succeeds_only_when_dependency_counts_are_zero() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.delete",
            new=AsyncMock(),
        ) as delete_department,
    ):
        response = await DepartmentService.hard_delete(
            db=db,
            actor=_admin(tenant_id),
            department_id=department.id,
        )

    assert response.id == department.id
    delete_department.assert_awaited_once_with(db, department)


@pytest.mark.asyncio
async def test_hard_delete_fails_permanently_once_historical_usage_exists() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id)
    counts = _counts(class_assignments_total=1)

    with (
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await DepartmentService.hard_delete(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
            )

    assert exc_info.value.payload == {"dependency_counts": counts}


@pytest.mark.asyncio
async def test_archived_department_cannot_be_updated() -> None:
    tenant_id = uuid.uuid4()
    department = _department(tenant_id, active=False, archived=True)

    with patch(
        "app.modules.classes.service.DepartmentRepository.get_by_id",
        new=AsyncMock(return_value=department),
    ):
        with pytest.raises(ConflictException, match="Archived departments cannot be updated"):
            await DepartmentService.update(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                department_id=department.id,
                payload=DepartmentUpdate(name="Commercial"),
            )


@pytest.mark.asyncio
async def test_lifecycle_mutations_respect_academic_write_window() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    department = _department(tenant_id, active=False)
    level = _level(tenant_id, level_id=department.academic_level_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ensure_academic_write_window",
            new=AsyncMock(),
        ) as write_window,
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_id",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service._tenant_institution_type",
            new=AsyncMock(return_value="secondary"),
        ),
        patch(
            "app.modules.classes.service.category_supports_departments",
            return_value=True,
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.get_by_normalized_name",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.save",
            new=AsyncMock(return_value=department),
        ),
        patch(
            "app.modules.classes.service.DepartmentRepository.delete",
            new=AsyncMock(),
        ),
    ):
        await DepartmentService.activate(db, actor, department.id)
        await DepartmentService.deactivate(db, actor, department.id)
        await DepartmentService.update(db, actor, department.id, DepartmentUpdate(name="Science"))
        await DepartmentService.archive(db, actor, department.id)
        await DepartmentService.restore(db, actor, department.id)
        await DepartmentService.hard_delete(db, actor, department.id)

    assert write_window.await_count == 6
    write_window.assert_any_await(db, tenant_id=tenant_id)


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


def _level(
    tenant_id: uuid.UUID,
    *,
    level_id: uuid.UUID | None = None,
    status: AcademicLevelStatus = AcademicLevelStatus.ACTIVE,
) -> AcademicLevel:
    now = datetime.now(timezone.utc)
    return AcademicLevel(
        id=level_id or uuid.uuid4(),
        tenant_id=tenant_id,
        name="SS1",
        normalized_name="ss1",
        category=AcademicCategory.SENIOR_SECONDARY,
        position=1,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _department(
    tenant_id: uuid.UUID,
    *,
    level_id: uuid.UUID | None = None,
    active: bool = True,
    archived: bool = False,
    archived_by: uuid.UUID | None = None,
) -> Department:
    now = datetime.now(timezone.utc)
    return Department(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level_id or uuid.uuid4(),
        name="Science",
        normalized_name="science",
        is_active=active,
        archived_at=now if archived else None,
        archived_by_admin_id=archived_by if archived else None,
        created_at=now,
        updated_at=now,
    )


def _counts(
    *,
    class_assignments_total: int = 0,
    class_assignments_live: int = 0,
    offerings_total: int = 0,
    offerings_live: int = 0,
) -> dict[str, int]:
    return {
        "class_assignments_total": class_assignments_total,
        "class_assignments_live": class_assignments_live,
        "offerings_total": offerings_total,
        "offerings_live": offerings_live,
    }
