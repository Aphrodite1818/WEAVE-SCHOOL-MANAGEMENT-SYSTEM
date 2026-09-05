from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest

from app.core.exceptions import ConflictException
from app.modules.students.enrollment_schemas import StudentClassPlacementRequest
from app.modules.students.lifecycle_service import (
    LegacyStudentLifecycleService,
    StudentLifecycleService,
)
from app.modules.students.models import AcademicStatus
from app.modules.students.placement_service import StudentPlacementService
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentHardDeleteEligibilityResponse
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode


@pytest.mark.asyncio
async def test_bulk_placement_locks_students_in_deterministic_uuid_order(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session_id = uuid.uuid4()
    level_id = uuid.uuid4()
    target_class_id = uuid.uuid4()
    lower_id = uuid.UUID(int=1)
    higher_id = uuid.UUID(int=2)

    students = {
        lower_id: SimpleNamespace(id=lower_id, status=AcademicStatus.ACTIVE),
        higher_id: SimpleNamespace(id=higher_id, status=AcademicStatus.ACTIVE),
    }
    enrollments = {
        student_id: SimpleNamespace(
            id=uuid.uuid4(),
            student_id=student_id,
            academic_session_id=session_id,
            academic_level_id=level_id,
            class_id=None,
            started_on=date.today(),
            entry_outcome=None,
        )
        for student_id in students
    }
    target_class = SimpleNamespace(id=target_class_id, academic_level_id=level_id)
    lock_order: list[uuid.UUID] = []

    async def get_student(_db, _tenant_id, student_id, *, lock=False, **_kwargs):
        assert lock is True
        lock_order.append(student_id)
        return students[student_id]

    async def get_enrollment(_db, _tenant_id, student_id, *, lock=False):
        assert lock is True
        return enrollments[student_id]

    monkeypatch.setattr(
        "app.modules.students.placement_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StudentPlacementService,
        "_require_open_session",
        AsyncMock(return_value=SimpleNamespace(id=session_id)),
    )
    monkeypatch.setattr(
        StudentPlacementService,
        "_require_target_class",
        AsyncMock(return_value=target_class),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(side_effect=get_student))
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(side_effect=get_enrollment),
    )
    monkeypatch.setattr(StudentEnrollmentRepository, "save", AsyncMock())

    db = SimpleNamespace(commit=AsyncMock())
    payload = StudentClassPlacementRequest(
        student_ids=[higher_id, lower_id],
        academic_session_id=session_id,
        academic_level_id=level_id,
        target_class_id=target_class_id,
    )

    # Request normalization establishes the lock order before the service iterates.
    assert payload.student_ids == [lower_id, higher_id]

    response = await StudentPlacementService.place_class(
        db,
        actor=SimpleNamespace(id=admin_id, tenant_id=tenant_id),
        payload=payload,
    )

    assert lock_order == [lower_id, higher_id]
    assert response.placed_student_ids == [lower_id, higher_id]
    assert response.placed_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_restore_archived_student_enforces_student_quota(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)
    archived_student = SimpleNamespace(id=student_id, is_archived=True)
    restored = SimpleNamespace(id=student_id)

    quota_lock = AsyncMock()
    ensure_limit = AsyncMock()
    legacy_restore = AsyncMock(return_value=restored)
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=archived_student))
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.acquire_resource_quota_lock",
        quota_lock,
    )
    monkeypatch.setattr(
        SubscriptionFeatureService,
        "ensure_resource_limit_available",
        ensure_limit,
    )
    monkeypatch.setattr(LegacyStudentLifecycleService, "restore", legacy_restore)

    result = await StudentLifecycleService.restore(
        SimpleNamespace(),
        actor=actor,
        student_id=student_id,
        reason="Restore accidental archive",
    )

    assert result is restored
    StudentRepository.get_by_id.assert_awaited_once_with(
        ANY,
        tenant_id,
        student_id,
        include_archived=True,
    )
    quota_lock.assert_awaited_once_with(
        ANY,
        tenant_id=tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    ensure_limit.assert_awaited_once_with(
        ANY,
        tenant_id,
        ResourceLimitCode.STUDENTS,
    )
    legacy_restore.assert_awaited_once()


@pytest.mark.asyncio
async def test_hard_delete_eligibility_blocks_student_with_login_history(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    base = StudentHardDeleteEligibilityResponse(
        student_id=student_id,
        eligible=True,
        blocking_dependencies=[],
        recommendation="hard_delete",
    )
    student = SimpleNamespace(id=student_id, last_login_at=datetime.now(timezone.utc))

    monkeypatch.setattr(
        LegacyStudentLifecycleService,
        "hard_delete_eligibility",
        AsyncMock(return_value=base),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))

    result = await StudentLifecycleService.hard_delete_eligibility(
        SimpleNamespace(),
        tenant_id=tenant_id,
        student_id=student_id,
    )

    assert result.eligible is False
    assert result.recommendation == "archive"
    assert result.blocking_dependencies == ["login_history"]


@pytest.mark.asyncio
async def test_hard_delete_execution_rejects_student_with_login_history(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    student_id = uuid.uuid4()
    actor = SimpleNamespace(id=uuid.uuid4(), tenant_id=tenant_id)
    student = SimpleNamespace(id=student_id, last_login_at=datetime.now(timezone.utc))
    legacy_delete = AsyncMock()

    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(LegacyStudentLifecycleService, "hard_delete", legacy_delete)

    with pytest.raises(ConflictException, match="login history"):
        await StudentLifecycleService.hard_delete(
            SimpleNamespace(),
            actor=actor,
            student_id=student_id,
        )

    legacy_delete.assert_not_awaited()
