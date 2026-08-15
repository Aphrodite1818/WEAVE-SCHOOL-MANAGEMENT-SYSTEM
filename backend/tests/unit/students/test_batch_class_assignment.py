from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentBatchClassAssignmentRequest
from app.modules.students.service import StudentEnrollmentService


@pytest.mark.asyncio
async def test_batch_class_assignment_places_classless_students_atomically(monkeypatch):
    tenant_id = uuid4()
    admin_id = uuid4()
    level_id = uuid4()
    student = SimpleNamespace(id=uuid4(), admission_number="STD-1", is_archived=False, class_id=None)
    enrollment = SimpleNamespace(
        student_id=student.id,
        academic_level_id=level_id,
        class_id=None,
        reason=None,
        changed_by_admin_id=None,
    )
    target = SimpleNamespace(
        id=uuid4(),
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )
    monkeypatch.setattr(ClassRoomRepository, "get_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(StudentRepository, "save", AsyncMock())
    monkeypatch.setattr(StudentEnrollmentRepository, "get_current", AsyncMock(return_value=enrollment))
    monkeypatch.setattr(StudentEnrollmentRepository, "save", AsyncMock())
    db = SimpleNamespace(commit=AsyncMock())

    response = await StudentEnrollmentService.assign_class_batch(
        db,
        actor=SimpleNamespace(id=admin_id, tenant_id=tenant_id),
        payload=StudentBatchClassAssignmentRequest(
            student_ids=[student.id],
            target_class_id=target.id,
            reason="Operational placement",
        ),
    )

    assert response.updated_count == 1
    assert enrollment.class_id == target.id
    assert student.class_id == target.id
    db.commit.assert_awaited_once()
    ClassRoomRepository.get_by_id.assert_awaited_once_with(
        db, tenant_id, target.id, lock=True
    )


@pytest.mark.asyncio
async def test_batch_class_assignment_rejects_cross_level_placement(monkeypatch):
    tenant_id = uuid4()
    student = SimpleNamespace(id=uuid4(), admission_number="STD-2", is_archived=False)
    enrollment = SimpleNamespace(academic_level_id=uuid4())
    target = SimpleNamespace(
        id=uuid4(),
        academic_level_id=uuid4(),
        is_active=True,
        archived_at=None,
    )
    monkeypatch.setattr(ClassRoomRepository, "get_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(StudentEnrollmentRepository, "get_current", AsyncMock(return_value=enrollment))

    with pytest.raises(BadRequestException, match="not enrolled in the target class level"):
        await StudentEnrollmentService.assign_class_batch(
            SimpleNamespace(commit=AsyncMock()),
            actor=SimpleNamespace(id=uuid4(), tenant_id=tenant_id),
            payload=StudentBatchClassAssignmentRequest(
                student_ids=[student.id],
                target_class_id=target.id,
                reason="Invalid level placement",
            ),
        )
