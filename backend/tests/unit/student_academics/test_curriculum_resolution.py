from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.classes.models import AcademicLevelStatus
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.models import AcademicTermName


def _scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _rows(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _scalars(values):
    result = MagicMock()
    result.scalars.return_value = values
    return result


def _subject(row_id):
    return SimpleNamespace(id=row_id, subject_id=uuid4(), is_elective=False)


@pytest.mark.asyncio
async def test_pre_specialization_includes_general_science_and_arts() -> None:
    tenant_id, level_id, class_id, term_id = uuid4(), uuid4(), uuid4(), uuid4()
    general_id, science_id, arts_id = uuid4(), uuid4(), uuid4()
    science_department_id, arts_department_id = uuid4(), uuid4()
    subjects = [
        (_subject(general_id), SimpleNamespace()),
        (_subject(science_id), SimpleNamespace()),
        (_subject(arts_id), SimpleNamespace()),
    ]
    links = [
        SimpleNamespace(
            curriculum_subject_id=science_id, academic_level_department_id=science_department_id
        ),
        SimpleNamespace(
            curriculum_subject_id=arts_id, academic_level_department_id=arts_department_id
        ),
    ]
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar(SimpleNamespace(id=class_id, academic_level_id=level_id)),
                _scalar(SimpleNamespace(id=term_id, name=AcademicTermName.FIRST_TERM)),
                _scalar(
                    SimpleNamespace(
                        id=level_id,
                        status=AcademicLevelStatus.ACTIVE,
                        specialization_required_from_term_position=2,
                    )
                ),
                _rows(subjects),
                _scalars(links),
            ]
        )
    )

    resolved = await CurriculumResolutionService.resolve_class_subjects(
        db, tenant_id=tenant_id, class_id=class_id, academic_term_id=term_id
    )

    assert {item.curriculum_subject_id for item in resolved} == {general_id, science_id, arts_id}
    assert next(item for item in resolved if item.curriculum_subject_id == general_id).is_general
    assert all(item.academic_level_department_id is None for item in resolved)


@pytest.mark.asyncio
async def test_post_specialization_includes_general_and_matching_department_only() -> None:
    tenant_id, level_id, class_id, term_id = uuid4(), uuid4(), uuid4(), uuid4()
    general_id, science_id, arts_id = uuid4(), uuid4(), uuid4()
    science_department_id, arts_department_id = uuid4(), uuid4()
    subjects = [
        (_subject(general_id), SimpleNamespace()),
        (_subject(science_id), SimpleNamespace()),
        (_subject(arts_id), SimpleNamespace()),
    ]
    links = [
        SimpleNamespace(
            curriculum_subject_id=science_id, academic_level_department_id=science_department_id
        ),
        SimpleNamespace(
            curriculum_subject_id=arts_id, academic_level_department_id=arts_department_id
        ),
    ]
    exact = MagicMock()
    exact.first.return_value = (
        SimpleNamespace(academic_level_department_id=science_department_id),
        SimpleNamespace(
            id=science_department_id, academic_level_id=level_id, is_active=True, archived_at=None
        ),
        SimpleNamespace(is_active=True, archived_at=None),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalar(SimpleNamespace(id=class_id, academic_level_id=level_id)),
                _scalar(SimpleNamespace(id=term_id, name=AcademicTermName.SECOND_TERM)),
                _scalar(
                    SimpleNamespace(
                        id=level_id,
                        status=AcademicLevelStatus.ACTIVE,
                        specialization_required_from_term_position=2,
                    )
                ),
                exact,
                _rows(subjects),
                _scalars(links),
            ]
        )
    )

    resolved = await CurriculumResolutionService.resolve_class_subjects(
        db, tenant_id=tenant_id, class_id=class_id, academic_term_id=term_id
    )

    assert {item.curriculum_subject_id for item in resolved} == {general_id, science_id}
    matching = next(item for item in resolved if item.curriculum_subject_id == science_id)
    assert matching.academic_level_department_id == science_department_id
    assert "class_term_department_assignments.academic_term_id" in str(
        db.execute.await_args_list[3].args[0]
    )
