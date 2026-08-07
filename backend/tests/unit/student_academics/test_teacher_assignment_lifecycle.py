from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.schemas import (
    TeacherAssignmentDelete,
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
)
from app.modules.student_academics.service import StudentAcademicService


def _assignment(
    *, active: bool = True, effective_to: date | None = None
) -> TeacherAssignment:
    now = datetime.now(timezone.utc)
    return TeacherAssignment(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        class_subject_id=uuid.uuid4(),
        teacher_membership_id=uuid.uuid4(),
        is_active=active,
        effective_from=date(2026, 1, 10),
        effective_to=effective_to,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_end_historical_assignment_missing_effective_to_requires_repair() -> None:
    assignment = _assignment(active=False, effective_to=None)
    db = AsyncMock()

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
        new=AsyncMock(return_value=assignment),
    ):
        with pytest.raises(ConflictException, match="requires administrative repair"):
            await StudentAcademicService.end_teacher_assignment(
                db,
                assignment.tenant_id,
                assignment.id,
                TeacherAssignmentEnd(effective_to=date(2026, 1, 20)),
            )

    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_end_active_assignment_allows_same_day_end_date() -> None:
    assignment = _assignment(active=True, effective_to=None)
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
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=None),
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


@pytest.mark.asyncio
async def test_dependency_preview_reports_structured_counts_and_capabilities() -> None:
    assignment = _assignment(active=False, effective_to=date(2026, 1, 20))

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(
                return_value={
                    "student_results": 2,
                    "report_card_references": 1,
                    "other_academic_records": 0,
                }
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[_assignment(active=True)]),
        ),
    ):
        preview = await StudentAcademicService.teacher_assignment_dependency_preview(
            AsyncMock(),
            assignment.tenant_id,
            assignment.id,
        )

    assert preview.dependency_counts["student_results"] == 2
    assert preview.dependency_counts["report_card_references"] == 1
    assert preview.dependency_counts["later_assignment_history"] == 1
    assert preview.can_end is False
    assert preview.can_reassign is False
    assert preview.can_delete is False
    assert preview.blocker_messages


@pytest.mark.asyncio
async def test_delete_assignment_returns_structured_dependency_payload_when_blocked() -> (
    None
):
    assignment = _assignment(active=False, effective_to=date(2026, 1, 20))

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.count_teacher_assignment_dependencies",
            new=AsyncMock(
                return_value={
                    "student_results": 1,
                    "report_card_references": 0,
                    "other_academic_records": 0,
                }
            ),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[]),
        ),
    ):
        with pytest.raises(ConflictException) as exc_info:
            await StudentAcademicService.delete_teacher_assignment(
                AsyncMock(),
                assignment.tenant_id,
                assignment.id,
                TeacherAssignmentDelete(confirmation="DELETE_TEACHER_ASSIGNMENT"),
            )

    assert exc_info.value.payload["dependency_counts"]["student_results"] == 1
    assert exc_info.value.payload["blocker_messages"]


@pytest.mark.asyncio
async def test_list_teacher_assignments_builds_response_from_joined_records() -> None:
    assignment = _assignment(active=True)
    record = {
        "assignment": assignment,
        "class_id": uuid.uuid4(),
        "class_name": "JSS 1",
        "class_arm": "A",
        "subject_id": uuid.uuid4(),
        "subject_name": "Mathematics",
        "subject_code": "MTH",
        "teacher_name": "Ada Lovelace",
        "teacher_staff_id": "T-001",
    }

    with patch(
        "app.modules.student_academics.service.StudentAcademicRepository.list_teacher_assignment_rows",
        new=AsyncMock(return_value=([record], 1)),
    ):
        items, total = await StudentAcademicService.list_teacher_assignment_responses(
            AsyncMock(),
            assignment.tenant_id,
            status="active",
            search="Ada",
            skip=0,
            limit=25,
        )

    assert total == 1
    assert items[0].teacher_name == "Ada Lovelace"
    assert items[0].class_name == "JSS1"
    assert items[0].subject_code == "MTH"


@pytest.mark.asyncio
async def test_reassign_teacher_allows_same_day_replacement() -> None:
    current = _assignment(active=True)
    replacement_teacher_id = uuid.uuid4()
    replacement = _assignment(active=True)
    db = AsyncMock()
    class_subject = SimpleNamespace(
        id=current.class_subject_id,
        class_id=uuid.uuid4(),
        subject_id=uuid.uuid4(),
        is_active=True,
        archived_at=None,
    )
    classroom = SimpleNamespace(is_active=True, archived_at=None)
    subject = SimpleNamespace(is_active=True, archived_at=None)

    async def create_assignment(_, assignment):
        replacement.teacher_membership_id = assignment.teacher_membership_id
        replacement.class_subject_id = assignment.class_subject_id
        replacement.effective_from = assignment.effective_from
        replacement.effective_to = assignment.effective_to
        return replacement

    with (
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_teacher_assignment_by_id",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_class_subject_by_id",
            new=AsyncMock(return_value=class_subject),
        ),
        patch(
            "app.modules.student_academics.service.ClassRoomRepository.get_by_id",
            new=AsyncMock(return_value=classroom),
        ),
        patch(
            "app.modules.student_academics.service.SubjectRepository.get_subject_by_id",
            new=AsyncMock(return_value=subject),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._validate_teacher_capability",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_active_teacher_assignment_for_class_subject",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.get_later_teacher_assignments",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.save_teacher_assignment",
            new=AsyncMock(return_value=current),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicRepository.create_teacher_assignment",
            new=AsyncMock(side_effect=create_assignment),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._ensure_compatibility_assignment",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._record_teacher_assignment_audit",
            new=AsyncMock(),
        ),
        patch(
            "app.modules.student_academics.service.StudentAcademicService._build_teacher_assignment_response",
            new=AsyncMock(return_value=SimpleNamespace(id=replacement.id)),
        ),
    ):
        await StudentAcademicService.reassign_teacher_assignment(
            db,
            current.tenant_id,
            current.id,
            TeacherAssignmentReassign(
                teacher_membership_id=replacement_teacher_id,
                effective_from=current.effective_from,
            ),
        )

    assert current.is_active is False
    assert current.effective_to == current.effective_from
    assert replacement.teacher_membership_id == replacement_teacher_id
    assert replacement.effective_from == current.effective_from
