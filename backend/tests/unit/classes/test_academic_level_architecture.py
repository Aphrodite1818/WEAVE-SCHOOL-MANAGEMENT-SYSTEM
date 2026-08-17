from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from app.core.exceptions import ConflictException
from app.modules.classes.models import (
    AcademicCategory,
    AcademicLevel,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.classes.schemas import ArmLabelCreate, ClassRoomCreate, ClassRoomUpdate
from app.modules.classes.service import ArmLabelService, ClassRoomService
from app.modules.student_academics.curriculum_models import CurriculumSubject
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.schemas import TeacherAssignmentCreate
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@pytest.fixture(autouse=True)
def _allow_academic_writes_for_class_unit_tests():
    with patch(
        "app.modules.classes.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


def test_classroom_contract_requires_level_and_concrete_arm() -> None:
    arm_label_id = uuid.uuid4()
    payload = ClassRoomCreate(academic_level_id=uuid.uuid4(), arm_label_id=arm_label_id)
    assert payload.arm_label_id == arm_label_id

    with pytest.raises(ValidationError):
        ClassRoomCreate(academic_level_id=uuid.uuid4())


def test_teacher_assignment_contract_is_concrete_class_and_curriculum_subject() -> None:
    payload = TeacherAssignmentCreate(
        teacher_membership_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        academic_term_id=uuid.uuid4(),
    )
    assert payload.class_id
    assert payload.curriculum_subject_id
    assert payload.academic_term_id
    assert "level_subject_id" not in payload.model_dump()


def test_academic_tables_expose_canonical_foreign_keys() -> None:
    assert "normalized_name" in AcademicLevel.__table__.columns
    assert "academic_level_id" in ClassRoom.__table__.columns
    assert "arm_label_id" in ClassRoom.__table__.columns
    assert "normalized_arm" not in ClassRoom.__table__.columns
    assert "curriculum_id" in CurriculumSubject.__table__.columns
    assert "subject_id" in CurriculumSubject.__table__.columns
    assert "class_id" in TeacherAssignment.__table__.columns
    assert "curriculum_subject_id" in TeacherAssignment.__table__.columns
    assert "level_subject_id" not in TeacherAssignment.__table__.columns


def test_department_name_uniqueness_is_scoped_to_academic_level() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in Department.__table__.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }

    assert constraints["uq_departments_tenant_level_name"] == (
        "tenant_id",
        "academic_level_id",
        "normalized_name",
    )
    assert "uq_departments_tenant_name" not in constraints
    assert Department.__table__.columns.academic_level_id.nullable is False


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
                payload=ClassRoomUpdate(arm_label_id=uuid.uuid4()),
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
            "app.modules.classes.service.ArmLabelRepository.get_by_id",
            new=AsyncMock(return_value=classroom.arm_label_ref),
        ),
        patch(
            "app.modules.classes.service.ClassRoomRepository.get_by_level_arm_label",
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


@pytest.mark.asyncio
async def test_duplicate_arm_labels_are_rejected_per_tenant() -> None:
    tenant_id = uuid.uuid4()
    with patch(
        "app.modules.classes.service.ArmLabelRepository.get_by_normalized_label",
        new=AsyncMock(return_value=object()),
    ):
        with pytest.raises(ConflictException, match="Arm label with this name already exists"):
            await ArmLabelService.create(
                db=AsyncMock(),
                actor=_admin(tenant_id),
                payload=ArmLabelCreate(label=" a "),
            )


def test_arm_label_can_be_reused_across_levels() -> None:
    tenant_id = uuid.uuid4()
    arm_label = ArmLabel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        label="A",
        normalized_label="a",
        is_active=True,
    )
    jss1 = _classroom(tenant_id, arm_label=arm_label)
    jss2 = _classroom(tenant_id, arm_label=arm_label)
    jss2.academic_level_id = uuid.uuid4()

    assert jss1.arm_label_id == jss2.arm_label_id
    assert jss1.display_name.endswith(" A")
    assert jss2.display_name.endswith(" A")


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


def _classroom(
    tenant_id: uuid.UUID,
    *,
    active: bool = True,
    arm_label: ArmLabel | None = None,
) -> ClassRoom:
    now = datetime.now(timezone.utc)
    level = AcademicLevel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="JSS1",
        normalized_name="JSS1",
        category=AcademicCategory.JUNIOR_SECONDARY,
        position=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    arm_label = arm_label or ArmLabel(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        label="A",
        normalized_label="a",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    return ClassRoom(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level.id,
        academic_level=level,
        arm_label_id=arm_label.id,
        arm_label_ref=arm_label,
        is_active=active,
        created_at=now,
        updated_at=now,
    )
