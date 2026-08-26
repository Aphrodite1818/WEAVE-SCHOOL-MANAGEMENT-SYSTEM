from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock

import pytest

from app.core.exceptions import ConflictException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository
from app.modules.students.enrollment_schemas import StudentBatchClassAssignmentRequest
from app.modules.students.enrollment_service import StudentEnrollmentService
from app.modules.students.lifecycle_service import (
    LegacyStudentLifecycleService,
    StudentLifecycleService,
)
from app.modules.students.models import AcademicStatus
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentHardDeleteEligibilityResponse
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode


@pytest.mark.asyncio
async def test_split_effective_today_checks_same_day_academic_evidence(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    enrollment = SimpleNamespace(id=uuid.uuid4())
    dependency_counts = AsyncMock(return_value={"attendance": 1, "results": 0})
    monkeypatch.setattr(
        StudentEnrollmentService,
        "_segment_dependency_counts",
        dependency_counts,
    )

    with pytest.raises(ConflictException, match="preserved academic evidence"):
        await StudentEnrollmentService._ensure_backdated_split_safe(
            SimpleNamespace(),
            tenant_id=tenant_id,
            enrollment=enrollment,
            effective_date=date.today(),
        )

    assert dependency_counts.await_args.kwargs["on_or_after"] == date.today()


@pytest.mark.asyncio
async def test_batch_placement_locks_students_in_deterministic_uuid_order(monkeypatch) -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    session_id = uuid.uuid4()
    level_id = uuid.uuid4()
    target_class_id = uuid.uuid4()
    lower_id = uuid.UUID(int=1)
    higher_id = uuid.UUID(int=2)

    students = {
        lower_id: SimpleNamespace(
            id=lower_id,
            admission_number="STD-LOW",
            is_archived=False,
            status=AcademicStatus.ACTIVE,
        ),
        higher_id: SimpleNamespace(
            id=higher_id,
            admission_number="STD-HIGH",
            is_archived=False,
            status=AcademicStatus.ACTIVE,
        ),
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
            entry_reason=None,
            created_by_admin_id=None,
        )
        for student_id in students
    }
    target_class = SimpleNamespace(
        id=target_class_id,
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )
    session = SimpleNamespace(id=session_id)
    lock_order: list[uuid.UUID] = []

    async def get_student(_db, _tenant_id, student_id, *, lock=False, **_kwargs):
        assert lock is True
        lock_order.append(student_id)
        return students[student_id]

    async def get_enrollment(_db, _tenant_id, student_id, *, lock=False):
        assert lock is True
        return enrollments[student_id]

    monkeypatch.setattr(
        "app.modules.students.enrollment_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(ClassRoomRepository, "get_by_id", AsyncMock(return_value=target_class))
    monkeypatch.setattr(
        AcademicSessionLifecycleRepository,
        "get_current_open",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(side_effect=get_student))
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(side_effect=get_enrollment),
    )
    monkeypatch.setattr(
        StudentEnrollmentService,
        "_segment_dependency_counts",
        AsyncMock(return_value={"attendance": 0, "results": 0}),
    )
    monkeypatch.setattr(StudentEnrollmentRepository, "save", AsyncMock())

    db = SimpleNamespace(commit=AsyncMock())
    response = await StudentEnrollmentService.assign_class_batch(
        db,
        actor=SimpleNamespace(id=admin_id, tenant_id=tenant_id),
        payload=StudentBatchClassAssignmentRequest(
            student_ids=[higher_id, lower_id],
            target_class_id=target_class_id,
            effective_date=date.today(),
            reason="Initial arm placement",
        ),
    )

    assert lock_order == [lower_id, higher_id]
    assert response.updated_student_ids == [lower_id, higher_id]
    assert response.updated_count == 2
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
    student = SimpleNamespace(
        id=student_id,
        last_login_at=datetime.now(timezone.utc),
    )

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
    student = SimpleNamespace(
        id=student_id,
        last_login_at=datetime.now(timezone.utc),
    )
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
