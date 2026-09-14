from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictException
from app.modules.student_academics.academic_evidence import AcademicEvidenceProtection
from app.modules.student_academics.curriculum_service import ResolvedCurriculumSubject
from app.modules.student_academics.curriculum_v2_schemas import TeacherAssignmentBulkCreate
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.service import StudentAcademicService


def _assignment(*, starts_on: date) -> TeacherAssignment:
    return TeacherAssignment(
        id=uuid4(),
        tenant_id=uuid4(),
        class_id=uuid4(),
        curriculum_subject_id=uuid4(),
        teacher_membership_id=uuid4(),
        effective_from=starts_on,
        effective_to=None,
    )


@pytest.mark.asyncio
async def test_reconciliation_ends_removed_assignment_and_preserves_general() -> None:
    boundary = date.today() + timedelta(days=10)
    removed = _assignment(starts_on=date.today() - timedelta(days=20))
    general = _assignment(starts_on=date.today() - timedelta(days=20))
    general.class_id = removed.class_id
    rows = MagicMock()
    rows.scalars.return_value = [removed, general]
    db = SimpleNamespace(
        execute=AsyncMock(return_value=rows), add=MagicMock(), delete=AsyncMock(), flush=AsyncMock()
    )
    resolved = [
        ResolvedCurriculumSubject(
            curriculum_subject_id=general.curriculum_subject_id,
            subject_id=uuid4(),
            academic_level_department_id=None,
            is_elective=False,
            is_general=True,
        )
    ]
    term = SimpleNamespace(id=uuid4(), start_date=boundary, end_date=boundary + timedelta(days=80))

    with patch(
        "app.modules.student_academics.curriculum_v2_service.CurriculumResolutionService.resolve_classes_subjects",
        new=AsyncMock(return_value={removed.class_id: resolved}),
    ):
        counts = await AcademicCurriculumService.reconcile_teacher_assignments_for_term(
            db, tenant_id=removed.tenant_id, term=term, acting_admin_id=uuid4()
        )

    assert removed.effective_to == boundary - timedelta(days=1)
    assert general.effective_to is None
    assert counts == {"ended": 1, "deleted_scheduled": 0}
    db.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_future_assignment_blocks_transition_without_rewriting_history() -> None:
    boundary = date.today() + timedelta(days=10)
    future = _assignment(starts_on=boundary + timedelta(days=5))
    rows = MagicMock()
    rows.scalars.return_value = [future]
    db = SimpleNamespace(
        execute=AsyncMock(return_value=rows), add=MagicMock(), delete=AsyncMock(), flush=AsyncMock()
    )
    term = SimpleNamespace(id=uuid4(), start_date=boundary, end_date=boundary + timedelta(days=80))

    with patch(
        "app.modules.student_academics.curriculum_v2_service.CurriculumResolutionService.resolve_classes_subjects",
        new=AsyncMock(return_value={future.class_id: []}),
    ):
        with pytest.raises(ConflictException, match="scheduled teacher assignment"):
            await AcademicCurriculumService.reconcile_teacher_assignments_for_term(
                db, tenant_id=future.tenant_id, term=term, acting_admin_id=uuid4()
            )

    assert future.effective_to is None
    db.delete.assert_not_awaited()
    db.add.assert_not_called()
    db.flush.assert_not_awaited()


def test_teacher_assignments_alone_do_not_block_reinterpretation() -> None:
    AcademicEvidenceProtection.ensure_none(
        {"results": 0, "report_cards": 0, "cbt": 0},
        operation="Class specialization change",
    )


@pytest.mark.parametrize("evidence", ["results", "report_cards", "cbt"])
def test_each_immutable_evidence_type_blocks_reinterpretation(evidence: str) -> None:
    counts = {"results": 0, "report_cards": 0, "cbt": 0}
    counts[evidence] = 1
    with pytest.raises(ConflictException, match="immutable academic evidence"):
        AcademicEvidenceProtection.ensure_none(counts, operation="Class specialization change")


@pytest.mark.asyncio
async def test_bulk_assignment_revalidates_each_explicit_class_atomically() -> None:
    tenant_id = uuid4()
    class_ids = [uuid4(), uuid4()]
    assignment_ids = [uuid4(), uuid4()]
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    payload = TeacherAssignmentBulkCreate(
        teacher_membership_id=uuid4(),
        curriculum_subject_id=uuid4(),
        academic_term_id=uuid4(),
        class_ids=class_ids,
    )

    with patch.object(
        StudentAcademicService,
        "create_teacher_assignment",
        new=AsyncMock(
            side_effect=[
                SimpleNamespace(id=assignment_ids[0]),
                SimpleNamespace(id=assignment_ids[1]),
            ]
        ),
    ) as create:
        response = await StudentAcademicService.create_teacher_assignments_bulk(
            db, tenant_id, payload
        )

    assert [call.args[2].class_id for call in create.await_args_list] == class_ids
    assert all(call.kwargs["commit"] is False for call in create.await_args_list)
    assert response.created == 2
    assert response.assignment_ids == assignment_ids
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_assignment_rolls_back_when_one_class_fails_revalidation() -> None:
    db = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    payload = TeacherAssignmentBulkCreate(
        teacher_membership_id=uuid4(),
        curriculum_subject_id=uuid4(),
        academic_term_id=uuid4(),
        class_ids=[uuid4(), uuid4()],
    )

    with (
        patch.object(
            StudentAcademicService,
            "create_teacher_assignment",
            new=AsyncMock(
                side_effect=[
                    SimpleNamespace(id=uuid4()),
                    ConflictException("not eligible"),
                ]
            ),
        ),
        pytest.raises(ConflictException, match="not eligible"),
    ):
        await StudentAcademicService.create_teacher_assignments_bulk(db, uuid4(), payload)

    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
