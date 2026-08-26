from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.modules.student_academics.models import AcademicSessionStatus
from app.modules.students.enrollment_schemas import StudentClassChangeRequest
from app.modules.students.enrollment_service import StudentEnrollmentService
from app.modules.students.models import (
    AcademicStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
)
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentEnrollmentDetailResponse
from app.modules.students.service import StudentService
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository


def _segment(*, ended_on: date | None = None) -> StudentEnrollment:
    return StudentEnrollment(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        academic_level_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        started_on=date(2026, 8, 1),
        ended_on=ended_on,
        entry_outcome=StudentEnrollmentOutcome.ENROLLED,
        entry_reason="Initial admission",
        exit_outcome=(StudentEnrollmentOutcome.RECLASSIFIED if ended_on else None),
        exit_reason=("Moved class" if ended_on else None),
    )


def test_current_state_is_derived_and_not_writable() -> None:
    current = _segment()
    ended = _segment(ended_on=date(2026, 8, 10))

    assert current.is_current is True
    assert ended.is_current is False
    with pytest.raises(AttributeError):
        current.is_current = False

    assert not hasattr(StudentEnrollment, "outcome")
    assert not hasattr(StudentEnrollment, "reason")
    assert not hasattr(StudentEnrollment, "changed_by_admin_id")


def test_class_change_contract_rejects_progression_outcome() -> None:
    with pytest.raises(ValidationError):
        StudentClassChangeRequest(
            target_class_id=uuid.uuid4(),
            academic_session_id=uuid.uuid4(),
            effective_date=date(2026, 8, 20),
            reason="Correct arm placement",
            outcome="repeated",
        )


def test_enrollment_history_schema_exposes_entry_exit_metadata_and_level_name() -> None:
    now = datetime.now(timezone.utc)
    response = StudentEnrollmentDetailResponse(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        student_id=uuid.uuid4(),
        academic_level_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        academic_session_id=uuid.uuid4(),
        started_on=date(2026, 8, 1),
        ended_on=date(2026, 8, 10),
        entry_outcome=StudentEnrollmentOutcome.ENROLLED,
        exit_outcome=StudentEnrollmentOutcome.RECLASSIFIED,
        entry_reason="Initial admission",
        exit_reason="Correct arm placement",
        created_by_admin_id=uuid.uuid4(),
        ended_by_admin_id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        academic_level_name="JSS 1",
    )

    dumped = response.model_dump()
    assert dumped["academic_level_name"] == "JSS 1"
    assert dumped["entry_outcome"] == "enrolled"
    assert dumped["exit_outcome"] == "reclassified"
    assert "outcome" not in dumped
    assert "is_current" not in dumped


@pytest.mark.asyncio
async def test_class_change_splits_placement_on_effective_date(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    level_id = uuid.uuid4()
    old_class_id = uuid.uuid4()
    target_class_id = uuid.uuid4()
    session_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    student = SimpleNamespace(
        id=student_id,
        tenant_id=tenant_id,
        status=AcademicStatus.ACTIVE,
    )
    current = SimpleNamespace(
        id=uuid.uuid4(),
        student_id=student_id,
        academic_level_id=level_id,
        class_id=old_class_id,
        academic_session_id=session_id,
        started_on=date(2026, 8, 1),
    )
    target_class = SimpleNamespace(
        id=target_class_id,
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )
    session = SimpleNamespace(
        id=session_id,
        is_current=True,
        status=AcademicSessionStatus.OPEN,
    )
    actor = SimpleNamespace(id=admin_id, tenant_id=tenant_id)
    payload = StudentClassChangeRequest(
        target_class_id=target_class_id,
        academic_session_id=session_id,
        effective_date=date(2026, 8, 20),
        reason="Correct arm placement",
    )

    monkeypatch.setattr(
        "app.modules.students.enrollment_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(ClassRoomRepository, "get_by_id", AsyncMock(return_value=target_class))
    monkeypatch.setattr(
        AcademicSessionLifecycleRepository,
        "get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=current),
    )
    monkeypatch.setattr(
        StudentEnrollmentService,
        "_ensure_specialization_transfer_safe",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StudentEnrollmentService,
        "_ensure_backdated_split_safe",
        AsyncMock(),
    )
    close_segment = AsyncMock(return_value=current)
    create_segment = AsyncMock()
    monkeypatch.setattr(StudentEnrollmentService, "_close_segment", close_segment)
    monkeypatch.setattr(StudentEnrollmentService, "_create_segment", create_segment)
    monkeypatch.setattr(StudentService, "_build_detail_response", AsyncMock(return_value=object()))

    db = AsyncMock()
    await StudentEnrollmentService.change_class(
        db,
        actor=actor,
        student_id=student_id,
        payload=payload,
    )

    assert close_segment.await_args.kwargs["ended_on"] == date(2026, 8, 19)
    assert close_segment.await_args.kwargs["outcome"] == StudentEnrollmentOutcome.RECLASSIFIED
    assert create_segment.await_args.kwargs["started_on"] == date(2026, 8, 20)
    assert create_segment.await_args.kwargs["class_id"] == target_class_id
    assert create_segment.await_args.kwargs["outcome"] == StudentEnrollmentOutcome.RECLASSIFIED
    db.commit.assert_awaited_once()
