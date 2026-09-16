from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.schemas import (
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
    TeacherAssignmentScheduleCancel,
)
from app.modules.student_academics.service import StudentAcademicService


def _assignment(
    *,
    tenant_id: uuid.UUID | None = None,
    class_id: uuid.UUID | None = None,
    curriculum_subject_id: uuid.UUID | None = None,
    teacher_membership_id: uuid.UUID | None = None,
    effective_from: date,
    effective_to: date | None = None,
) -> TeacherAssignment:
    now = datetime.now(timezone.utc)
    return TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        class_id=class_id or uuid.uuid4(),
        curriculum_subject_id=curriculum_subject_id or uuid.uuid4(),
        teacher_membership_id=teacher_membership_id or uuid.uuid4(),
        effective_from=effective_from,
        effective_to=effective_to,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_current_assignment_with_planned_end_is_still_endable() -> None:
    today = date.today()
    assignment = _assignment(
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=10),
    )
    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(return_value={"student_results": 0, "report_card_references": 0}),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[assignment]),
        ),
    ):
        preview = await StudentAcademicService.teacher_assignment_dependency_preview(
            db, assignment.tenant_id, assignment.id
        )

    assert preview.can_end is True
    assert preview.can_reassign is True
    assert all("permanently deleted" not in message for message in preview.blocker_messages)


@pytest.mark.asyncio
async def test_cancel_takeover_deletes_before_reopening_predecessor() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    curriculum_subject_id = uuid.uuid4()
    scheduled = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today + timedelta(days=10),
    )
    predecessor = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=scheduled.effective_from - timedelta(days=1),
    )
    events: list[str] = []
    db = AsyncMock()
    db.flush.side_effect = lambda: events.append("flush_delete")
    db.commit.side_effect = lambda: events.append("commit")

    async def _delete(_db, row):
        assert row is scheduled
        events.append("delete")

    async def _save(_db, row):
        assert row is predecessor
        events.append("reopen_predecessor")
        return row

    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
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
            new=AsyncMock(return_value=[predecessor, scheduled]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._is_scheduled_takeover_relation",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(side_effect=lambda *args, **kwargs: events.append("audit")),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(side_effect=_delete),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=_save),
        ),
    ):
        await StudentAcademicService.cancel_scheduled_teacher_assignment(
            db,
            tenant_id,
            scheduled.id,
            TeacherAssignmentScheduleCancel(reason="Cancel the planned handover"),
        )

    assert predecessor.effective_to is None
    assert events.index("delete") < events.index("flush_delete")
    assert events.index("flush_delete") < events.index("reopen_predecessor")
    assert events[-1] == "commit"


@pytest.mark.asyncio
async def test_cancel_standalone_schedule_does_not_reopen_adjacent_predecessor() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    curriculum_subject_id = uuid.uuid4()
    scheduled = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today + timedelta(days=10),
    )
    predecessor = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=scheduled.effective_from - timedelta(days=1),
    )
    original_end = predecessor.effective_to
    db = AsyncMock()
    audit = AsyncMock()
    save = AsyncMock(return_value=predecessor)

    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
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
            new=AsyncMock(return_value=[predecessor, scheduled]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._is_scheduled_takeover_relation",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=audit,
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=save,
        ),
    ):
        await StudentAcademicService.cancel_scheduled_teacher_assignment(
            db,
            tenant_id,
            scheduled.id,
            TeacherAssignmentScheduleCancel(reason="Cancel standalone schedule"),
        )

    assert predecessor.effective_to == original_end
    save.assert_not_awaited()
    assert audit.await_args.kwargs["action"] == "scheduled_assignment_cancelled"


@pytest.mark.asyncio
async def test_early_end_does_not_cancel_unrelated_adjacent_schedule() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    curriculum_subject_id = uuid.uuid4()
    predecessor = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=10),
    )
    scheduled = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=predecessor.effective_to + timedelta(days=1),
    )
    delete = AsyncMock()
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._teacher_assignment_term_context",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=predecessor),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject",
            new=AsyncMock(return_value=[predecessor, scheduled]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._is_scheduled_takeover_relation",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.delete_teacher_assignment",
            new=delete,
        ),
    ):
        with pytest.raises(ConflictException, match="already has a scheduled end date"):
            await StudentAcademicService.end_teacher_assignment(
                db,
                tenant_id,
                predecessor.id,
                TeacherAssignmentEnd(
                    academic_term_id=uuid.uuid4(),
                    effective_to=today,
                    reason="End current teacher early",
                ),
            )

    delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_reassign_planned_end_defaults_takeover_to_next_day() -> None:
    today = date.today()
    tenant_id = uuid.uuid4()
    class_id = uuid.uuid4()
    curriculum_subject_id = uuid.uuid4()
    replacement_teacher_id = uuid.uuid4()
    planned_end = today + timedelta(days=10)
    current = _assignment(
        tenant_id=tenant_id,
        class_id=class_id,
        curriculum_subject_id=curriculum_subject_id,
        effective_from=today - timedelta(days=30),
        effective_to=planned_end,
    )
    created: list[TeacherAssignment] = []

    async def _create(_db, assignment):
        assignment.id = uuid.uuid4()
        created.append(assignment)
        return assignment

    db = AsyncMock()
    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._scheduled_takeover_successor",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._load_curriculum_subject_context",
            new=AsyncMock(
                return_value=(
                    SimpleNamespace(id=curriculum_subject_id, subject_id=uuid.uuid4()),
                    SimpleNamespace(academic_level_id=uuid.uuid4()),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_curriculum_subject_available_to_class",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    id=uuid.uuid4(),
                    start_date=today - timedelta(days=60),
                    end_date=today + timedelta(days=60),
                )
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_backdated_assignment_change_safe",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(side_effect=lambda _db, row: row),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_teacher_assignment",
            new=AsyncMock(side_effect=_create),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
    ):
        await StudentAcademicService.reassign_teacher_assignment(
            db,
            tenant_id,
            current.id,
            TeacherAssignmentReassign(
                teacher_membership_id=replacement_teacher_id,
                academic_term_id=uuid.uuid4(),
                effective_from=None,
                reason="Replace teacher after planned end",
            ),
        )

    assert len(created) == 1
    replacement = created[0]
    assert replacement.effective_from == planned_end + timedelta(days=1)
    assert current.effective_to == planned_end


@pytest.mark.asyncio
async def test_reassign_still_blocks_a_real_scheduled_takeover() -> None:
    today = date.today()
    current = _assignment(
        effective_from=today - timedelta(days=30),
        effective_to=today + timedelta(days=10),
    )
    successor = _assignment(
        tenant_id=current.tenant_id,
        class_id=current.class_id,
        curriculum_subject_id=current.curriculum_subject_id,
        effective_from=current.effective_to + timedelta(days=1),
    )
    db = AsyncMock()

    with (
        patch(
            "app.modules.student_academics.service.ensure_academic_write_window",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._scheduled_takeover_successor",
            new=AsyncMock(return_value=successor),
        ),
    ):
        with pytest.raises(ConflictException, match="takeover is already scheduled"):
            await StudentAcademicService.reassign_teacher_assignment(
                db,
                current.tenant_id,
                current.id,
                TeacherAssignmentReassign(
                    teacher_membership_id=uuid.uuid4(),
                    academic_term_id=uuid.uuid4(),
                    reason="Attempt duplicate takeover",
                ),
            )
