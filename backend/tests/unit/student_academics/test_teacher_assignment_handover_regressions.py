from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.schemas import TeacherAssignmentScheduleCancel
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
    ):
        preview = await StudentAcademicService.teacher_assignment_dependency_preview(
            db, assignment.tenant_id, assignment.id
        )

    assert preview.can_end is True
    assert preview.can_reassign is False
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
