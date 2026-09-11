from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.report_cards.comment_models import TeacherCommentStatus
from app.modules.report_cards.comment_router import _ensure_teacher_comment_ready
from app.modules.report_cards.comment_schemas import CommentTemplateCreate, TeacherCommentWrite
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.repository import ReportCardRepository
from app.modules.teachers.models import TeacherMembership


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def _comment(*, teacher_id, student_id, enrollment_id, class_id, session_id, term_id):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        student_id=student_id,
        student_enrollment_id=enrollment_id,
        class_id=class_id,
        academic_session_id=session_id,
        academic_term_id=term_id,
        teacher_membership_id=teacher_id,
        average_snapshot=Decimal("0"),
        grade_snapshot="Pending",
        comment_text="Draft",
        source_template_id=None,
        status=TeacherCommentStatus.DRAFT,
        submitted_at=None,
        created_at=now,
        updated_at=now,
    )


def test_public_comment_contract_uses_inclusive_score_range() -> None:
    payload = CommentTemplateCreate(
        text="Strong effort this term.",
        minimum_score=Decimal("60"),
        maximum_score=Decimal("70"),
        is_default=False,
    )

    assert payload.minimum_score == Decimal("60")
    assert payload.maximum_score == Decimal("70")
    assert not hasattr(payload, "grading_scale_id")


@pytest.mark.asyncio
async def test_subject_teacher_cannot_use_class_teacher_comment_capability(monkeypatch) -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    monkeypatch.setattr(
        ReportCommentService,
        "_is_current_class_teacher",
        AsyncMock(return_value=False),
    )

    with pytest.raises(ForbiddenException, match="class teacher"):
        await ReportCommentService._require_class_teacher_capability(
            SimpleNamespace(),
            teacher,
            class_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_teacher_comment_http_boundary_rejects_work_before_results_are_ready(
    monkeypatch,
) -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    monkeypatch.setattr(
        ReportCommentService,
        "_academic_readiness",
        AsyncMock(return_value=(False, None, None)),
    )

    with pytest.raises(BadRequestException, match="finalized and locked"):
        await _ensure_teacher_comment_ready(
            SimpleNamespace(),
            teacher,
            uuid4(),
            TeacherCommentWrite(
                academic_session_id=uuid4(),
                academic_term_id=uuid4(),
                comment_text="Not ready yet.",
            ),
        )


@pytest.mark.asyncio
async def test_teacher_cannot_select_comment_outside_student_performance_range(monkeypatch) -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    selected_template_id = uuid4()
    monkeypatch.setattr(
        ReportCommentService,
        "_academic_readiness",
        AsyncMock(return_value=(True, Decimal("68.50"), SimpleNamespace(grade="B"))),
    )
    monkeypatch.setattr(
        ReportCommentService,
        "templates_for_performance",
        AsyncMock(return_value=[SimpleNamespace(id=uuid4())]),
    )

    with pytest.raises(BadRequestException, match="performance range"):
        await _ensure_teacher_comment_ready(
            SimpleNamespace(),
            teacher,
            uuid4(),
            TeacherCommentWrite(
                academic_session_id=uuid4(),
                academic_term_id=uuid4(),
                comment_text="Selected wording.",
                source_template_id=selected_template_id,
            ),
        )


@pytest.mark.asyncio
async def test_teacher_can_select_comment_covering_exact_boundary(monkeypatch) -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    selected_template_id = uuid4()
    monkeypatch.setattr(
        ReportCommentService,
        "_academic_readiness",
        AsyncMock(return_value=(True, Decimal("70"), SimpleNamespace(grade="B"))),
    )
    monkeypatch.setattr(
        ReportCommentService,
        "templates_for_performance",
        AsyncMock(return_value=[SimpleNamespace(id=selected_template_id)]),
    )

    await _ensure_teacher_comment_ready(
        SimpleNamespace(),
        teacher,
        uuid4(),
        TeacherCommentWrite(
            academic_session_id=uuid4(),
            academic_term_id=uuid4(),
            comment_text="Boundary wording.",
            source_template_id=selected_template_id,
        ),
    )


@pytest.mark.asyncio
async def test_submitted_comment_snapshots_weighted_performance_percentage(monkeypatch) -> None:
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    student_id = uuid4()
    class_id = uuid4()
    enrollment_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    comment = _comment(
        teacher_id=teacher.id,
        student_id=student_id,
        enrollment_id=enrollment_id,
        class_id=class_id,
        session_id=session_id,
        term_id=term_id,
    )
    classroom = SimpleNamespace(id=class_id, teacher_membership_id=teacher.id)
    enrollment = SimpleNamespace(id=enrollment_id, class_id=class_id)
    grading_scale = SimpleNamespace(id=uuid4(), grade="A")
    db = SimpleNamespace(
        execute=AsyncMock(return_value=ScalarResult(comment)),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    monkeypatch.setattr(
        ReportCommentService,
        "_current_comment_context",
        AsyncMock(return_value=(enrollment, classroom)),
    )
    monkeypatch.setattr(
        ReportCommentService,
        "_require_class_teacher_capability",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ReportCommentService,
        "_academic_readiness",
        AsyncMock(return_value=(True, Decimal("84.50"), grading_scale)),
    )
    mark_outdated = AsyncMock()
    monkeypatch.setattr(
        ReportCardRepository,
        "mark_outdated_for_student_period",
        mark_outdated,
    )

    response = await ReportCommentService.save_teacher_comment(
        db,
        teacher=teacher,
        student_id=student_id,
        payload=TeacherCommentWrite(
            academic_session_id=session_id,
            academic_term_id=term_id,
            comment_text="Excellent work this term.",
        ),
        submit=True,
    )

    assert response.average_snapshot == Decimal("84.50")
    assert response.grade_snapshot == "A"
    assert response.status == TeacherCommentStatus.SUBMITTED.value
    assert comment.average_snapshot == Decimal("84.50")
    assert comment.grade_snapshot == "A"
    mark_outdated.assert_awaited_once_with(
        db,
        teacher.tenant_id,
        student_id,
        session_id,
        term_id,
    )
