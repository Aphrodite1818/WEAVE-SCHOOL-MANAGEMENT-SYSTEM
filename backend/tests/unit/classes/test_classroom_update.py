from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.classes.models import ClassRoom
from app.modules.classes.schemas import (
    ClassProgressionConfigureRequest,
    ClassRoomActivateRequest,
    ClassRoomDeactivateRequest,
    ClassRoomUpdate,
)
from app.modules.classes.service import ClassRoomService
from app.modules.students.schemas import StudentCreate
from app.modules.students.service import StudentService
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("counts", "message"),
    [
        (
            {"active_students": 1},
            "active students",
        ),
        (
            {"suspended_students": 1},
            "suspended students",
        ),
        (
            {"current_enrollments": 1},
            "current student enrollments",
        ),
        (
            {"active_mappings": 1},
            "active subject mappings",
        ),
        (
            {"active_assignments": 1},
            "active teacher assignments",
        ),
    ],
)
async def test_deactivate_classroom_rejects_live_dependencies(
    counts: dict[str, int],
    message: str,
) -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()
    patches = _dependency_patches(**counts)

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patches[0],
        patches[1],
        patches[2],
        patches[3],
    ):
        with pytest.raises(ConflictException, match=message):
            await ClassRoomService.deactivate_classroom(
                db=db,
                actor=_admin(tenant_id),
                class_id=classroom.id,
            )


@pytest.mark.asyncio
async def test_deactivate_classroom_allows_only_historical_dependencies() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()
    patches = _dependency_patches()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ),
        patches[0],
        patches[1],
        patches[2],
        patches[3],
    ):
        response = await ClassRoomService.deactivate_classroom(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
        )

    assert classroom.is_active is False
    assert response.is_active is False


@pytest.mark.asyncio
async def test_archive_classroom_rejects_active_classroom() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.classes.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(ConflictException, match="Deactivate the class first"):
            await ClassRoomService.archive_classroom(
                db=db,
                actor=_admin(tenant_id),
                class_id=classroom.id,
            )


@pytest.mark.asyncio
async def test_archive_classroom_allows_inactive_dependency_free_classroom() -> None:
    tenant_id = uuid.uuid4()
    actor = _admin(tenant_id)
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    db = AsyncMock()
    patches = _dependency_patches()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ),
        patches[0],
        patches[1],
        patches[2],
        patches[3],
    ):
        response = await ClassRoomService.archive_classroom(
            db=db,
            actor=actor,
            class_id=classroom.id,
        )

    assert classroom.is_active is False
    assert classroom.archived_at is not None
    assert classroom.archived_by_admin_id == actor.id
    assert response.archived_at is not None


@pytest.mark.asyncio
async def test_restore_classroom_returns_to_inactive() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    classroom.archived_at = datetime.now(timezone.utc)
    classroom.archived_by_admin_id = uuid.uuid4()
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
        response = await ClassRoomService.restore_classroom(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
        )

    assert classroom.is_active is False
    assert classroom.archived_at is None
    assert classroom.archived_by_admin_id is None
    assert response.is_active is False


@pytest.mark.asyncio
async def test_configure_class_progression_sets_next_class() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    next_classroom = _classroom(tenant_id)
    next_classroom.id = uuid.uuid4()
    next_classroom.name = "PRIMARY2"
    next_classroom.normalized_name = "PRIMARY2"
    db = AsyncMock()

    async def get_by_id(*, class_id: uuid.UUID, **_: object) -> ClassRoom | None:
        if class_id == classroom.id:
            return classroom
        if class_id == next_classroom.id:
            return next_classroom
        return None

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(side_effect=get_by_id),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ),
    ):
        response = await ClassRoomService.configure_class_progression(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
            payload=ClassProgressionConfigureRequest(next_class_id=next_classroom.id),
        )

    assert classroom.next_class_id == next_classroom.id
    assert classroom.is_terminal is False
    assert response.next_class_id == next_classroom.id
    assert response.next_class_name == "PRIMARY2"


@pytest.mark.asyncio
async def test_configure_class_progression_rejects_self_reference() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    db = AsyncMock()

    with patch(
        "app.modules.classes.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(BadRequestException):
            await ClassRoomService.configure_class_progression(
                db=db,
                actor=_admin(tenant_id),
                class_id=classroom.id,
                payload=ClassProgressionConfigureRequest(next_class_id=classroom.id),
            )


@pytest.mark.asyncio
async def test_create_student_rejects_inactive_classroom() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    db = AsyncMock()

    with patch(
        "app.modules.students.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(NotFoundException, match="inactive"):
            await StudentService.create_student_profile(
                db=db,
                actor=_admin(tenant_id),
                payload=_student_payload(classroom.id),
            )


@pytest.mark.asyncio
async def test_create_student_rejects_archived_classroom() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    classroom.archived_at = datetime.now(timezone.utc)
    classroom.archived_by_admin_id = uuid.uuid4()
    db = AsyncMock()

    with patch(
        "app.modules.students.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(NotFoundException, match="inactive"):
            await StudentService.create_student_profile(
                db=db,
                actor=_admin(tenant_id),
                payload=_student_payload(classroom.id),
            )


@pytest.mark.asyncio
async def test_activate_classroom_rejects_inactive_assigned_teacher() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.is_active = False
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomService._validate_teacher_assignment",
            new=AsyncMock(side_effect=BadRequestException("Cannot assign an inactive teacher")),
        ),
    ):
        with pytest.raises(BadRequestException, match="inactive teacher"):
            await ClassRoomService.activate_classroom(
                db=db,
                actor=_admin(tenant_id),
                class_id=classroom.id,
            )


@pytest.mark.asyncio
async def test_activate_classroom_is_idempotent_when_already_active() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.teacher_membership_id = None
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.save",
            new=AsyncMock(return_value=classroom),
        ) as save_mock,
    ):
        response = await ClassRoomService.activate_classroom(
            db=db,
            actor=_admin(tenant_id),
            class_id=classroom.id,
        )

    assert response.is_active is True
    save_mock.assert_not_awaited()


def test_class_lifecycle_confirmation_literals_are_required() -> None:
    assert (
        ClassRoomActivateRequest(confirmation="ACTIVATE_CLASSROOM").confirmation
        == "ACTIVATE_CLASSROOM"
    )


def _student_payload(class_id: uuid.UUID) -> StudentCreate:
    return StudentCreate(
        first_name="Ada",
        last_name="Lovelace",
        date_of_birth=date(2015, 1, 1),
        class_id=class_id,
    )


def _dependency_patches(
    *,
    active_students: int = 0,
    suspended_students: int = 0,
    current_enrollments: int = 0,
    active_mappings: int = 0,
    active_assignments: int = 0,
):
    return (
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_assigned_students_by_status",
            new=AsyncMock(side_effect=[active_students, suspended_students]),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_current_enrollments",
            new=AsyncMock(return_value=current_enrollments),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_active_class_subjects",
            new=AsyncMock(return_value=active_mappings),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_active_teacher_assignments",
            new=AsyncMock(return_value=active_assignments),
        ),
    )
    assert (
        ClassRoomDeactivateRequest(confirmation="DEACTIVATE_CLASSROOM").confirmation
        == "DEACTIVATE_CLASSROOM"
    )

    with pytest.raises(ValidationError):
        ClassRoomActivateRequest(confirmation="DEACTIVATE_CLASSROOM")

    with pytest.raises(ValidationError):
        ClassRoomDeactivateRequest(confirmation="ACTIVATE_CLASSROOM")
