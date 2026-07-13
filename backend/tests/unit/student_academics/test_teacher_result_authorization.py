from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.student_academics.models import AcademicResultStatus
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.router import (
    _ensure_teacher_can_write_result,
    list_my_assignment_students,
)
from app.modules.student_academics.schemas import StudentSubjectResultUpsert
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.repository import StudentRepository
from app.modules.teachers.models import Teacher


def _teacher() -> Teacher:
    return Teacher(
        id=uuid4(),
        tenant_id=uuid4(),
        email=f"teacher-{uuid4()}@example.com",
        password_hash="hashed",
    )


def _payload(*, teacher_assignment_id=None) -> StudentSubjectResultUpsert:
    return StudentSubjectResultUpsert(
        student_id=uuid4(),
        teacher_assignment_id=teacher_assignment_id or uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
        test_score=20,
        assessment_score=20,
        exam_score=50,
        status=AcademicResultStatus.DRAFT,
    )


@pytest.mark.asyncio
async def test_submitted_result_is_locked_for_teacher_assignment(monkeypatch) -> None:
    teacher = _teacher()
    payload = _payload()
    lookup = AsyncMock(
        return_value=SimpleNamespace(status=AcademicResultStatus.SUBMITTED)
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_result_by_teacher_assignment_scope",
        lookup,
    )

    with pytest.raises(ForbiddenException, match="Submitted scores are locked"):
        await _ensure_teacher_can_write_result(SimpleNamespace(), teacher, payload)

    lookup.assert_awaited_once_with(
        db=ANY,
        tenant_id=teacher.tenant_id,
        student_id=payload.student_id,
        teacher_assignment_id=payload.teacher_assignment_id,
        academic_session_id=payload.academic_session_id,
        academic_term_id=payload.academic_term_id,
    )


@pytest.mark.asyncio
async def test_teacher_cannot_list_students_for_another_teachers_assignment(
    monkeypatch,
) -> None:
    teacher = _teacher()
    assignment_id = uuid4()
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_teacher_assignment_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=assignment_id,
                teacher_id=uuid4(),
                class_subject_id=uuid4(),
                is_active=True,
            )
        ),
    )

    with pytest.raises(ForbiddenException, match="assigned to you"):
        await list_my_assignment_students(
            assignment_id=assignment_id,
            db=SimpleNamespace(),
            current_teacher=teacher,
        )


@pytest.mark.asyncio
async def test_teacher_result_listing_is_scoped_to_current_teacher(monkeypatch) -> None:
    teacher = _teacher()
    list_results = AsyncMock(return_value=([], 0))
    monkeypatch.setattr(StudentAcademicRepository, "list_results", list_results)

    items, total = await StudentAcademicService.list_results(
        SimpleNamespace(),
        teacher,
        class_id=uuid4(),
    )

    assert items == []
    assert total == 0
    assert list_results.await_args.kwargs["tenant_id"] == teacher.tenant_id
    assert list_results.await_args.kwargs["teacher_id"] == teacher.id


@pytest.mark.asyncio
async def test_teacher_cannot_write_result_for_another_teachers_assignment(
    monkeypatch,
) -> None:
    teacher = _teacher()
    payload = _payload()
    class_subject_id = uuid4()

    monkeypatch.setattr(
        StudentAcademicService,
        "_resolve_assignment_context",
        AsyncMock(
            return_value=(
                SimpleNamespace(
                    id=payload.teacher_assignment_id,
                    class_subject_id=class_subject_id,
                    teacher_id=uuid4(),
                ),
                None,
            )
        ),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_class_subject_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=class_subject_id,
                class_id=uuid4(),
                subject_id=uuid4(),
                tenant_id=teacher.tenant_id,
                is_active=True,
                is_core=True,
            )
        ),
    )

    with pytest.raises(ForbiddenException, match="assigned to you"):
        await StudentAcademicService.upsert_student_result(
            SimpleNamespace(),
            teacher,
            payload,
        )


@pytest.mark.asyncio
async def test_teacher_cannot_write_result_for_student_outside_assignment_class(
    monkeypatch,
) -> None:
    teacher = _teacher()
    payload = _payload()
    class_subject_id = uuid4()
    assigned_class_id = uuid4()

    monkeypatch.setattr(
        StudentAcademicService,
        "_resolve_assignment_context",
        AsyncMock(
            return_value=(
                SimpleNamespace(
                    id=payload.teacher_assignment_id,
                    class_subject_id=class_subject_id,
                    teacher_id=teacher.id,
                ),
                None,
            )
        ),
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_class_subject_by_id",
        AsyncMock(
            return_value=SimpleNamespace(
                id=class_subject_id,
                class_id=assigned_class_id,
                subject_id=uuid4(),
                tenant_id=teacher.tenant_id,
                is_active=True,
                is_core=True,
            )
        ),
    )
    monkeypatch.setattr(
        StudentRepository,
        "get_student_by_id",
        AsyncMock(return_value=SimpleNamespace(id=payload.student_id, class_id=uuid4())),
    )

    with pytest.raises(BadRequestException, match="does not belong"):
        await StudentAcademicService.upsert_student_result(
            SimpleNamespace(),
            teacher,
            payload,
        )
