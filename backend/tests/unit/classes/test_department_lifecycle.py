from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.department_service import DepartmentPoolService
from app.modules.classes.models import AcademicLevelDepartment, Department
from app.modules.classes.schemas import (
    AcademicLevelDepartmentCreate,
    DepartmentCreate,
    DepartmentUpdate,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes():
    with patch(
        "app.modules.classes.department_service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


@pytest.mark.asyncio
async def test_creation_normalizes_exact_duplicate_key_and_scopes_lookup_to_tenant() -> None:
    tenant_id = uuid.uuid4()
    lookup = AsyncMock(return_value=None)

    async def add(_db, row):
        _stamp(row)
        return row

    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_normalized_name",
            new=lookup,
        ),
        patch("app.modules.classes.department_service.CanonicalDepartmentRepository.add", new=add),
    ):
        response = await DepartmentPoolService.create_department(
            AsyncMock(), _admin(tenant_id), DepartmentCreate(name="  Applied   Science  ")
        )

    lookup.assert_awaited_once_with(ANY, tenant_id, "applied science")
    assert response.name == "Applied Science"


@pytest.mark.asyncio
async def test_exact_duplicate_is_rejected_but_typo_like_name_is_not_fuzzy_blocked() -> None:
    tenant_id = uuid.uuid4()
    with patch(
        "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_normalized_name",
        new=AsyncMock(return_value=_department(tenant_id)),
    ):
        with pytest.raises(ConflictException, match="already exists"):
            await DepartmentPoolService.create_department(
                AsyncMock(), _admin(tenant_id), DepartmentCreate(name=" SCIENCE ")
            )

    async def add(_db, row):
        _stamp(row)
        return row

    typo_lookup = AsyncMock(return_value=None)
    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_normalized_name",
            new=typo_lookup,
        ),
        patch("app.modules.classes.department_service.CanonicalDepartmentRepository.add", new=add),
    ):
        response = await DepartmentPoolService.create_department(
            AsyncMock(), _admin(tenant_id), DepartmentCreate(name="SCIEINCE")
        )
    assert response.name == "SCIEINCE"
    typo_lookup.assert_awaited_once_with(ANY, tenant_id, "scieince")


@pytest.mark.asyncio
async def test_update_duplicate_lookup_remains_tenant_scoped() -> None:
    tenant_id = uuid.uuid4()
    row = _department(tenant_id)
    lookup = AsyncMock(return_value=_department(tenant_id, name="Commercial"))
    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_normalized_name",
            new=lookup,
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.count_level_links",
            new=AsyncMock(return_value={"level_links_total": 0, "level_links_active": 0}),
        ),
    ):
        with pytest.raises(ConflictException, match="already exists"):
            await DepartmentPoolService.update_department(
                AsyncMock(), _admin(tenant_id), row.id, DepartmentUpdate(name="Commercial")
            )
    lookup.assert_awaited_once_with(ANY, tenant_id, "commercial")


@pytest.mark.asyncio
async def test_active_level_links_block_canonical_deactivation() -> None:
    tenant_id = uuid.uuid4()
    row = _department(tenant_id)
    counts = {"level_links_total": 2, "level_links_active": 1}
    counter = AsyncMock(return_value=counts)
    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.count_level_links",
            new=counter,
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await DepartmentPoolService.deactivate_department(
                AsyncMock(), _admin(tenant_id), row.id
            )
    counter.assert_awaited_once_with(ANY, tenant_id, row.id)
    assert exc_info.value.payload == {"dependency_counts": counts}


@pytest.mark.asyncio
async def test_canonical_lifecycle_is_active_then_inactive_then_archived() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    row = _department(tenant_id)
    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.count_level_links",
            new=AsyncMock(return_value={"level_links_total": 0, "level_links_active": 0}),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.save",
            new=AsyncMock(return_value=row),
        ),
    ):
        inactive = await DepartmentPoolService.deactivate_department(AsyncMock(), actor, row.id)
        archived = await DepartmentPoolService.archive_department(AsyncMock(), actor, row.id)
    assert inactive.is_active is False
    assert archived.archived_at is not None
    assert archived.archived_by_admin_id == actor.id


@pytest.mark.asyncio
async def test_canonical_delete_rechecks_history_and_only_deletes_unused_rows() -> None:
    tenant_id = uuid.uuid4()
    row = _department(tenant_id, active=False, archived=True)
    delete = AsyncMock()
    get_row = AsyncMock(return_value=row)

    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=get_row,
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.count_level_links",
            new=AsyncMock(return_value={"level_links_total": 1, "level_links_active": 0}),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.delete",
            new=delete,
        ),
    ):
        with pytest.raises(ConflictException):
            await DepartmentPoolService.delete_department(AsyncMock(), _admin(tenant_id), row.id)
    delete.assert_not_awaited()
    get_row.assert_awaited_with(ANY, tenant_id, row.id, lock=True)

    db = AsyncMock()
    with (
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.count_level_links",
            new=AsyncMock(return_value={"level_links_total": 0, "level_links_active": 0}),
        ),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.delete",
            new=delete,
        ),
    ):
        response = await DepartmentPoolService.delete_department(db, _admin(tenant_id), row.id)
    assert response.id == row.id
    delete.assert_awaited_once_with(db, row)


@pytest.mark.asyncio
async def test_attach_to_level_uses_actor_tenant_for_both_lookups() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    department = _department(tenant_id)
    get_department = AsyncMock(return_value=department)
    get_mapping = AsyncMock(return_value=None)
    returned_link = _link(tenant_id, level_id, department)

    async def add(_db, row):
        _stamp(row)
        return row

    with (
        patch.object(DepartmentPoolService, "_eligible_level", new=AsyncMock()),
        patch(
            "app.modules.classes.department_service.CanonicalDepartmentRepository.get_by_id",
            new=get_department,
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.get_for_level_department",
            new=get_mapping,
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.add", new=add
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=returned_link),
        ),
    ):
        await DepartmentPoolService.attach_to_level(
            AsyncMock(),
            _admin(tenant_id),
            level_id,
            AcademicLevelDepartmentCreate(department_id=department.id),
        )
    get_department.assert_awaited_once_with(ANY, tenant_id, department.id, lock=True)
    get_mapping.assert_awaited_once_with(ANY, tenant_id, level_id, department.id, lock=True)


@pytest.mark.asyncio
async def test_live_mapping_dependencies_block_deactivation_but_history_only_allows_it() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    row = _link(tenant_id, level_id, _department(tenant_id))
    with (
        patch.object(DepartmentPoolService, "_link", new=AsyncMock(return_value=row)),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.count_dependencies",
            new=AsyncMock(
                return_value=_counts(class_assignments_total=1, class_assignments_live=1)
            ),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await DepartmentPoolService.deactivate_level_department(
                AsyncMock(), _admin(tenant_id), level_id, row.id
            )
    assert exc_info.value.payload == {"dependency_counts": {"class_assignments_live": 1}}

    with (
        patch.object(DepartmentPoolService, "_link", new=AsyncMock(return_value=row)),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.count_dependencies",
            new=AsyncMock(
                return_value=_counts(
                    class_assignments_total=1,
                    curriculum_subject_links_total=1,
                )
            ),
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.save",
            new=AsyncMock(return_value=row),
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.get_by_id",
            new=AsyncMock(return_value=row),
        ),
    ):
        response = await DepartmentPoolService.deactivate_level_department(
            AsyncMock(), _admin(tenant_id), level_id, row.id
        )
    assert response.is_active is False


@pytest.mark.asyncio
async def test_mapping_delete_blocks_history_and_allows_a_truly_unused_link() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    row = _link(tenant_id, level_id, _department(tenant_id), active=False)
    delete = AsyncMock()
    with (
        patch.object(DepartmentPoolService, "_link", new=AsyncMock(return_value=row)),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts(curriculum_subject_links_total=1)),
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.delete",
            new=delete,
        ),
    ):
        with pytest.raises(ConflictException):
            await DepartmentPoolService.delete_level_department(
                AsyncMock(), _admin(tenant_id), level_id, row.id
            )
    delete.assert_not_awaited()

    db = AsyncMock()
    with (
        patch.object(DepartmentPoolService, "_link", new=AsyncMock(return_value=row)),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.count_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.department_service.AcademicLevelDepartmentRepository.delete",
            new=delete,
        ),
    ):
        response = await DepartmentPoolService.delete_level_department(
            db, _admin(tenant_id), level_id, row.id
        )
    assert response.id == row.id
    delete.assert_awaited_once_with(db, row)


@pytest.mark.asyncio
async def test_mapping_lookup_rejects_a_link_from_another_level() -> None:
    tenant_id = uuid.uuid4()
    row = _link(tenant_id, uuid.uuid4(), _department(tenant_id))
    with patch(
        "app.modules.classes.department_service.AcademicLevelDepartmentRepository.get_by_id",
        new=AsyncMock(return_value=row),
    ):
        with pytest.raises(NotFoundException):
            await DepartmentPoolService._link(AsyncMock(), _admin(tenant_id), uuid.uuid4(), row.id)


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


def _stamp(row) -> None:
    now = datetime.now(timezone.utc)
    row.id = getattr(row, "id", None) or uuid.uuid4()
    row.created_at = getattr(row, "created_at", None) or now
    row.updated_at = now


def _department(
    tenant_id: uuid.UUID, *, name: str = "Science", active: bool = True, archived: bool = False
) -> Department:
    now = datetime.now(timezone.utc)
    return Department(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        normalized_name=name.casefold(),
        is_active=active,
        archived_at=now if archived else None,
        archived_by_admin_id=uuid.uuid4() if archived else None,
        created_at=now,
        updated_at=now,
    )


def _link(
    tenant_id: uuid.UUID, level_id: uuid.UUID, department: Department, *, active: bool = True
) -> AcademicLevelDepartment:
    now = datetime.now(timezone.utc)
    return AcademicLevelDepartment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level_id,
        department_id=department.id,
        department=department,
        is_active=active,
        archived_at=None,
        archived_by_admin_id=None,
        created_at=now,
        updated_at=now,
    )


def _counts(
    *,
    class_assignments_total: int = 0,
    class_assignments_live: int = 0,
    curriculum_subject_links_total: int = 0,
    curriculum_subject_links_live: int = 0,
) -> dict[str, int]:
    return {
        "class_assignments_total": class_assignments_total,
        "class_assignments_live": class_assignments_live,
        "curriculum_subject_links_total": curriculum_subject_links_total,
        "curriculum_subject_links_live": curriculum_subject_links_live,
    }
