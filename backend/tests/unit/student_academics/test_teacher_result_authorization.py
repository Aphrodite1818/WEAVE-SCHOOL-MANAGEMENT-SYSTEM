from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.report_cards.service import ReportCardService
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.router import list_my_assignment_students
from app.modules.student_academics.schemas import (
    StudentSubjectResultReopenRequest,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.repository import StudentRepository
from app.modules.teachers.models import TeacherMembership, TeacherMembershipStatus


def _teacher_membership() -> TeacherMembership:
    return TeacherMembership(
        id=uuid4(),
        tenant_id=uuid4(),
        teacher_account_id=uuid4(),
        staff_id="T-001",
        status=TeacherMembershipStatus.ACTIVE,
        joined_at=datetime.now(timezone.utc),
    )


def _payload(*, assignment_id=None) -> StudentSubjectResultUpsert:
    return StudentSubjectResultUpsert(
        student_id=uuid4(),
        teacher_assignment_id=assignment_id or uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        test_score=20,
        assessment_score=20,
        exam_score=50,
        status=AcademicResultStatus.DRAFT,
    )


def _admin(tenant_id):
    return SimpleNamespace(id=uuid4(), tenant_id=tenant_id)


def _result(status: AcademicResultStatus):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        student_id=uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        test_score=20,
        assessment_score=20,
        exam_score=50,
        status=status,
        recorded_by_actor_type="teacher",
        recorded_by_actor_id=uuid4(),
        submitted_at=None,
        submitted_by_actor_type=None,
        submitted_by_actor_id=None,
        approved_at=None,
        approved_by_admin_id=None,
        locked_at=None,
        locked_by_admin_id=None,
    )


async def _save_result(_db, result):
    return result


@pytest.mark.asyncio
async def test_teacher_cannot_list_students_for_another_memberships_assignment(
    monkeypatch,
) -> None:
    teacher = _teacher_membership()
    assignment_id = uuid4()
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_teacher_assignment_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=assignment_id,
                teacher_membership_id=uuid4(),
                class_subject_id=uuid4(),
                is_active=True,
            )
        ),
    )

    with pytest.raises(ForbiddenException, match="active assignments"):
        await list_my_assignment_students(
            assignment_id=assignment_id,
            db=SimpleNamespace(),
            current_teacher=teacher,
            skip=0,
            limit=100,
        )


@pytest.mark.asyncio
async def test_teacher_result_listing_is_scoped_to_membership(monkeypatch) -> None:
    teacher = _teacher_membership()
    list_results = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(StudentAcademicRepository, "list_results", list_results)

    items, total = await StudentAcademicService.list_results(
        SimpleNamespace(),
        teacher,
        class_id=uuid4(),
    )

    assert items == []
    assert total == 0
    assert list_results.await_args.args[1] == teacher.tenant_id
    assert list_results.await_args.kwargs["teacher_id"] == teacher.id


@pytest.mark.asyncio
async def test_teacher_cannot_write_result_for_another_memberships_assignment(
    monkeypatch,
) -> None:
    teacher = _teacher_membership()
    payload = _payload()
    class_subject = SimpleNamespace(
        id=uuid4(),
        class_id=uuid4(),
        subject_id=uuid4(),
        is_active=True,
    )
    assignment = SimpleNamespace(
        id=payload.teacher_assignment_id,
        teacher_membership_id=uuid4(),
        class_subject_id=class_subject.id,
    )
    compatibility = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        StudentAcademicService,
        "_resolve_assignment_context",
        AsyncMock(return_value=(assignment, compatibility, class_subject)),
    )

    with pytest.raises(ForbiddenException, match="own assignments"):
        await StudentAcademicService.upsert_student_result(
            SimpleNamespace(),
            teacher,
            payload,
        )


@pytest.mark.asyncio
async def test_teacher_cannot_write_result_for_student_outside_assignment_class(
    monkeypatch,
) -> None:
    teacher = _teacher_membership()
    payload = _payload()
    class_subject = SimpleNamespace(
        id=uuid4(),
        class_id=uuid4(),
        subject_id=uuid4(),
        is_active=True,
    )
    assignment = SimpleNamespace(
        id=payload.teacher_assignment_id,
        teacher_membership_id=teacher.id,
        class_subject_id=class_subject.id,
    )
    compatibility = SimpleNamespace(id=uuid4())
    monkeypatch.setattr(
        StudentAcademicService,
        "_resolve_assignment_context",
        AsyncMock(return_value=(assignment, compatibility, class_subject)),
    )
    monkeypatch.setattr(
        StudentRepository,
        "get_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=payload.student_id,
                class_id=uuid4(),
            )
        ),
    )

    with pytest.raises(ForbiddenException, match="currently enrolled"):
        await StudentAcademicService.upsert_student_result(
            SimpleNamespace(),
            teacher,
            payload,
        )


@pytest.mark.asyncio
async def test_admin_result_status_cannot_skip_lifecycle_states(monkeypatch) -> None:
    result = _result(AcademicResultStatus.DRAFT)
    admin = _admin(result.tenant_id)
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_result_by_id",
        AsyncMock(return_value=result),
    )

    with pytest.raises(BadRequestException, match="draft to locked"):
        await StudentAcademicService.update_result_status(
            SimpleNamespace(commit=AsyncMock()),
            admin,
            result.id,
            StudentSubjectResultStatusUpdate(status=AcademicResultStatus.LOCKED),
        )


@pytest.mark.asyncio
async def test_admin_result_forward_lifecycle_writes_service_metadata(monkeypatch) -> None:
    result = _result(AcademicResultStatus.DRAFT)
    admin = _admin(result.tenant_id)
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_result_by_id",
        AsyncMock(return_value=result),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "upsert_result",
        AsyncMock(side_effect=_save_result),
    )
    monkeypatch.setattr(
        StudentAcademicService,
        "_build_result_response",
        AsyncMock(side_effect=_save_result),
    )

    await StudentAcademicService.update_result_status(
        SimpleNamespace(commit=AsyncMock()),
        admin,
        result.id,
        StudentSubjectResultStatusUpdate(status=AcademicResultStatus.SUBMITTED),
    )
    assert result.status == AcademicResultStatus.SUBMITTED
    assert result.submitted_by_actor_type == "tenant_admin"
    assert result.submitted_by_actor_id == admin.id
    assert result.submitted_at is not None

    await StudentAcademicService.update_result_status(
        SimpleNamespace(commit=AsyncMock()),
        admin,
        result.id,
        StudentSubjectResultStatusUpdate(status=AcademicResultStatus.APPROVED),
    )
    assert result.status == AcademicResultStatus.APPROVED
    assert result.approved_by_admin_id == admin.id
    assert result.approved_at is not None

    await StudentAcademicService.update_result_status(
        SimpleNamespace(commit=AsyncMock()),
        admin,
        result.id,
        StudentSubjectResultStatusUpdate(status=AcademicResultStatus.LOCKED),
    )
    assert result.status == AcademicResultStatus.LOCKED
    assert result.locked_by_admin_id == admin.id
    assert result.locked_at is not None


@pytest.mark.asyncio
async def test_admin_reopen_locked_result_marks_cards_outdated_and_resets_current_lifecycle_metadata(
    monkeypatch,
) -> None:
    result = _result(AcademicResultStatus.LOCKED)
    result.submitted_at = datetime.now(timezone.utc)
    result.submitted_by_actor_type = "teacher"
    result.submitted_by_actor_id = uuid4()
    result.approved_at = datetime.now(timezone.utc)
    result.approved_by_admin_id = uuid4()
    result.locked_at = datetime.now(timezone.utc)
    result.locked_by_admin_id = uuid4()
    admin = _admin(result.tenant_id)
    mark_outdated = AsyncMock()
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_result_by_id",
        AsyncMock(return_value=result),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "upsert_result",
        AsyncMock(side_effect=_save_result),
    )
    monkeypatch.setattr(
        StudentAcademicService,
        "_build_result_response",
        AsyncMock(side_effect=_save_result),
    )
    monkeypatch.setattr(
        ReportCardService,
        "mark_outdated_for_score_change",
        mark_outdated,
    )

    await StudentAcademicService.reopen_result(
        SimpleNamespace(commit=AsyncMock()),
        admin,
        result.id,
        StudentSubjectResultReopenRequest(reason="Correction needed"),
    )

    assert result.status == AcademicResultStatus.DRAFT
    assert result.submitted_at is None
    assert result.submitted_by_actor_type is None
    assert result.submitted_by_actor_id is None
    assert result.approved_at is None
    assert result.approved_by_admin_id is None
    assert result.locked_at is None
    assert result.locked_by_admin_id is None
    mark_outdated.assert_awaited_once()
