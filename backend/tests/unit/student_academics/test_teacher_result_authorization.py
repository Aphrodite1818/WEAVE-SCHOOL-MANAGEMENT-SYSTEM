from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenException
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.router import list_my_assignment_students
from app.modules.student_academics.schemas import StudentSubjectResultUpsert
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
