from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.report_cards.comment_models import TeacherCommentStatus
from app.modules.report_cards.comment_schemas import (
    CommentTemplateWrite,
    PersonalCommentTemplateCreate,
    TeacherCommentWrite,
)
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.teachers.models import TeacherMembership


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        values = self.value if isinstance(self.value, list) else [self.value]
        return [item for item in values if item is not None]


def make_comment(*, teacher_id, student_id, enrollment_id, class_id, session_id, term_id):
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


def test_public_personal_comment_contract_is_text_plus_one_grade_only():
    grade_id = uuid4()
    payload = PersonalCommentTemplateCreate(
        text="Very good performance. Keep it up.",
        grading_scale_id=grade_id,
        is_default=True,
    )

    assert payload.text == "Very good performance. Keep it up."
    assert payload.grading_scale_id == grade_id
    assert payload.is_default is True
    assert "name" not in payload.model_fields_set
    assert not hasattr(payload, "grading_scale_ids")


@pytest.mark.asyncio
async def test_subject_teacher_cannot_use_class_teacher_comment_capability(monkeypatch):
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    monkeypatch.setattr(
        ReportCommentService,
        "_is_current_class_teacher",
        AsyncMock(return_value=False),
    )

    with pytest.raises(ForbiddenException, match="class teacher"):
        await ReportCommentService._require_class_teacher_capability(
            SimpleNamespace(), teacher, class_id=uuid4()
        )


@pytest.mark.asyncio
async def test_teacher_comment_draft_can_be_saved_before_results_are_ready(monkeypatch):
    """Service remains tolerant for historical/internal callers; HTTP routes gate new work."""

    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    student_id = uuid4()
    class_id = uuid4()
    enrollment_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    comment = make_comment(
        teacher_id=teacher.id,
        student_id=student_id,
        enrollment_id=enrollment_id,
        class_id=class_id,
        session_id=session_id,
        term_id=term_id,
    )
    classroom = SimpleNamespace(id=class_id, teacher_membership_id=teacher.id)
    enrollment = SimpleNamespace(id=enrollment_id, class_id=class_id)
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
        AsyncMock(return_value=(False, None, None)),
    )

    response = await ReportCommentService.save_teacher_comment(
        db,
        teacher=teacher,
        student_id=student_id,
        payload=TeacherCommentWrite(
            academic_session_id=session_id,
            academic_term_id=term_id,
            comment_text="Keep improving your consistency.",
        ),
        submit=False,
    )

    assert response.status == TeacherCommentStatus.DRAFT.value
    assert response.average_snapshot == Decimal("0")
    assert response.grade_snapshot == "Pending"
    assert response.comment_text == "Keep improving your consistency."
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_teacher_comment_submission_requires_locked_expected_results(monkeypatch):
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    student_id = uuid4()
    class_id = uuid4()
    enrollment = SimpleNamespace(id=uuid4(), class_id=class_id)
    classroom = SimpleNamespace(id=class_id, teacher_membership_id=teacher.id)

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
        AsyncMock(return_value=(False, Decimal("61"), None)),
    )

    with pytest.raises(BadRequestException, match="all expected results are locked"):
        await ReportCommentService.save_teacher_comment(
            SimpleNamespace(),
            teacher=teacher,
            student_id=student_id,
            payload=TeacherCommentWrite(
                academic_session_id=uuid4(),
                academic_term_id=uuid4(),
                comment_text="Ready when results are final.",
            ),
            submit=True,
        )


@pytest.mark.asyncio
async def test_submitted_comment_snapshots_average_and_grade(monkeypatch):
    teacher = TeacherMembership(id=uuid4(), tenant_id=uuid4())
    student_id = uuid4()
    class_id = uuid4()
    enrollment_id = uuid4()
    session_id = uuid4()
    term_id = uuid4()
    comment = make_comment(
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
        AsyncMock(return_value=(True, Decimal("84.5"), grading_scale)),
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

    assert response.status == TeacherCommentStatus.SUBMITTED.value
    assert response.average_snapshot == Decimal("84.5")
    assert response.grade_snapshot == "A"
    assert response.submitted_at is not None


@pytest.mark.asyncio
async def test_result_change_marks_submitted_teacher_comment_needs_review():
    comment = SimpleNamespace(status=TeacherCommentStatus.SUBMITTED)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=ScalarResult([comment])),
        add=Mock(),
    )

    await ReportCommentService.invalidate_for_result_change(
        db,
        tenant_id=uuid4(),
        student_id=uuid4(),
        academic_session_id=uuid4(),
        academic_term_id=uuid4(),
    )

    assert comment.status == TeacherCommentStatus.NEEDS_REVIEW
    db.add.assert_called_once_with(comment)


def test_internal_template_defaults_must_be_grade_mappings():
    grade_id = uuid4()
    with pytest.raises(ValueError, match="defaults must also appear"):
        CommentTemplateWrite(
            name="Internal derived name",
            text="Excellent progress.",
            grading_scale_ids=[],
            default_grading_scale_ids=[grade_id],
        )
