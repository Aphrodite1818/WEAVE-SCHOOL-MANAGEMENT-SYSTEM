from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.classes.models import AcademicLevelStatus
from app.modules.student_academics.curriculum_service import ResolvedCurriculumSubject
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.models import AcademicTermName

SERVICE = "app.modules.student_academics.curriculum_v2_service"


def _rows(values):
    result = MagicMock()
    result.all.return_value = values
    return result


def _scalars(values):
    result = MagicMock()
    result.scalars.return_value = values
    return result


@pytest.mark.asyncio
async def test_term_readiness_blocks_an_empty_academic_structure() -> None:
    tenant_id, term_id = uuid4(), uuid4()
    term = SimpleNamespace(id=term_id, name=AcademicTermName.FIRST_TERM)
    db = SimpleNamespace(execute=AsyncMock(return_value=_scalars([])))

    with patch(
        f"{SERVICE}.AcademicLevelRepository.list_for_tenant",
        new=AsyncMock(return_value=[]),
    ):
        counts, blockers = await AcademicCurriculumService.specialization_readiness(
            db,
            tenant_id=tenant_id,
            term=term,
        )

    assert counts["active_academic_levels"] == 0
    assert counts["active_classes"] == 0
    assert counts["classes_missing_department"] == 0
    assert "Activate at least one academic level before opening the term." in blockers
    assert "Create at least one active class before opening the term." in blockers


@pytest.mark.asyncio
async def test_term_readiness_accepts_active_level_and_class_before_specialization() -> None:
    tenant_id, term_id, level_id, class_id = uuid4(), uuid4(), uuid4(), uuid4()
    level = SimpleNamespace(
        id=level_id,
        name="SS1",
        status=AcademicLevelStatus.ACTIVE,
        specialization_required_from_term_position=2,
    )
    classroom = SimpleNamespace(id=class_id, academic_level_id=level_id)
    term = SimpleNamespace(id=term_id, name=AcademicTermName.FIRST_TERM)
    db = SimpleNamespace(execute=AsyncMock(return_value=_scalars([classroom])))

    with patch(
        f"{SERVICE}.AcademicLevelRepository.list_for_tenant",
        new=AsyncMock(return_value=[level]),
    ):
        counts, blockers = await AcademicCurriculumService.specialization_readiness(
            db,
            tenant_id=tenant_id,
            term=term,
        )

    assert counts == {
        "active_academic_levels": 1,
        "active_classes": 1,
        "classes_on_inactive_levels": 0,
        "classes_missing_department": 0,
    }
    assert blockers == []


@pytest.mark.asyncio
async def test_term_readiness_requires_valid_active_exact_term_specialization() -> None:
    tenant_id, term_id, level_id, class_id = uuid4(), uuid4(), uuid4(), uuid4()
    level = SimpleNamespace(
        id=level_id,
        name="SS1",
        status=AcademicLevelStatus.ACTIVE,
        specialization_required_from_term_position=1,
    )
    classroom = SimpleNamespace(id=class_id, academic_level_id=level_id)
    term = SimpleNamespace(id=term_id, name=AcademicTermName.FIRST_TERM)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalars([classroom]),
                _rows([]),
            ]
        )
    )

    with patch(
        f"{SERVICE}.AcademicLevelRepository.list_for_tenant",
        new=AsyncMock(return_value=[level]),
    ):
        counts, blockers = await AcademicCurriculumService.specialization_readiness(
            db,
            tenant_id=tenant_id,
            term=term,
        )

    assert counts["classes_missing_department"] == 1
    assert any("valid active department specialization" in message for message in blockers)


@pytest.mark.asyncio
async def test_level_department_validation_batches_many_ids_into_one_query() -> None:
    tenant_id, level_id = uuid4(), uuid4()
    ids = [uuid4() for _ in range(40)]
    rows = [
        (
            SimpleNamespace(
                id=link_id,
                academic_level_id=level_id,
                is_active=True,
                archived_at=None,
            ),
            SimpleNamespace(is_active=True, archived_at=None),
        )
        for link_id in ids
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=_rows(rows)))

    with patch(
        f"{SERVICE}.AcademicCurriculumService._ensure_department_capability",
        new=AsyncMock(),
    ):
        resolved = await AcademicCurriculumService._validated_level_department_ids(
            db,
            tenant_id=tenant_id,
            academic_level_id=level_id,
            ids=ids,
        )

    assert [row.id for row in resolved] == ids
    assert db.execute.await_count == 1


@pytest.mark.asyncio
async def test_class_department_list_hydrates_many_rows_with_two_queries() -> None:
    tenant_id, term_id, link_id, department_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)
    assignments = [
        SimpleNamespace(
            id=uuid4(),
            tenant_id=tenant_id,
            class_id=uuid4(),
            academic_term_id=term_id,
            academic_level_department_id=link_id,
            assigned_by_admin_id=uuid4(),
            created_at=now,
            updated_at=now,
        )
        for _ in range(50)
    ]
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalars(assignments),
                _rows([(link_id, department_id, "Science")]),
            ]
        )
    )

    with patch(
        f"{SERVICE}.AcademicCurriculumService._term",
        new=AsyncMock(return_value=SimpleNamespace(id=term_id)),
    ):
        result = await AcademicCurriculumService.list_class_departments(
            db,
            tenant_id,
            term_id,
        )

    assert len(result) == 50
    assert all(item.department_name == "Science" for item in result)
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_teacher_subject_availability_resolves_all_classes_once() -> None:
    tenant_id, level_id, term_id, curriculum_id = uuid4(), uuid4(), uuid4(), uuid4()
    subject_id = uuid4()
    classes = [SimpleNamespace(id=uuid4()) for _ in range(60)]
    resolved = {
        classroom.id: [
            ResolvedCurriculumSubject(
                curriculum_subject_id=subject_id,
                subject_id=uuid4(),
                academic_level_department_id=None,
                is_elective=False,
                is_general=True,
            )
        ]
        for classroom in classes
    }
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _scalars([subject_id]),
                _scalars(classes),
                _rows([]),
            ]
        )
    )

    with (
        patch(
            f"{SERVICE}.AcademicCurriculumService._curriculum",
            new=AsyncMock(return_value=SimpleNamespace(id=curriculum_id)),
        ),
        patch(
            f"{SERVICE}.CurriculumResolutionService.resolve_classes_subjects",
            new=AsyncMock(return_value=resolved),
        ) as bulk_resolve,
    ):
        result = await AcademicCurriculumService.teacher_assignment_subject_availability(
            db,
            tenant_id=tenant_id,
            academic_level_id=level_id,
            academic_term_id=term_id,
        )

    bulk_resolve.assert_awaited_once()
    assert result[0].eligible_class_count == 60
    assert result[0].unassigned_class_count == 60
    assert db.execute.await_count == 3
