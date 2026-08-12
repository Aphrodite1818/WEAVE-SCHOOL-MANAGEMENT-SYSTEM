from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.classes.models import AcademicLevelProgressionMode, ClassRoom
from app.modules.student_academics.models import (
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
)
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentEnrollment,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_worker_creates_stable_awaiting_selection_without_graduating(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    student = Student(
        id=uuid4(),
        tenant_id=tenant_id,
        admission_number="WEAVE-001",
        first_name="Ada",
        last_name="Lovelace",
        status=AcademicStatus.ACTIVE,
        account_status=StudentAccountStatus.ACTIVE,
        is_active=True,
        is_verified=True,
        is_archived=False,
        promotion_hold=False,
        created_at=_now(),
        updated_at=_now(),
    )
    source_level_id = uuid4()
    source_class = ClassRoom(
        id=uuid4(),
        tenant_id=tenant_id,
        academic_level_id=source_level_id,
        arm="A",
        normalized_arm="A",
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )
    enrollment = StudentEnrollment(
        id=uuid4(),
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=source_class.id,
        academic_session_id=uuid4(),
        started_on=date(2025, 9, 1),
        is_current=True,
        created_at=_now(),
        updated_at=_now(),
    )
    run = StudentProgressionRun(
        id=uuid4(),
        tenant_id=tenant_id,
        academic_session_id=enrollment.academic_session_id,
        next_academic_session_id=uuid4(),
        idempotency_key="selection-test-run",
        created_at=_now(),
        updated_at=_now(),
    )
    actor = TenantAdmin(
        id=uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hash",
        account_status=TenantAdminStatus.ACTIVE,
        is_active=True,
        is_verified=True,
        created_at=_now(),
        updated_at=_now(),
    )

    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_item_by_run_and_student",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicLevelRepository.get_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=source_level_id,
                progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
            )
        ),
    )
    save_enrollment = AsyncMock(side_effect=lambda _db, value: value)
    save_student = AsyncMock(side_effect=lambda _db, value: value)
    add_next_enrollment = AsyncMock()
    add_item = AsyncMock(side_effect=lambda _db, value: value)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentEnrollmentRepository.save",
        save_enrollment,
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentEnrollmentRepository.add",
        add_next_enrollment,
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentRepository.save",
        save_student,
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.add_item",
        add_item,
    )

    item = await AcademicProgressionService._progress_student(
        AsyncMock(),
        actor=actor,
        run=run,
        enrollment=enrollment,
        classroom=source_class,
        target_class=None,
        next_session=SimpleNamespace(id=run.next_academic_session_id),
        effective_date=date(2026, 7, 31),
    )

    assert item.action == StudentProgressionItemAction.STUDENT_SELECTION
    assert item.status == StudentProgressionItemStatus.AWAITING_SELECTION
    assert enrollment.is_current is False
    assert enrollment.ended_on == date(2026, 7, 31)
    assert student.status == AcademicStatus.ACTIVE
    assert student.account_status == StudentAccountStatus.ACTIVE
    assert student.is_active is True
    assert student.class_id is None
    add_next_enrollment.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_retry_returns_existing_pending_item(monkeypatch) -> None:
    existing = SimpleNamespace(status=StudentProgressionItemStatus.AWAITING_SELECTION)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_item_by_run_and_student",
        AsyncMock(return_value=existing),
    )
    result = await AcademicProgressionService._progress_student(
        AsyncMock(),
        actor=SimpleNamespace(tenant_id=uuid4()),
        run=SimpleNamespace(id=uuid4()),
        enrollment=SimpleNamespace(student_id=uuid4()),
        classroom=SimpleNamespace(),
        target_class=None,
        next_session=SimpleNamespace(),
        effective_date=date.today(),
    )
    assert result is existing
