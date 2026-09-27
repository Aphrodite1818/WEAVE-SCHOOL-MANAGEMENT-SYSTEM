import uuid

import pytest
from pydantic import ValidationError

from app.modules.student_academics.curriculum_v2_schemas import (
    CurriculumSubjectCreate,
    CurriculumSubjectUpdate,
)
from app.modules.student_academics.elective_schemas import (
    ElectiveGroupCreate,
    StudentElectiveSelectionUpdate,
)


def test_elective_subject_requires_group() -> None:
    with pytest.raises(ValidationError):
        CurriculumSubjectCreate(subject_id=uuid.uuid4(), is_elective=True)


def test_compulsory_subject_rejects_elective_group() -> None:
    with pytest.raises(ValidationError):
        CurriculumSubjectCreate(
            subject_id=uuid.uuid4(),
            is_elective=False,
            elective_group_id=uuid.uuid4(),
        )


def test_valid_elective_subject_carries_group() -> None:
    group_id = uuid.uuid4()
    payload = CurriculumSubjectCreate(
        subject_id=uuid.uuid4(),
        is_elective=True,
        elective_group_id=group_id,
    )
    assert payload.elective_group_id == group_id


def test_curriculum_patch_can_explicitly_clear_group_when_making_compulsory() -> None:
    payload = CurriculumSubjectUpdate(
        is_elective=False,
        elective_group_id=None,
    )
    assert payload.is_elective is False
    assert "elective_group_id" in payload.model_fields_set
    assert payload.elective_group_id is None


def test_elective_group_choice_bounds_are_validated() -> None:
    with pytest.raises(ValidationError):
        ElectiveGroupCreate(
            name="Languages",
            minimum_choices=3,
            maximum_choices=2,
        )


def test_student_elective_selection_rejects_duplicates() -> None:
    curriculum_subject_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        StudentElectiveSelectionUpdate(
            curriculum_subject_ids=[curriculum_subject_id, curriculum_subject_id]
        )
