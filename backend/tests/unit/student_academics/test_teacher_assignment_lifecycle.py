from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.router import open_academic_term
from app.modules.student_academics.repository import StudentAcademicRepository
from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.schemas import (
    AcademicTermOpenRequest,
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
    TeacherAssignmentScheduleCancel,
    TeacherAssignmentScheduleUpdate,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.offboarding_service import (
    TeacherOffboardingRequest,
    TeacherOffboardingService,
)


@pytest.fixture(autouse=True)
def _allow_academic_writes_for_assignment_unit_tests():
    with patch(
        "app.modules.student_academics.service.ensure_academic_write_window",
        new=AsyncMock(),
    ):
        yield


def _assignment() -> TeacherAssignment:
    now = datetime.now(timezone.utc)
    return TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        effective_from=date(2026, 1, 10),
        effective_to=None,
        created_at=now,
        updated_at=now,
    )


def _assignment_result(assignments: list[TeacherAssignment]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = assignments
    return result


@pytest.mark.asyncio
async def test_end_assignment_preserves_history() -> None:
    assignment = _assignment()
    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._teacher_assignment_term_context",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=assignment.id)),
        ),
    ):
        await StudentAcademicService.end_teacher_assignment(
            db,
            assignment.tenant_id,
            assignment.id,
            TeacherAssignmentEnd(
                academic_term_id=uuid.uuid4(),
                effective_to=assignment.effective_from,
                reason="end assignment",
            ),
        )
    assert assignment.is_active is False
    assert assignment.effective_to == assignment.effective_from
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_historical_assignment_context_can_load_inactive_curriculum_subject() -> None:
    tenant_id = uuid.uuid4()
    curriculum_subject = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        curriculum_id=uuid.uuid4(),
        is_active=False,
    )
    curriculum = SimpleNamespace(
        id=curriculum_subject.curriculum_id,
        tenant_id=tenant_id,
    )
    result = MagicMock()
    result.first.return_value = (curriculum_subject, curriculum)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    (
        loaded_subject,
        loaded_curriculum,
    ) = await StudentAcademicService._load_curriculum_subject_context(
        db,
        tenant_id=tenant_id,
        curriculum_subject_id=curriculum_subject.id,
        require_active=False,
    )

    assert loaded_subject is curriculum_subject
    assert loaded_curriculum is curriculum
    statement = db.execute.await_args.args[0]
    assert "curriculum_subjects.is_active" not in str(statement.whereclause)


@pytest.mark.asyncio
async def test_operational_assignment_context_requires_active_curriculum_subject() -> None:
    tenant_id = uuid.uuid4()
    result = MagicMock()
    result.first.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(Exception):
        await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=uuid.uuid4(),
        )

    statement = db.execute.await_args.args[0]
    assert "curriculum_subjects.is_active" in str(statement.whereclause)


@pytest.mark.asyncio
async def test_open_academic_term_uses_canonical_academic_service() -> None:
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    term_id = uuid.uuid4()
    db = AsyncMock()
    admin = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    expected = SimpleNamespace(id=term_id)

    with patch(
        "app.modules.student_academics.router.StudentAcademicService.open_academic_term",
        new=AsyncMock(return_value=expected),
    ) as open_term:
        response = await open_academic_term(
            term_id,
            AcademicTermOpenRequest(confirmation="OPEN_ACADEMIC_TERM"),
            db,
            admin,
        )

    assert response is expected
    open_term.assert_awaited_once_with(db, tenant_id, term_id, admin_id)


@pytest.mark.asyncio
async def test_teacher_offboarding_ends_current_assignment_by_date() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    membership = SimpleNamespace(id=membership_id)
    assignment = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=membership_id,
        effective_from=today - timedelta(days=30),
        effective_to=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _assignment_result([assignment]),
                MagicMock(),
            ]
        )
    )
    expected = SimpleNamespace(id=membership_id)

    with (
        patch(
            "app.modules.teachers.offboarding_service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(return_value=membership),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(return_value=assignment),
        ) as save_assignment,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete_assignment,
        patch(
            "app.modules.teachers.offboarding_service.TeacherOffboardingService._create_replacement_assignment",
            new=AsyncMock(),
        ) as create_replacement,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ) as record_audit,
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipService.end_membership",
            new=AsyncMock(return_value=expected),
        ) as end_membership,
    ):
        response = await TeacherOffboardingService.end_membership_and_release_responsibilities(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherOffboardingRequest(reason="Teacher left the school"),
        )

    assert response is expected
    assert assignment.effective_to == today
    save_assignment.assert_awaited_once_with(db, assignment)
    delete_assignment.assert_not_awaited()
    create_replacement.assert_not_awaited()
    record_audit.assert_awaited_once()
    end_membership.assert_awaited_once()


@pytest.mark.asyncio
async def test_teacher_offboarding_transfers_scheduled_assignment_temporally() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    membership_id = uuid.uuid4()
    replacement_id = uuid.uuid4()
    actor = SimpleNamespace(tenant_id=tenant_id, id=admin_id)
    membership = SimpleNamespace(id=membership_id)
    replacement_membership = SimpleNamespace(
        id=replacement_id,
        status=TeacherMembershipStatus.ACTIVE,
    )
    scheduled = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=uuid.uuid4(),
        curriculum_subject_id=uuid.uuid4(),
        teacher_membership_id=membership_id,
        effective_from=today + timedelta(days=10),
        effective_to=today + timedelta(days=40),
    )
    replacement_assignment = TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        class_id=scheduled.class_id,
        curriculum_subject_id=scheduled.curriculum_subject_id,
        teacher_membership_id=replacement_id,
        effective_from=scheduled.effective_from,
        effective_to=scheduled.effective_to,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _assignment_result([scheduled]),
                MagicMock(),
            ]
        )
    )
    expected = SimpleNamespace(id=membership_id)

    with (
        patch(
            "app.modules.teachers.offboarding_service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipRepository.get_by_id",
            new=AsyncMock(side_effect=[membership, replacement_membership]),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete_assignment,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(),
        ) as save_assignment,
        patch(
            "app.modules.teachers.offboarding_service.TeacherOffboardingService._create_replacement_assignment",
            new=AsyncMock(return_value=replacement_assignment),
        ) as create_replacement,
        patch(
            "app.modules.teachers.offboarding_service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ) as record_audit,
        patch(
            "app.modules.teachers.offboarding_service.TeacherMembershipService.end_membership",
            new=AsyncMock(return_value=expected),
        ),
    ):
        response = await TeacherOffboardingService.end_membership_and_release_responsibilities(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherOffboardingRequest(
                reason="Teacher left the school",
                replacement_teacher_membership_id=replacement_id,
            ),
        )

    assert response is expected
    delete_assignment.assert_awaited_once_with(db, scheduled)
    save_assignment.assert_not_awaited()
    create_replacement.assert_awaited_once_with(
        db,
        tenant_id=tenant_id,
        source=scheduled,
        replacement_teacher_membership_id=replacement_id,
        effective_from=scheduled.effective_from,
        effective_to=scheduled.effective_to,
    )
    record_audit.assert_awaited_once()


def _dated_assignment(
    *,
    tenant_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    curriculum_subject_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    effective_from: date,
    effective_to: date | None = None,
) -> TeacherAssignment:
    now = datetime.now(timezone.utc)
    return TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        class_id=class_id or uuid.uuid4(),
        curriculum_subject_id=curriculum_subject_id or uuid.uuid4(),
        teacher_membership_id=teacher_id or uuid.uuid4(),
        effective_from=effective_from,
        effective_to=effective_to,
        created_at=now,
        updated_at=now,
    )


def _assignment_context_patches(assignment: TeacherAssignment, *, dependencies=None):
    today = date.today()
    return (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._load_curriculum_subject_context",
            new=AsyncMock(
                return_value=(
                    SimpleNamespace(id=assignment.curriculum_subject_id),
                    SimpleNamespace(),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_curriculum_subject_available_to_class",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    start_date=today - timedelta(days=365),
                    end_date=today + timedelta(days=365),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(
                return_value=dependencies or {"student_results": 0, "report_card_references": 0}
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(
                side_effect=lambda _db, row: SimpleNamespace(id=row.id, status=row.state)
            ),
        ),
    )


@pytest.mark.asyncio
async def test_same_start_reassignment_corrects_existing_row_without_history_split() -> None:
    today = date.today()
    current = _dated_assignment(effective_from=today - timedelta(days=20))
    replacement_id = uuid.uuid4()
    db = AsyncMock()
    patches = _assignment_context_patches(current)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5] as save,
        patches[6] as audit,
        patches[7],
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_teacher_assignment",
            new=AsyncMock(),
        ) as create,
    ):
        response = await StudentAcademicService.reassign_teacher_assignment(
            db,
            current.tenant_id,
            current.id,
            TeacherAssignmentReassign(
                teacher_membership_id=replacement_id,
                academic_term_id=uuid.uuid4(),
                effective_from=current.effective_from,
                reason="Correct the original teacher",
            ),
        )

    assert response.id == current.id
    assert current.teacher_membership_id == replacement_id
    assert current.effective_to is None
    save.assert_awaited_once_with(db, current)
    create.assert_not_awaited()
    assert audit.await_args.kwargs["action"] == "assignment_corrected"


@pytest.mark.asyncio
async def test_same_start_correction_is_blocked_by_academic_dependencies() -> None:
    current = _dated_assignment(effective_from=date.today() - timedelta(days=20))
    db = AsyncMock()
    patches = _assignment_context_patches(
        current,
        dependencies={"student_results": 1, "report_card_references": 0},
    )
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.reassign_teacher_assignment(
                db,
                current.tenant_id,
                current.id,
                TeacherAssignmentReassign(
                    teacher_membership_id=uuid.uuid4(),
                    academic_term_id=uuid.uuid4(),
                    effective_from=current.effective_from,
                    reason="Correct the original teacher",
                ),
            )

    assert exc_info.value.payload["code"] == "ASSIGNMENT_CORRECTION_BLOCKED"
    assert exc_info.value.payload["dependency_counts"] == {"student_results": 1}
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_later_reassignment_still_splits_history() -> None:
    today = date.today()
    current = _dated_assignment(effective_from=today - timedelta(days=20))
    replacement_id = uuid.uuid4()
    takeover_date = today + timedelta(days=5)
    db = AsyncMock()
    patches = _assignment_context_patches(current)

    async def create_replacement(_db, row):
        row.id = uuid.uuid4()
        row.created_at = datetime.now(timezone.utc)
        row.updated_at = row.created_at
        return row

    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6] as audit,
        patches[7],
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_teacher_assignment",
            new=AsyncMock(side_effect=create_replacement),
        ),
    ):
        response = await StudentAcademicService.reassign_teacher_assignment(
            db,
            current.tenant_id,
            current.id,
            TeacherAssignmentReassign(
                teacher_membership_id=replacement_id,
                academic_term_id=uuid.uuid4(),
                effective_from=takeover_date,
                reason="Plan teacher handover",
            ),
        )

    assert current.effective_to == takeover_date - timedelta(days=1)
    assert response.status.value == "scheduled"
    assert audit.await_args.kwargs["action"] == "teacher_reassigned"


@pytest.mark.asyncio
@pytest.mark.parametrize("days_until_start", [0, 12])
async def test_scheduled_takeover_edit_updates_teacher_and_predecessor_boundary(
    days_until_start: int,
) -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    old_start = today + timedelta(days=20)
    predecessor = _dated_assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=old_start - timedelta(days=1),
    )
    scheduled = _dated_assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=subject_id,
        effective_from=old_start,
    )
    replacement_id = uuid.uuid4()
    new_start = today + timedelta(days=days_until_start)
    db = AsyncMock()
    patches = _assignment_context_patches(scheduled)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6],
        patches[7],
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[predecessor, scheduled]),
        ),
    ):
        response = await StudentAcademicService.update_scheduled_teacher_assignment(
            db,
            tenant_id,
            scheduled.id,
            TeacherAssignmentScheduleUpdate(
                teacher_membership_id=replacement_id,
                academic_term_id=uuid.uuid4(),
                effective_from=new_start,
                reason="Adjust the planned handover",
            ),
        )

    assert scheduled.teacher_membership_id == replacement_id
    assert scheduled.effective_from == new_start
    assert predecessor.effective_to == new_start - timedelta(days=1)
    assert response.status.value == ("current" if days_until_start == 0 else "scheduled")


@pytest.mark.asyncio
async def test_moving_takeover_to_predecessor_start_becomes_safe_correction() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    predecessor = _dated_assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=9),
    )
    scheduled = _dated_assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=subject_id,
        effective_from=today + timedelta(days=10),
    )
    replacement_id = uuid.uuid4()
    db = AsyncMock()
    patches = _assignment_context_patches(scheduled)
    with (
        patches[0],
        patches[1],
        patches[2],
        patches[3],
        patches[4],
        patches[5],
        patches[6] as audit,
        patches[7],
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[predecessor, scheduled]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete,
    ):
        response = await StudentAcademicService.update_scheduled_teacher_assignment(
            db,
            tenant_id,
            scheduled.id,
            TeacherAssignmentScheduleUpdate(
                teacher_membership_id=replacement_id,
                academic_term_id=uuid.uuid4(),
                effective_from=predecessor.effective_from,
                reason="Correct the original teacher plan",
            ),
        )

    assert response.id == predecessor.id
    assert predecessor.teacher_membership_id == replacement_id
    assert predecessor.effective_to is None
    delete.assert_awaited_once_with(db, scheduled)
    assert [call.kwargs["action"] for call in audit.await_args_list] == [
        "assignment_corrected",
        "scheduled_takeover_absorbed_by_correction",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("with_predecessor", [False, True])
async def test_cancel_schedule_deletes_never_effective_row_and_restores_takeover_predecessor(
    with_predecessor: bool,
) -> None:
    today = date.today()
    scheduled = _dated_assignment(effective_from=today + timedelta(days=10))
    predecessor = _dated_assignment(
        tenant_id=scheduled.tenant_id,
        class_id=scheduled.class_id,
        curriculum_subject_id=scheduled.curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=scheduled.effective_from - timedelta(days=1),
    )
    original_predecessor_end = predecessor.effective_to
    history = [scheduled, predecessor] if with_predecessor else [scheduled]
    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=scheduled),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService.teacher_assignment_dependency_preview",
            new=AsyncMock(return_value=SimpleNamespace(can_cancel_schedule=True)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=scheduled.id)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=history),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete,
    ):
        await StudentAcademicService.cancel_scheduled_teacher_assignment(
            db,
            scheduled.tenant_id,
            scheduled.id,
            TeacherAssignmentScheduleCancel(reason="Cancel the plan"),
        )

    delete.assert_awaited_once_with(db, scheduled)
    assert predecessor.effective_to == (None if with_predecessor else original_predecessor_end)


@pytest.mark.asyncio
async def test_early_end_cancels_successor_without_reopening_predecessor() -> None:
    today = date.today()
    current = _dated_assignment(
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=9),
    )
    successor = _dated_assignment(
        tenant_id=current.tenant_id,
        class_id=current.class_id,
        curriculum_subject_id=current.curriculum_subject_id,
        effective_from=today + timedelta(days=10),
    )
    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._teacher_assignment_term_context",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[current, successor]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ) as delete,
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=current.id)),
        ),
    ):
        await StudentAcademicService.end_teacher_assignment(
            db,
            current.tenant_id,
            current.id,
            TeacherAssignmentEnd(
                academic_term_id=uuid.uuid4(),
                effective_to=today,
                reason="End before planned takeover",
            ),
        )

    assert current.effective_to == today
    delete.assert_awaited_once_with(db, successor)


def test_natural_handover_state_changes_without_rewriting_rows() -> None:
    today = date.today()
    predecessor = _dated_assignment(
        effective_from=today - timedelta(days=10),
        effective_to=today - timedelta(days=1),
    )
    successor = _dated_assignment(
        tenant_id=predecessor.tenant_id,
        class_id=predecessor.class_id,
        curriculum_subject_id=predecessor.curriculum_subject_id,
        effective_from=today,
    )

    assert predecessor.state.value == "ended"
    assert successor.state.value == "current"


@pytest.mark.asyncio
async def test_paginated_list_enriches_current_row_from_batched_takeover_lookup() -> None:
    current = _dated_assignment(
        effective_from=date.today() - timedelta(days=10),
        effective_to=date.today() + timedelta(days=9),
    )
    takeover_id = uuid.uuid4()
    record = {"assignment": current}
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignment_rows",
            new=AsyncMock(return_value=([record], 51)),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_scheduled_takeovers_for_assignments",
            new=AsyncMock(
                return_value={
                    current.id: {
                        "id": takeover_id,
                        "teacher_membership_id": uuid.uuid4(),
                        "teacher_name": "Incoming Teacher",
                        "effective_from": current.effective_to + timedelta(days=1),
                    }
                }
            ),
        ) as batch_lookup,
    ):
        rows, total = await StudentAcademicService.list_teacher_assignment_responses(
            AsyncMock(), current.tenant_id, skip=25, limit=25
        )

    assert total == 51
    assert rows[0].has_scheduled_takeover is True
    assert rows[0].scheduled_takeover_id == takeover_id
    batch_lookup.assert_awaited_once()


@pytest.mark.asyncio
async def test_assignment_lookup_keeps_tenant_isolation_for_schedule_edit() -> None:
    tenant_id = uuid.uuid4()
    assignment_id = uuid.uuid4()
    lookup = AsyncMock(return_value=None)
    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
        new=lookup,
    ):
        with pytest.raises(NotFoundException):
            await StudentAcademicService.update_scheduled_teacher_assignment(
                AsyncMock(),
                tenant_id,
                assignment_id,
                TeacherAssignmentScheduleUpdate(
                    teacher_membership_id=uuid.uuid4(),
                    academic_term_id=uuid.uuid4(),
                    effective_from=date.today(),
                    reason="Attempt cross tenant edit",
                ),
            )

    assert lookup.await_args.args[1:] == (tenant_id, assignment_id)
    assert lookup.await_args.kwargs == {"lock": True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected_fragments"),
    [
        ("scheduled", ("effective_from > CURRENT_DATE",)),
        ("current", ("effective_from <= CURRENT_DATE", "effective_to >= CURRENT_DATE")),
        ("ended", ("effective_to IS NOT NULL", "effective_to < CURRENT_DATE")),
    ],
)
async def test_assignment_lifecycle_filters_remain_date_authoritative(
    status: str,
    expected_fragments: tuple[str, ...],
) -> None:
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    rows_result = MagicMock()
    rows_result.all.return_value = []
    db = SimpleNamespace(execute=AsyncMock(side_effect=[count_result, rows_result]))

    await StudentAcademicRepository.list_teacher_assignment_rows(
        db,
        uuid.uuid4(),
        status=status,
    )

    statement = str(db.execute.await_args_list[1].args[0])
    assert "teacher_assignments.tenant_id" in statement
    for fragment in expected_fragments:
        assert fragment in statement
