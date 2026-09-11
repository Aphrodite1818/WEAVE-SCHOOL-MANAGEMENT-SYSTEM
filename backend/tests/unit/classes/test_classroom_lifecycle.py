from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    AcademicLevelStatus,
    ArmLabel,
    ClassRoom,
)
from app.modules.classes.repository import ClassRoomRepository
from app.modules.classes.schemas import ClassRoomUpdate
from app.modules.classes.service import ClassRoomService
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.models import (
    TeacherAssignment,
    TeacherAssignmentLifecycleAudit,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes():
    with patch(
        "app.modules.classes.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="classroom-admin@example.test",
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


def _arm(
    tenant_id: uuid.UUID,
    *,
    arm_id: uuid.UUID | None = None,
    active: bool = True,
    archived: bool = False,
) -> ArmLabel:
    now = datetime.now(timezone.utc)
    return ArmLabel(
        id=arm_id or uuid.uuid4(),
        tenant_id=tenant_id,
        label="A",
        normalized_label="a",
        is_active=active,
        archived_at=now if archived else None,
        created_at=now,
        updated_at=now,
    )


def _classroom(
    tenant_id: uuid.UUID,
    *,
    active: bool = True,
    archived: bool = False,
    level: AcademicLevel | None = None,
    arm: ArmLabel | None = None,
    teacher_membership_id: uuid.UUID | None = None,
) -> ClassRoom:
    now = datetime.now(timezone.utc)
    level = level or _level(tenant_id)
    arm = arm or _arm(tenant_id)
    return ClassRoom(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level.id,
        arm_label_id=arm.id,
        teacher_membership_id=teacher_membership_id,
        is_active=active,
        archived_at=now if archived else None,
        archived_by_admin_id=uuid.uuid4() if archived else None,
        academic_level=level,
        arm_label_ref=arm,
        created_at=now,
        updated_at=now,
    )


def _counts(**overrides: int) -> dict[str, int]:
    values = {
        "students_assigned_total": 0,
        "students_assigned_live": 0,
        "enrollments_total": 0,
        "enrollments_current": 0,
        "teacher_assignments_total": 0,
        "teacher_assignments_active": 0,
        "teacher_assignment_audits_total": 0,
        "department_assignments_total": 0,
        "department_assignments_live": 0,
        "results_total": 0,
        "results_live": 0,
        "attendance_sheets_total": 0,
        "attendance_sheets_live": 0,
        "report_cards_total": 0,
        "report_cards_live": 0,
        "progression_items_total": 0,
        "progression_items_live": 0,
        "notice_audiences_total": 0,
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_unused_classroom_can_change_structural_identity() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    room = _classroom(tenant_id)
    new_level_id = uuid.uuid4()
    db = AsyncMock()

    get_by_id = AsyncMock(side_effect=[room, room])
    with (
        patch("app.modules.classes.service.ClassRoomRepository.get_by_id", new=get_by_id),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._validate_structure",
            new=AsyncMock(),
        ) as validate_structure,
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_level_arm_label",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=room),
        ),
    ):
        await ClassRoomService.update_classroom(
            db,
            actor,
            room.id,
            ClassRoomUpdate(academic_level_id=new_level_id),
        )

    assert room.academic_level_id == new_level_id
    validate_structure.assert_awaited_once_with(db, tenant_id, new_level_id, room.arm_label_id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependency_counts",
    [
        _counts(enrollments_total=1),
        _counts(teacher_assignments_total=1),
        _counts(department_assignments_total=1),
        _counts(results_total=1),
        _counts(attendance_sheets_total=1),
        _counts(report_cards_total=1),
        _counts(progression_items_total=1),
        _counts(notice_audiences_total=1),
    ],
)
async def test_used_classroom_cannot_change_level_or_arm(
    dependency_counts: dict[str, int],
) -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id)

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(return_value=dependency_counts),
        ),
    ):
        with pytest.raises(ConflictException, match="locked after the class is first used"):
            await ClassRoomService.update_classroom(
                AsyncMock(),
                _admin(tenant_id),
                room.id,
                ClassRoomUpdate(arm_label_id=uuid.uuid4()),
            )


@pytest.mark.asyncio
async def test_homeroom_teacher_can_change_after_classroom_has_history() -> None:
    tenant_id = uuid.uuid4()
    old_teacher_id = uuid.uuid4()
    new_teacher_id = uuid.uuid4()
    room = _classroom(tenant_id, teacher_membership_id=old_teacher_id)
    get_by_id = AsyncMock(side_effect=[room, room])
    count_dependencies = AsyncMock(return_value=_counts(enrollments_total=4, results_total=12))

    with (
        patch("app.modules.classes.service.ClassRoomRepository.get_by_id", new=get_by_id),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=count_dependencies,
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._validate_teacher",
            new=AsyncMock(),
        ) as validate_teacher,
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._teacher_membership",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._complete_class_teacher_guide",
            new=AsyncMock(),
        ) as complete_guide,
        patch(
            "app.modules.classes.service.ClassRoomService._queue_first_class_teacher_guide",
            new=AsyncMock(),
        ) as queue_guide,
    ):
        await ClassRoomService.update_classroom(
            AsyncMock(),
            _admin(tenant_id),
            room.id,
            ClassRoomUpdate(teacher_membership_id=new_teacher_id),
        )

    assert room.teacher_membership_id == new_teacher_id
    validate_teacher.assert_awaited_once()
    count_dependencies.assert_not_awaited()
    complete_guide.assert_awaited_once()
    queue_guide.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("students_assigned_live", 1),
        ("enrollments_current", 1),
        ("teacher_assignments_active", 1),
        ("department_assignments_live", 1),
        ("results_live", 1),
        ("attendance_sheets_live", 1),
        ("report_cards_live", 1),
        ("progression_items_live", 1),
    ],
)
async def test_live_dependencies_block_classroom_deactivation(key: str, value: int) -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id)
    counts = _counts(**{key: value})

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await ClassRoomService.deactivate_classroom(AsyncMock(), _admin(tenant_id), room.id)

    assert exc_info.value.payload == {"dependency_counts": {key: value}}


@pytest.mark.asyncio
async def test_historical_dependencies_allow_deactivate_and_archive() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    room = _classroom(tenant_id)
    historical = _counts(
        enrollments_total=20,
        teacher_assignments_total=4,
        department_assignments_total=3,
        results_total=60,
        attendance_sheets_total=80,
        report_cards_total=20,
    )
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(side_effect=[historical, historical]),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=room),
        ),
    ):
        deactivated = await ClassRoomService.deactivate_classroom(db, actor, room.id)
        archived = await ClassRoomService.archive_classroom(db, actor, room.id)

    assert deactivated.is_active is False
    assert archived.archived_at is not None
    assert archived.archived_by_admin_id == actor.id


@pytest.mark.asyncio
async def test_activation_revalidates_level_and_arm() -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id, active=False)
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._validate_structure",
            new=AsyncMock(),
        ) as validate_structure,
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=room),
        ),
    ):
        response = await ClassRoomService.activate_classroom(db, _admin(tenant_id), room.id)

    validate_structure.assert_awaited_once_with(
        db, tenant_id, room.academic_level_id, room.arm_label_id
    )
    assert response.is_active is True


@pytest.mark.asyncio
async def test_activation_fails_when_parent_structure_is_not_operational() -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id, active=False)

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._validate_structure",
            new=AsyncMock(side_effect=BadRequestException("Academic level must be active")),
        ),
    ):
        with pytest.raises(BadRequestException, match="Academic level must be active"):
            await ClassRoomService.activate_classroom(AsyncMock(), _admin(tenant_id), room.id)


@pytest.mark.asyncio
async def test_restore_clears_archive_metadata_and_stays_inactive() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    level = _level(tenant_id)
    arm = _arm(tenant_id)
    room = _classroom(tenant_id, active=False, archived=True, level=level, arm=arm)

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=level),
        ),
        patch(
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=arm),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=room),
        ),
    ):
        response = await ClassRoomService.restore_classroom(AsyncMock(), actor, room.id)

    assert response.is_active is False
    assert response.archived_at is None
    assert response.archived_by_admin_id is None


@pytest.mark.asyncio
async def test_restore_rejects_non_archived_classroom() -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id, active=False)

    with patch(
        "app.modules.classes.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=room),
    ):
        with pytest.raises(ConflictException, match="Only archived classrooms"):
            await ClassRoomService.restore_classroom(AsyncMock(), _admin(tenant_id), room.id)


@pytest.mark.asyncio
async def test_historical_usage_permanently_blocks_hard_delete() -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id, active=False)
    counts = _counts(results_total=1)

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(return_value=counts),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await ClassRoomService.purge_setup_classroom(AsyncMock(), _admin(tenant_id), room.id)

    assert exc_info.value.payload == {"dependency_counts": counts}


@pytest.mark.asyncio
async def test_never_used_classroom_can_be_hard_deleted() -> None:
    tenant_id = uuid.uuid4()
    room = _classroom(tenant_id)
    db = AsyncMock()
    delete = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_class_dependencies",
            new=AsyncMock(return_value=_counts()),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.delete_classroom",
            new=delete,
        ),
    ):
        response = await ClassRoomService.purge_setup_classroom(db, _admin(tenant_id), room.id)

    assert response.id == room.id
    delete.assert_awaited_once_with(db, room)


@pytest.mark.asyncio
async def test_non_admin_cannot_fetch_inactive_or_archived_classroom_by_id() -> None:
    tenant_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id)

    for room in (
        _classroom(tenant_id, active=False),
        _classroom(tenant_id, active=False, archived=True),
    ):
        with patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=room),
        ):
            with pytest.raises(NotFoundException, match="Classroom not found"):
                await ClassRoomService.get_classroom_by_id(AsyncMock(), actor, room.id)


@pytest.mark.asyncio
async def test_classroom_dependency_snapshot_exposes_total_and_live_contract() -> None:
    values = _counts(
        students_assigned_total=2,
        students_assigned_live=1,
        enrollments_total=3,
        enrollments_current=1,
        results_total=7,
        results_live=2,
    )
    row = SimpleNamespace(**values)
    result = MagicMock()
    result.one.return_value = row
    db = AsyncMock()
    db.execute.return_value = result

    snapshot = await ClassRoomRepository.count_class_dependencies(db, uuid.uuid4(), uuid.uuid4())

    assert snapshot == values


@pytest.mark.asyncio
@pytest.mark.parametrize(("remaining_class", "expected_calls"), [(None, 1), (uuid.uuid4(), 0)])
async def test_class_teacher_guide_completes_only_after_last_class_is_removed(
    remaining_class: uuid.UUID | None,
    expected_calls: int,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = remaining_class
    db = AsyncMock()
    db.execute.return_value = result
    teacher = SimpleNamespace(teacher_account_id=uuid.uuid4())

    with patch(
        "app.modules.classes.service.UserGuideService.complete_if_unfinished",
        new=AsyncMock(),
    ) as complete:
        await ClassRoomService._complete_class_teacher_guide(
            db,
            teacher=teacher,
            exclude_class_id=uuid.uuid4(),
        )

    assert complete.await_count == expected_calls


def test_classroom_history_foreign_keys_use_restrict() -> None:
    department_fk = next(iter(ClassTermDepartmentAssignment.__table__.c.class_id.foreign_keys))
    teacher_fk = next(iter(TeacherAssignment.__table__.c.class_id.foreign_keys))
    audit_fk = next(iter(TeacherAssignmentLifecycleAudit.__table__.c.class_id.foreign_keys))

    assert department_fk.ondelete == "RESTRICT"
    assert teacher_fk.ondelete == "RESTRICT"
    assert audit_fk.ondelete == "RESTRICT"


def test_classroom_archive_metadata_constraint_is_consistent() -> None:
    names = {
        constraint.name
        for constraint in ClassRoom.__table__.constraints
        if constraint.name is not None
    }
    assert "ck_classes_archive_metadata_consistency" in names
