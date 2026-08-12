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


def _student(tenant_id):
    return Student(
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


def _classroom(*, tenant_id, level_id, arm="A"):
    return ClassRoom(
        id=uuid4(),
        tenant_id=tenant_id,
        academic_level_id=level_id,
        arm=arm,
        normalized_arm=arm.upper(),
        is_active=True,
        created_at=_now(),
        updated_at=_now(),
    )


def _enrollment(*, tenant_id, student_id, class_id):
    return StudentEnrollment(
        id=uuid4(),
        tenant_id=tenant_id,
        student_id=student_id,
        class_id=class_id,
        academic_session_id=uuid4(),
        started_on=date(2025, 9, 1),
        is_current=True,
        created_at=_now(),
        updated_at=_now(),
    )


def _run(*, tenant_id, academic_session_id):
    return StudentProgressionRun(
        id=uuid4(),
        tenant_id=tenant_id,
        academic_session_id=academic_session_id,
        next_academic_session_id=uuid4(),
        idempotency_key="selection-test-run",
        created_at=_now(),
        updated_at=_now(),
    )


def _actor(tenant_id):
    return TenantAdmin(
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


@pytest.mark.asyncio
async def test_worker_creates_stable_awaiting_selection_without_graduating(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    student = _student(tenant_id)
    source_level_id = uuid4()
    source_class = _classroom(tenant_id=tenant_id, level_id=source_level_id)
    enrollment = _enrollment(
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=source_class.id,
    )
    run = _run(tenant_id=tenant_id, academic_session_id=enrollment.academic_session_id)
    actor = _actor(tenant_id)

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
async def test_direct_progression_without_matching_arm_awaits_admin_placement(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    student = _student(tenant_id)
    source_level_id = uuid4()
    target_level_id = uuid4()
    source_class = _classroom(
        tenant_id=tenant_id,
        level_id=source_level_id,
        arm="C",
    )
    enrollment = _enrollment(
        tenant_id=tenant_id,
        student_id=student.id,
        class_id=source_class.id,
    )
    run = _run(tenant_id=tenant_id, academic_session_id=enrollment.academic_session_id)
    actor = _actor(tenant_id)

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
                progression_mode=AcademicLevelProgressionMode.DIRECT,
                next_level_id=target_level_id,
            )
        ),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentEnrollmentRepository.save",
        AsyncMock(side_effect=lambda _db, value: value),
    )
    save_student = AsyncMock(side_effect=lambda _db, value: value)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentRepository.save",
        save_student,
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.add_item",
        AsyncMock(side_effect=lambda _db, value: value),
    )
    create_next = AsyncMock()
    monkeypatch.setattr(AcademicProgressionService, "_create_next_enrollment", create_next)

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

    assert item.action == StudentProgressionItemAction.DIRECT
    assert item.status == StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT
    assert item.selected_level_id == target_level_id
    assert enrollment.is_current is False
    assert enrollment.ended_on == date(2026, 7, 31)
    assert student.class_id is None
    create_next.assert_not_awaited()


@pytest.mark.asyncio
async def test_level_selection_preserves_source_arm_when_target_arm_exists(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    source_level_id = uuid4()
    target_level_id = uuid4()
    student = _student(tenant_id)
    source_class = _classroom(
        tenant_id=tenant_id,
        level_id=source_level_id,
        arm="B",
    )
    target_class = _classroom(
        tenant_id=tenant_id,
        level_id=target_level_id,
        arm="B",
    )
    item = SimpleNamespace(
        action=StudentProgressionItemAction.STUDENT_SELECTION,
        status=StudentProgressionItemStatus.AWAITING_SELECTION,
        progression_run_id=uuid4(),
        from_class_id=source_class.id,
        selected_level_id=None,
        selected_classroom_id=None,
    )
    option = SimpleNamespace(
        target_level_id=target_level_id,
        target_classroom_id=None,
    )
    run = SimpleNamespace(next_academic_session_id=uuid4())
    next_session = SimpleNamespace(id=run.next_academic_session_id)

    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_latest_item_for_student",
        AsyncMock(return_value=item),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=source_class),
    )
    get_level = AsyncMock(
        side_effect=[
            SimpleNamespace(
                id=source_level_id,
                progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
            ),
            SimpleNamespace(
                id=target_level_id,
                name="SS1 Science",
                is_active=True,
                archived_at=None,
            ),
        ]
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicLevelRepository.get_by_id",
        get_level,
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicLevelRepository.list_progression_options",
        AsyncMock(return_value=[option]),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_run_by_id",
        AsyncMock(return_value=run),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=next_session),
    )
    same_arm_lookup = AsyncMock(return_value=target_class)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.ClassRoomRepository.get_by_level_and_arm",
        same_arm_lookup,
    )
    create_next = AsyncMock(return_value=item)
    monkeypatch.setattr(AcademicProgressionService, "_create_next_enrollment", create_next)
    response = SimpleNamespace(item=item)
    monkeypatch.setattr(
        AcademicProgressionService,
        "_selection_response",
        AsyncMock(return_value=response),
    )
    db = AsyncMock()

    result = await AcademicProgressionService._select_destination(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        destination_id=target_level_id,
        changed_by_admin_id=None,
    )

    assert result is response
    assert item.selected_level_id == target_level_id
    same_arm_lookup.assert_awaited_once_with(db, tenant_id, target_level_id, "B")
    assert create_next.await_args.kwargs["target_class"] is target_class


@pytest.mark.asyncio
async def test_level_selection_without_matching_arm_awaits_admin_placement(
    monkeypatch,
) -> None:
    tenant_id = uuid4()
    source_level_id = uuid4()
    target_level_id = uuid4()
    student = _student(tenant_id)
    source_class = _classroom(
        tenant_id=tenant_id,
        level_id=source_level_id,
        arm="C",
    )
    item = SimpleNamespace(
        action=StudentProgressionItemAction.STUDENT_SELECTION,
        status=StudentProgressionItemStatus.AWAITING_SELECTION,
        progression_run_id=uuid4(),
        from_class_id=source_class.id,
        selected_level_id=None,
        selected_classroom_id=None,
        reason=None,
    )
    option = SimpleNamespace(
        target_level_id=target_level_id,
        target_classroom_id=None,
    )
    run = SimpleNamespace(next_academic_session_id=uuid4())

    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_latest_item_for_student",
        AsyncMock(return_value=item),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentRepository.get_by_id",
        AsyncMock(return_value=student),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=source_class),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicLevelRepository.get_by_id",
        AsyncMock(
            side_effect=[
                SimpleNamespace(
                    id=source_level_id,
                    progression_mode=AcademicLevelProgressionMode.STUDENT_SELECTION,
                ),
                SimpleNamespace(
                    id=target_level_id,
                    name="SS1 Science",
                    is_active=True,
                    archived_at=None,
                ),
            ]
        ),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicLevelRepository.list_progression_options",
        AsyncMock(return_value=[option]),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.get_run_by_id",
        AsyncMock(return_value=run),
    )
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=SimpleNamespace(id=run.next_academic_session_id)),
    )
    same_arm_lookup = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.ClassRoomRepository.get_by_level_and_arm",
        same_arm_lookup,
    )
    save_item = AsyncMock(side_effect=lambda _db, value: value)
    monkeypatch.setattr(
        "app.modules.student_academics.progression_service.StudentProgressionRepository.save_item",
        save_item,
    )
    create_next = AsyncMock()
    monkeypatch.setattr(AcademicProgressionService, "_create_next_enrollment", create_next)
    response = SimpleNamespace(item=item)
    monkeypatch.setattr(
        AcademicProgressionService,
        "_selection_response",
        AsyncMock(return_value=response),
    )
    db = AsyncMock()

    result = await AcademicProgressionService._select_destination(
        db,
        tenant_id=tenant_id,
        student_id=student.id,
        destination_id=target_level_id,
        changed_by_admin_id=None,
    )

    assert result is response
    assert item.selected_level_id == target_level_id
    assert item.status == StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT
    assert "no active C arm" in item.reason
    same_arm_lookup.assert_awaited_once_with(db, tenant_id, target_level_id, "C")
    save_item.assert_awaited()
    create_next.assert_not_awaited()


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
