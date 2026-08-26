from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.schemas import TeacherAssignmentEnd
from app.modules.student_academics.service import StudentAcademicService


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

    loaded_subject, loaded_curriculum = (
        await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=curriculum_subject.id,
            require_active=False,
        )
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
