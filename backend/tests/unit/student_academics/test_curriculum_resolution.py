from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.student_academics.curriculum_service import (
    CurriculumResolutionService,
    ResolvedCurriculumOffering,
)
from app.modules.student_academics.models import AcademicTermName
from app.modules.student_academics.service import StudentAcademicService
from app.modules.classes.repository import AcademicLevelRepository


class Result:
    def __init__(self, *, rows=(), scalars=()):
        self._rows = list(rows)
        self._scalars = list(scalars)

    def all(self):
        return self._rows

    def scalars(self):
        return self._scalars


@pytest.mark.asyncio
async def test_department_offering_overrides_common_offering_for_same_subject():
    tenant_id = uuid4()
    level_id = uuid4()
    term_id = uuid4()
    department_id = uuid4()
    level_subject = SimpleNamespace(id=uuid4(), subject_id=uuid4())
    common = SimpleNamespace(department_id=None, is_elective=False)
    specialized = SimpleNamespace(department_id=department_id, is_elective=False)
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=Result(rows=[(common, level_subject), (specialized, level_subject)])
        )
    )

    resolved = await CurriculumResolutionService.resolve_curriculum_offerings(
        db,
        tenant_id=tenant_id,
        academic_level_id=level_id,
        academic_term_id=term_id,
        department_id=department_id,
    )

    assert len(resolved) == 1
    assert resolved[0].department_id == department_id
    statement = str(db.execute.await_args.args[0])
    assert "subject_offerings.tenant_id" in statement
    assert "level_subjects.tenant_id" in statement


@pytest.mark.asyncio
@pytest.mark.parametrize("participating", [False, True])
async def test_elective_requires_a_meaningful_assessment_score(monkeypatch, participating):
    normal = ResolvedCurriculumOffering(uuid4(), uuid4(), uuid4(), None, False)
    elective = ResolvedCurriculumOffering(uuid4(), uuid4(), normal.academic_term_id, None, True)
    monkeypatch.setattr(
        CurriculumResolutionService,
        "resolve_student_offerings",
        AsyncMock(return_value=[normal, elective]),
    )
    scalar_rows = [elective.level_subject_id] if participating else []
    db = SimpleNamespace(execute=AsyncMock(return_value=Result(scalars=scalar_rows)))

    resolved = await CurriculumResolutionService.resolve_student_curriculum(
        db,
        tenant_id=uuid4(),
        student_id=uuid4(),
        academic_term_id=normal.academic_term_id,
    )

    assert normal in resolved
    assert (elective in resolved) is participating
    assert "student_assessment_scores" in str(db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_specialization_blocks_only_when_next_term_requires_it(monkeypatch):
    tenant_id = uuid4()
    session_id = uuid4()
    level_id = uuid4()
    current = SimpleNamespace(
        academic_session_id=session_id,
        name=AcademicTermName.FIRST_TERM,
    )
    next_term = SimpleNamespace(
        academic_session_id=session_id,
        name=AcademicTermName.SECOND_TERM,
    )
    enrollment = SimpleNamespace(
        id=uuid4(),
        academic_level_id=level_id,
        class_id=None,
    )
    level = SimpleNamespace(
        id=level_id,
        name="Custom Foundation Stage",
        specialization_required_from_term_position=2,
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "list_for_tenant",
        AsyncMock(return_value=[level]),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                Result(scalars=[current, next_term]),
                Result(scalars=[enrollment]),
                Result(rows=[]),
            ]
        )
    )

    counts, blockers = await StudentAcademicService._specialization_blockers_for_next_term(
        db,
        tenant_id=tenant_id,
        term=current,
    )

    assert counts == {"students_missing_department": 1}
    assert blockers == [
        "1 Custom Foundation Stage students require department assignment before Second Term."
    ]


@pytest.mark.asyncio
async def test_effective_department_assignment_allows_classless_student(monkeypatch):
    tenant_id = uuid4()
    session_id = uuid4()
    level_id = uuid4()
    current = SimpleNamespace(academic_session_id=session_id, name=AcademicTermName.FIRST_TERM)
    next_term = SimpleNamespace(academic_session_id=session_id, name=AcademicTermName.SECOND_TERM)
    enrollment = SimpleNamespace(id=uuid4(), academic_level_id=level_id, class_id=None)
    assignment = SimpleNamespace(student_enrollment_id=enrollment.id)
    level = SimpleNamespace(
        id=level_id,
        name="Stage Alpha",
        specialization_required_from_term_position=2,
    )
    monkeypatch.setattr(
        AcademicLevelRepository,
        "list_for_tenant",
        AsyncMock(return_value=[level]),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                Result(scalars=[current, next_term]),
                Result(scalars=[enrollment]),
                Result(rows=[(assignment, next_term)]),
            ]
        )
    )

    counts, blockers = await StudentAcademicService._specialization_blockers_for_next_term(
        db,
        tenant_id=tenant_id,
        term=current,
    )

    assert counts == {"students_missing_department": 0}
    assert blockers == []
