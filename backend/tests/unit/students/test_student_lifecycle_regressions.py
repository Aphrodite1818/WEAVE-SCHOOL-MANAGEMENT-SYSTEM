from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import BadRequestException, ConflictException
from app.modules.student_academics.models import AcademicSessionStatus
from app.modules.students.lifecycle_service import StudentLifecycleService
from app.modules.students.models import (
    AcademicStatus,
    StudentEnrollment,
    StudentAccountStatus,
    StudentEnrollmentOutcome,
)
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import (
    StudentExpelRequest,
    StudentGraduateRequest,
    StudentHardDeleteEligibilityResponse,
    StudentReturnEnrollmentRequest,
    StudentWithdrawRequest,
)
from app.modules.students.service import StudentService


@pytest.fixture
def actor():
    return SimpleNamespace(id=uuid4(), tenant_id=uuid4())


@pytest.fixture
def db():
    return SimpleNamespace(
        commit=AsyncMock(),
        refresh=AsyncMock(),
        execute=AsyncMock(),
    )


@pytest.fixture(autouse=True)
def no_existing_upcoming_enrollment(monkeypatch):
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_upcoming",
        AsyncMock(return_value=None),
    )


@pytest.mark.parametrize(
    ("request_type", "date_field"),
    [
        (StudentWithdrawRequest, "effective_date"),
        (StudentExpelRequest, "effective_date"),
        (StudentGraduateRequest, "graduation_date"),
    ],
)
def test_terminal_request_contracts_reject_client_supplied_dates(request_type, date_field):
    with pytest.raises(ValidationError):
        request_type(reason="Immediate lifecycle action", **{date_field: date.today()})


@pytest.mark.parametrize(
    ("method_name", "target_status"),
    [
        ("withdraw", AcademicStatus.WITHDRAWN),
        ("expel", AcademicStatus.EXPELLED),
        ("graduate", AcademicStatus.GRADUATED),
    ],
)
@pytest.mark.asyncio
async def test_terminal_services_always_use_server_today(
    monkeypatch,
    actor,
    db,
    method_name,
    target_status,
):
    ensure_safe = AsyncMock()
    transition = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentLifecycleService, "_ensure_terminal_exit_safe", ensure_safe)
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.LegacyStudentLifecycleService._transition",
        transition,
    )

    await getattr(StudentLifecycleService, method_name)(
        db,
        actor=actor,
        student_id=uuid4(),
        reason="Immediate lifecycle action",
    )

    assert ensure_safe.await_args.kwargs["effective_date"] == date.today()
    assert transition.await_args.kwargs["effective_date"] == date.today()
    assert transition.await_args.kwargs["target_status"] == target_status


def test_future_enrollment_is_not_current_before_its_start_date():
    enrollment = StudentEnrollment(
        tenant_id=uuid4(),
        student_id=uuid4(),
        academic_level_id=uuid4(),
        academic_session_id=uuid4(),
        started_on=date.today() + timedelta(days=1),
        entry_outcome=StudentEnrollmentOutcome.ENROLLED,
    )

    assert enrollment.is_current is False


def test_return_contract_accepts_future_enrollment_date():
    payload = StudentReturnEnrollmentRequest(
        target_academic_level_id=uuid4(),
        target_class_id=uuid4(),
        academic_session_id=uuid4(),
        effective_date=date.today() + timedelta(days=7),
        reason="Approved future return",
    )

    assert payload.effective_date == date.today() + timedelta(days=7)


@pytest.mark.asyncio
async def test_future_formal_return_keeps_terminal_access_until_start(
    monkeypatch,
    actor,
    db,
):
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        admission_number="STD-FUTURE",
        status=AcademicStatus.GRADUATED,
        is_archived=False,
    )
    previous = SimpleNamespace(id=uuid4(), ended_on=date.today())
    session = SimpleNamespace(
        id=uuid4(),
        status=AcademicSessionStatus.OPEN,
        is_current=True,
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() + timedelta(days=60),
    )
    classroom = SimpleNamespace(
        id=uuid4(),
        academic_level_id=uuid4(),
        is_active=True,
        archived_at=None,
    )
    future_date = date.today() + timedelta(days=7)
    save_student = AsyncMock()
    add_enrollment = AsyncMock()
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(StudentRepository, "save", save_student)
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(return_value=(False, "Historical action", SimpleNamespace(metadata_json={}))),
    )
    monkeypatch.setattr(StudentEnrollmentRepository, "get_current", AsyncMock(return_value=None))
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "list_for_student",
        AsyncMock(return_value=[previous]),
    )
    monkeypatch.setattr(StudentEnrollmentRepository, "add", add_enrollment)
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.ensure_for_actor",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.invalidate_after_commit",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentLifecycleService, "_record_lifecycle_audit", AsyncMock())
    monkeypatch.setattr(
        StudentService,
        "_build_detail_response",
        AsyncMock(return_value=SimpleNamespace(id=student.id)),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.StudentLifecycleTransitionResponse",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    response = await StudentLifecycleService.reenrol_graduate(
        db,
        actor=actor,
        student_id=student.id,
        payload=StudentReturnEnrollmentRequest(
            target_academic_level_id=classroom.academic_level_id,
            target_class_id=classroom.id,
            academic_session_id=session.id,
            effective_date=future_date,
            reason="Approved future re-enrollment",
        ),
    )

    created = add_enrollment.await_args.args[1]
    assert created.student_id == student.id
    assert created.started_on == future_date
    assert student.status == AcademicStatus.GRADUATED
    assert response.new_status == AcademicStatus.GRADUATED
    save_student.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_formal_return_materializes_active_state(monkeypatch, actor, db):
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        admission_number="STD-DUE",
        status=AcademicStatus.WITHDRAWN,
        promotion_hold=True,
        is_active=False,
        account_status=StudentAccountStatus.INACTIVE,
        graduation_date=None,
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=SimpleNamespace(id=uuid4())),
    )
    db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    save_student = AsyncMock()
    monkeypatch.setattr(StudentRepository, "save", save_student)
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.ensure_for_actor",
        AsyncMock(),
    )
    restore_links = AsyncMock(return_value=(0, 0))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_restore_parent_links_after_return",
        restore_links,
    )

    changed = await StudentLifecycleService.activate_due_return(
        db,
        student=student,
        commit=False,
    )

    assert changed is True
    assert student.status == AcademicStatus.ACTIVE
    assert student.is_active is True
    assert student.account_status == StudentAccountStatus.ACTIVE
    save_student.assert_awaited_once()
    restore_links.assert_awaited_once()


@pytest.mark.asyncio
async def test_capabilities_offer_undo_for_recent_terminal_action(monkeypatch, actor, db):
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        status=AcademicStatus.WITHDRAWN,
        is_archived=False,
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(return_value=(True, None, SimpleNamespace(id=uuid4()))),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=None),
    )

    capabilities = await StudentLifecycleService.capabilities(
        db,
        tenant_id=actor.tenant_id,
        student_id=student.id,
    )

    assert capabilities.can_undo_withdrawal is True
    assert capabilities.can_readmit is False
    assert capabilities.can_undo_expulsion is False
    assert capabilities.can_reinstate_expelled is False
    assert capabilities.can_undo_graduation is False
    assert capabilities.can_reenrol_graduate is False


@pytest.mark.asyncio
async def test_capabilities_offer_formal_return_after_undo_window(monkeypatch, actor, db):
    student = SimpleNamespace(
        id=uuid4(),
        tenant_id=actor.tenant_id,
        status=AcademicStatus.EXPELLED,
        is_archived=False,
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(
            return_value=(
                False,
                "The 24-hour correction window has passed.",
                SimpleNamespace(id=uuid4()),
            )
        ),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=None),
    )

    capabilities = await StudentLifecycleService.capabilities(
        db,
        tenant_id=actor.tenant_id,
        student_id=student.id,
    )

    assert capabilities.can_undo_expulsion is False
    assert capabilities.can_reinstate_expelled is True
    assert capabilities.undo_block_reason == "The 24-hour correction window has passed."


@pytest.mark.asyncio
async def test_undo_eligibility_expires_after_twenty_four_hours(monkeypatch, actor, db):
    student_id = uuid4()
    audit = SimpleNamespace(
        id=uuid4(),
        action="student_withdrawn",
        created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        metadata_json={},
    )
    monkeypatch.setattr(
        StudentLifecycleService,
        "_latest_lifecycle_audit",
        AsyncMock(return_value=audit),
    )

    undoable, reason, returned_audit = await StudentLifecycleService._undo_eligibility(
        db,
        tenant_id=actor.tenant_id,
        student_id=student_id,
        status=AcademicStatus.WITHDRAWN,
    )

    assert undoable is False
    assert reason == "The 24-hour correction window has passed."
    assert returned_audit is audit


@pytest.mark.asyncio
async def test_undo_eligibility_rejects_later_protected_activity(monkeypatch, actor, db):
    student_id = uuid4()
    enrollment_id = uuid4()
    admin_id = actor.id
    ended_on = date.today()
    audit = SimpleNamespace(
        id=uuid4(),
        action="student_withdrawn",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        metadata_json={
            "enrollment": {
                "id": str(enrollment_id),
                "after": {
                    "ended_on": ended_on.isoformat(),
                    "exit_outcome": StudentEnrollmentOutcome.WITHDRAWN.value,
                    "exit_reason": "Family relocation",
                    "ended_by_admin_id": str(admin_id),
                },
            }
        },
    )
    enrollment = SimpleNamespace(
        id=enrollment_id,
        ended_on=ended_on,
        exit_outcome=StudentEnrollmentOutcome.WITHDRAWN,
        exit_reason="Family relocation",
        ended_by_admin_id=admin_id,
    )
    monkeypatch.setattr(
        StudentLifecycleService,
        "_latest_lifecycle_audit",
        AsyncMock(return_value=audit),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "list_for_student",
        AsyncMock(return_value=[enrollment]),
    )
    activity = AsyncMock(
        return_value={
            "attendance": 0,
            "results": 1,
            "report_cards": 0,
            "teacher_comments": 0,
            "cbt_results": 0,
            "progression": 0,
        }
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.StudentEnrollmentEvidenceService.student_activity_counts_after",
        activity,
    )

    undoable, reason, _ = await StudentLifecycleService._undo_eligibility(
        db,
        tenant_id=actor.tenant_id,
        student_id=student_id,
        status=AcademicStatus.WITHDRAWN,
    )

    assert undoable is False
    assert reason == "Later protected academic activity makes Undo unsafe."


@pytest.mark.asyncio
async def test_formal_reinstatement_preserves_student_identity_and_creates_new_enrollment(
    monkeypatch, actor, db
):
    student_id = uuid4()
    level_id = uuid4()
    class_id = uuid4()
    session_id = uuid4()
    prior_enrollment = SimpleNamespace(
        id=uuid4(),
        ended_on=date.today() - timedelta(days=5),
    )
    student = SimpleNamespace(
        id=student_id,
        tenant_id=actor.tenant_id,
        admission_number="STD-001",
        status=AcademicStatus.EXPELLED,
        is_archived=False,
        promotion_hold=True,
        is_active=False,
        account_status=StudentAccountStatus.INACTIVE,
        graduation_date=None,
    )
    session = SimpleNamespace(
        id=session_id,
        status=AcademicSessionStatus.OPEN,
        is_current=True,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=30),
    )
    classroom = SimpleNamespace(
        id=class_id,
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )

    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(StudentRepository, "save", AsyncMock(return_value=student))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(return_value=(False, "Historical action", SimpleNamespace(metadata_json={}))),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "list_for_student",
        AsyncMock(return_value=[prior_enrollment]),
    )
    add_enrollment = AsyncMock()
    monkeypatch.setattr(StudentEnrollmentRepository, "add", add_enrollment)
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.ensure_for_actor",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AuthIdentityService.invalidate_after_commit",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StudentLifecycleService,
        "_record_lifecycle_audit",
        AsyncMock(),
    )
    monkeypatch.setattr(
        StudentService,
        "_build_detail_response",
        AsyncMock(return_value=SimpleNamespace(id=student_id)),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.StudentLifecycleTransitionResponse",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    response = await StudentLifecycleService.reinstate_expelled(
        db,
        actor=actor,
        student_id=student_id,
        payload=StudentReturnEnrollmentRequest(
            target_academic_level_id=level_id,
            target_class_id=class_id,
            academic_session_id=session_id,
            effective_date=date.today(),
            reason="Formal reinstatement approved",
        ),
    )

    assert response.student.id == student_id
    assert student.id == student_id
    assert student.status == AcademicStatus.ACTIVE
    assert student.is_active is True
    assert student.account_status == StudentAccountStatus.ACTIVE
    add_enrollment.assert_awaited_once()
    created = add_enrollment.await_args.args[1]
    assert created.student_id == student_id
    assert created.academic_level_id == level_id
    assert created.class_id == class_id
    assert created.academic_session_id == session_id
    assert created.entry_outcome == StudentEnrollmentOutcome.REINSTATED
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_formal_return_must_begin_after_previous_enrollment(monkeypatch, actor, db):
    student_id = uuid4()
    level_id = uuid4()
    class_id = uuid4()
    session_id = uuid4()
    previous_end = date.today()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=actor.tenant_id,
        admission_number="STD-002",
        status=AcademicStatus.WITHDRAWN,
        is_archived=False,
    )
    session = SimpleNamespace(
        id=session_id,
        status=AcademicSessionStatus.OPEN,
        is_current=True,
        start_date=date.today() - timedelta(days=30),
        end_date=date.today() + timedelta(days=30),
    )
    classroom = SimpleNamespace(
        id=class_id,
        academic_level_id=level_id,
        is_active=True,
        archived_at=None,
    )

    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(return_value=(False, "Historical action", SimpleNamespace(metadata_json={}))),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "list_for_student",
        AsyncMock(return_value=[SimpleNamespace(id=uuid4(), ended_on=previous_end)]),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=session),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ClassRoomRepository.get_by_id",
        AsyncMock(return_value=classroom),
    )

    with pytest.raises(ConflictException, match="cannot begin on the same date.*use Undo"):
        await StudentLifecycleService.readmit(
            db,
            actor=actor,
            student_id=student_id,
            payload=StudentReturnEnrollmentRequest(
                target_academic_level_id=level_id,
                target_class_id=class_id,
                academic_session_id=session_id,
                effective_date=previous_end,
                reason="Return to school",
            ),
        )


@pytest.mark.asyncio
async def test_formal_return_effective_date_must_be_inside_current_session(monkeypatch, actor, db):
    student_id = uuid4()
    session_id = uuid4()
    student = SimpleNamespace(
        id=student_id,
        tenant_id=actor.tenant_id,
        admission_number="STD-003",
        status=AcademicStatus.WITHDRAWN,
        is_archived=False,
    )
    session = SimpleNamespace(
        id=session_id,
        status=AcademicSessionStatus.OPEN,
        is_current=True,
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() + timedelta(days=30),
    )

    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
    monkeypatch.setattr(
        StudentLifecycleService,
        "_undo_eligibility",
        AsyncMock(return_value=(False, "Historical action", SimpleNamespace(metadata_json={}))),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.AcademicSessionLifecycleRepository.get_by_id",
        AsyncMock(return_value=session),
    )

    with pytest.raises(BadRequestException, match="before the current session starts"):
        await StudentLifecycleService.readmit(
            db,
            actor=actor,
            student_id=student_id,
            payload=StudentReturnEnrollmentRequest(
                target_academic_level_id=uuid4(),
                target_class_id=uuid4(),
                academic_session_id=session_id,
                effective_date=date.today() - timedelta(days=10),
                reason="Historical return date",
            ),
        )


@pytest.mark.asyncio
async def test_backdated_terminal_exit_rejects_preserved_evidence(monkeypatch, actor, db):
    student_id = uuid4()
    enrollment = SimpleNamespace(
        id=uuid4(),
        started_on=date.today() - timedelta(days=60),
    )
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=enrollment),
    )
    evidence = AsyncMock(
        return_value={
            "attendance": 1,
            "results": 0,
            "teacher_comments": 0,
            "report_cards": 0,
            "cbt_results": 0,
            "progression": 0,
        }
    )
    monkeypatch.setattr(
        "app.modules.students.lifecycle_service.StudentEnrollmentEvidenceService.segment_dependency_counts",
        evidence,
    )

    with pytest.raises(ConflictException, match="preserved academic evidence"):
        await StudentLifecycleService._ensure_terminal_exit_safe(
            db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
            effective_date=date.today() - timedelta(days=10),
        )

    assert evidence.await_args.kwargs["on_or_after"] == date.today() - timedelta(days=9)


@pytest.mark.asyncio
async def test_same_day_class_correction_mutates_segment_without_fake_history(
    monkeypatch, actor, db
):
    from app.modules.students.enrollment_schemas import StudentClassReassignmentRequest
    from app.modules.students.placement_service import StudentPlacementService

    session_id = uuid4()
    level_id = uuid4()
    old_class_id = uuid4()
    new_class_id = uuid4()
    student = SimpleNamespace(id=uuid4(), status=AcademicStatus.ACTIVE)
    current = SimpleNamespace(
        id=uuid4(),
        student_id=student.id,
        academic_session_id=session_id,
        academic_level_id=level_id,
        class_id=old_class_id,
        started_on=date.today(),
    )
    target_class = SimpleNamespace(id=new_class_id, academic_level_id=level_id)

    monkeypatch.setattr(
        "app.modules.students.placement_service.ensure_academic_write_window",
        AsyncMock(),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))
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
    monkeypatch.setattr(
        StudentEnrollmentRepository,
        "get_current",
        AsyncMock(return_value=current),
    )
    correction = AsyncMock()
    monkeypatch.setattr(StudentPlacementService, "_correct_same_day_placement", correction)
    invalidate = AsyncMock()
    monkeypatch.setattr(StudentPlacementService, "_invalidate_derived_context", invalidate)
    create_segment = AsyncMock()
    close_segment = AsyncMock()
    monkeypatch.setattr(StudentPlacementService, "_create_segment", create_segment)
    monkeypatch.setattr(StudentPlacementService, "_close_segment", close_segment)
    monkeypatch.setattr(
        StudentService,
        "get_student_profile",
        AsyncMock(return_value=SimpleNamespace(id=student.id)),
    )

    await StudentPlacementService.reassign_class(
        db,
        actor=actor,
        student_id=student.id,
        payload=StudentClassReassignmentRequest(
            target_class_id=new_class_id,
            academic_session_id=session_id,
            effective_date=date.today(),
            reason="Correct same-day class selection",
        ),
    )

    correction.assert_awaited_once()
    create_segment.assert_not_awaited()
    close_segment.assert_not_awaited()
    invalidate.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_day_correction_is_blocked_after_academic_evidence(monkeypatch, actor, db):
    from app.modules.students.placement_service import StudentPlacementService

    enrollment = SimpleNamespace(
        id=uuid4(),
        student_id=uuid4(),
        academic_level_id=uuid4(),
        class_id=uuid4(),
        started_on=date.today(),
    )
    monkeypatch.setattr(
        "app.modules.students.placement_service.StudentEnrollmentEvidenceService.segment_dependency_counts",
        AsyncMock(
            return_value={
                "attendance": 0,
                "results": 1,
                "teacher_comments": 0,
                "report_cards": 0,
                "cbt_results": 0,
                "progression": 0,
            }
        ),
    )

    with pytest.raises(ConflictException, match="can no longer be corrected"):
        await StudentPlacementService._correct_same_day_placement(
            db,
            actor=actor,
            enrollment=enrollment,
            target_academic_level_id=enrollment.academic_level_id,
            target_class_id=uuid4(),
            reason="Correction",
        )


@pytest.mark.asyncio
async def test_hard_delete_eligibility_treats_login_history_as_protected(monkeypatch, actor, db):
    student_id = uuid4()
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
        "app.modules.students.lifecycle_service.LegacyStudentLifecycleService.hard_delete_eligibility",
        AsyncMock(return_value=base),
    )
    monkeypatch.setattr(StudentRepository, "get_by_id", AsyncMock(return_value=student))

    eligibility = await StudentLifecycleService.hard_delete_eligibility(
        db,
        tenant_id=actor.tenant_id,
        student_id=student_id,
    )

    assert eligibility.eligible is False
    assert eligibility.recommendation == "archive"
    assert "login_history" in eligibility.blocking_dependencies
