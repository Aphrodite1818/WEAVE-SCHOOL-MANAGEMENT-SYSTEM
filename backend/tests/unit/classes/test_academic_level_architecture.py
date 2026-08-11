from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.modules.classes.models import AcademicLevel, ClassRoom
from app.core.exceptions import ConflictException
from app.modules.classes.schemas import ClassRoomCreate, ClassRoomUpdate
from app.modules.classes.service import ClassRoomService
from app.modules.student_academics.models import LevelSubject, TeacherAssignment
from app.modules.student_academics.schemas import TeacherAssignmentCreate
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def test_classroom_contract_requires_explicit_level_and_arm() -> None:
    payload = ClassRoomCreate(academic_level_id=uuid.uuid4(), arm=" A ")
    assert payload.arm == "A"

    with pytest.raises(ValidationError):
        ClassRoomCreate(academic_level_id=uuid.uuid4(), arm="")


def test_teacher_assignment_contract_is_concrete_class_and_level_subject() -> None:
    payload = TeacherAssignmentCreate(
        teacher_membership_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        level_subject_id=uuid.uuid4(),
    )
    assert payload.class_id
    assert payload.level_subject_id
    assert "class_subject_id" not in payload.model_dump()


def test_academic_tables_expose_canonical_foreign_keys() -> None:
    assert "normalized_name" in AcademicLevel.__table__.columns
    assert "academic_level_id" in ClassRoom.__table__.columns
    assert "normalized_arm" in ClassRoom.__table__.columns
    assert "academic_level_id" in LevelSubject.__table__.columns
    assert "class_id" in TeacherAssignment.__table__.columns
    assert "level_subject_id" in TeacherAssignment.__table__.columns


@pytest.mark.asyncio
async def test_archived_class_arm_cannot_be_updated() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id, active=False)
    classroom.archived_at = datetime.now(timezone.utc)
    with patch(
        "app.modules.classes.service.ClassRoomRepository.get_by_id",
        new=AsyncMock(return_value=classroom),
    ):
        with pytest.raises(ConflictException, match="Archived classrooms cannot be updated"):
            await ClassRoomService.update_classroom(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                class_id=classroom.id,
                payload=ClassRoomUpdate(arm="B"),
            )


@pytest.mark.asyncio
async def test_class_teacher_can_be_explicitly_unassigned() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    classroom.teacher_membership_id = uuid.uuid4()
    db = AsyncMock()

    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.AcademicLevelRepository.get_by_id",
            new=AsyncMock(return_value=classroom.academic_level),
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
            payload=ClassRoomUpdate(teacher_membership_id=None),
        )

    assert classroom.teacher_membership_id is None
    assert response.teacher_membership_id is None


@pytest.mark.asyncio
async def test_class_arm_with_live_enrollment_cannot_be_deactivated() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id)
    with (
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_assigned_students_by_status",
            new=AsyncMock(side_effect=[0, 0]),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.count_current_enrollments",
            new=AsyncMock(return_value=1),
        ),
    ):
        with pytest.raises(ConflictException, match="current student enrollments"):
            await ClassRoomService.deactivate_classroom(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                class_id=classroom.id,
            )


@pytest.mark.asyncio
async def test_restored_class_arm_remains_inactive() -> None:
    tenant_id = uuid.uuid4()
    classroom = _classroom(tenant_id, active=False)
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
    assert response.is_active is False
    assert response.archived_at is None


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


def _classroom(tenant_id: uuid.UUID, *, active: bool = True) -> ClassRoom:
    now = datetime.now(timezone.utc)
    level = AcademicLevel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="JSS1",
        normalized_name="JSS1",
        is_active=True,
        is_terminal=False,
        created_at=now,
        updated_at=now,
    )
    return ClassRoom(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level.id,
        academic_level=level,
        arm="A",
        normalized_arm="A",
        is_active=active,
        created_at=now,
        updated_at=now,
    )
