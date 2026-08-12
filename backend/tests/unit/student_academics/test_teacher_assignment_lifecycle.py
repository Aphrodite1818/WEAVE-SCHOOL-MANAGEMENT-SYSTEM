from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
        level_subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        is_active=True,
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
            TeacherAssignmentEnd(effective_to=assignment.effective_from),
        )
    assert assignment.is_active is False
    assert assignment.effective_to == assignment.effective_from
    db.commit.assert_awaited_once()
