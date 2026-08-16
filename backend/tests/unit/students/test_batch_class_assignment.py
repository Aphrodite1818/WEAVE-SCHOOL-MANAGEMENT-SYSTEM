from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.students.models import AcademicStatus
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentBatchClassAssignmentRequest
from app.modules.students.schemas import StudentClassChangeRequest
from app.modules.students.service import StudentEnrollmentService
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository
from app.modules.student_academics.models import AcademicSessionStatus


@pytest.mark.asyncio
async def test_batch_class_assignment_places_classless_students_atomically(monkeypatch):
    tenant_id = uuid4()
    admin_id = uuid4()
    level_id = uuid4()
    student = SimpleNamespace(
        id=uuid4(), admission_number="STD-1", is_archived=False, class_id=None
    )
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
    monkeypatch.setattr(
        StudentEnrollmentRepository, "get_current", AsyncMock(return_value=enrollment)
    )
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
    ClassRoomRepository.get_by_id.assert_awaited_once_with(db, tenant_id, target.id, lock=True)


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
    monkeypatch.setattr(
        StudentEnrollmentRepository, "get_current", AsyncMock(return_value=enrollment)
    )

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


@pytest.mark.asyncio
async def test_single_class_reassignment_updates_current_enrollment_in_place(monkeypatch):
    tenant_id = uuid4()
    admin_id = uuid4()
    session_id = uuid4()
    level_id = uuid4()
    student = SimpleNamespace(
        id=uuid4(),
        admission_number="STD-3",
        is_archived=False,
        class_id=uuid4(),
        status=AcademicStatus.ACTIVE,
    )
    enrollment = SimpleNamespace(
        id=uuid4(),
        student_id=student.id,
        academic_session_id=session_id,
        academic_level_id=level_id,
        class_id=student.class_id,
        is_current=True,
        ended_on=None,
        outcome=None,
        reason=None,
        changed_by_admin_id=None,
    )
    target = SimpleNamespace(
        id=uuid4(),
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )
    session = SimpleNamespace(
        id=session_id,
        is_current=True,
        status=AcademicSessionStatus.OPEN,
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(ClassRoomRepository, "get_by_id", AsyncMock(return_value=target))
    monkeypatch.setattr(
        AcademicSessionLifecycleRepository,
        "get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=enrollment),
    )
    monkeypatch.setattr(StudentEnrollmentRepository, "save", AsyncMock())
    monkeypatch.setattr(StudentEnrollmentRepository, "add", AsyncMock())
    monkeypatch.setattr(StudentRepository, "save", AsyncMock())
    monkeypatch.setattr(
        "app.modules.students.service.StudentService._build_detail_response",
        AsyncMock(return_value=SimpleNamespace(id=student.id)),
    )
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    await StudentEnrollmentService.change_class(
        db,
        actor=SimpleNamespace(id=admin_id, tenant_id=tenant_id),
        student_id=student.id,
        payload=StudentClassChangeRequest(
            target_class_id=target.id,
            academic_session_id=session_id,
            reason="Move to another arm",
        ),
    )

    assert enrollment.is_current is True
    assert enrollment.ended_on is None
    assert enrollment.academic_level_id == level_id
    assert enrollment.class_id == target.id
    assert student.class_id == target.id
    StudentEnrollmentRepository.save.assert_awaited_once_with(db, enrollment)
    StudentEnrollmentRepository.add.assert_not_awaited()
