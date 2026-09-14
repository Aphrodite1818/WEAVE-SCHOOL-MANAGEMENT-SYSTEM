from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService


def _scalar_result(values):
    result = MagicMock()
    result.scalars.return_value = values
    return result


def _row_result(values):
    result = MagicMock()
    result.all.return_value = values
    return result


@pytest.mark.asyncio
async def test_subject_availability_keeps_partial_coverage_and_marks_full_coverage() -> None:
    tenant_id = uuid.uuid4()
    level_id = uuid.uuid4()
    term_id = uuid.uuid4()
    partial_subject_id = uuid.uuid4()
    covered_subject_id = uuid.uuid4()
    no_eligible_classes_subject_id = uuid.uuid4()
    first_class = SimpleNamespace(id=uuid.uuid4())
    second_class = SimpleNamespace(id=uuid.uuid4())
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar_result(
                    [
                        partial_subject_id,
                        covered_subject_id,
                        no_eligible_classes_subject_id,
                    ]
                ),
                _scalar_result([first_class, second_class]),
                _row_result(
                    [
                        (partial_subject_id, first_class.id),
                        (covered_subject_id, first_class.id),
                        (covered_subject_id, second_class.id),
                    ]
                ),
            ]
        )
    )
    resolved = {
        first_class.id: [
            SimpleNamespace(curriculum_subject_id=partial_subject_id),
            SimpleNamespace(curriculum_subject_id=covered_subject_id),
        ],
        second_class.id: [
            SimpleNamespace(curriculum_subject_id=partial_subject_id),
            SimpleNamespace(curriculum_subject_id=covered_subject_id),
        ],
    }

    with (
        patch.object(
            AcademicCurriculumService,
            "_curriculum",
            new=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())),
        ),
        patch(
            "app.modules.student_academics.curriculum_v2_service."
            "CurriculumResolutionService.resolve_classes_subjects",
            new=AsyncMock(return_value=resolved),
        ) as resolve_subjects,
    ):
        response = await AcademicCurriculumService.teacher_assignment_subject_availability(
            db,
            tenant_id=tenant_id,
            academic_level_id=level_id,
            academic_term_id=term_id,
        )

    availability = {item.curriculum_subject_id: item for item in response}
    assert availability[partial_subject_id].eligible_class_count == 2
    assert availability[partial_subject_id].assigned_class_count == 1
    assert availability[partial_subject_id].unassigned_class_count == 1
    assert availability[covered_subject_id].unassigned_class_count == 0
    assert availability[no_eligible_classes_subject_id].eligible_class_count == 0
    assert availability[no_eligible_classes_subject_id].unassigned_class_count == 0
    resolve_subjects.assert_awaited_once()
    assert resolve_subjects.await_args.kwargs["class_ids"] == {first_class.id, second_class.id}
