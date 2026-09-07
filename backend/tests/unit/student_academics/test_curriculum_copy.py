from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics import curriculum_copy_service as service
from app.modules.student_academics.curriculum_models import (
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.curriculum_v2_schemas import CurriculumCopyRequest


@pytest.fixture
def context(monkeypatch):
    tenant, source_id, target_id = uuid4(), uuid4(), uuid4()
    levels = {
        key: SimpleNamespace(id=key, category="PRIMARY", status="active")
        for key in [source_id, target_id]
    }
    curricula = {key: SimpleNamespace(id=uuid4()) for key in levels}
    rows = [
        SimpleNamespace(id=uuid4(), subject_id=uuid4(), is_active=True, is_elective=elective)
        for elective in [False, True]
    ]
    subjects = [SimpleNamespace(is_active=True, archived_at=None) for _ in rows]
    results = [MagicMock() for _ in range(3)]
    results[0].all.return_value = list(zip(rows, subjects))
    results[1].scalars.return_value = []
    results[2].all.return_value = []
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=results),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    guard = AsyncMock()
    load = AsyncMock(side_effect=lambda db, tenant_id, level_id, **kw: levels.get(level_id))
    monkeypatch.setattr(service, "ensure_academic_write_window", guard)
    monkeypatch.setattr(service.AcademicLevelRepository, "get_by_id", load)
    monkeypatch.setattr(
        service.AcademicCurriculumService,
        "_curriculum",
        AsyncMock(side_effect=lambda db, tenant_id, level_id: curricula[level_id]),
    )
    validate = AsyncMock()
    monkeypatch.setattr(
        service.AcademicCurriculumService, "_validated_level_department_ids", validate
    )
    target_link = SimpleNamespace(id=uuid4())
    map_department = AsyncMock(return_value=target_link)
    monkeypatch.setattr(
        service.AcademicLevelDepartmentRepository, "get_for_level_department", map_department
    )
    return SimpleNamespace(**locals())


async def copy(ctx):
    return await service.copy_curriculum(ctx.db, ctx.tenant, ctx.target_id, ctx.source_id)


@pytest.mark.asyncio
async def test_copy_preserves_semantics_and_remaps_department_identity(context):
    c = context
    department_id = uuid4()
    c.results[2].all.return_value = [
        (
            SimpleNamespace(curriculum_subject_id=c.rows[1].id),
            SimpleNamespace(department_id=department_id, academic_level_id=c.source_id),
        )
    ]
    assert await copy(c) == {"created": 2, "skipped_existing": 0, "skipped_inactive": 0}
    added = [call.args[0] for call in c.db.add.call_args_list]
    memberships = [row for row in added if isinstance(row, CurriculumSubject)]
    scopes = [row for row in added if isinstance(row, CurriculumSubjectDepartment)]
    assert [row.is_elective for row in memberships] == [False, True]
    assert all(row.curriculum_id == c.curricula[c.target_id].id for row in memberships)
    assert all(row.tenant_id == c.tenant for row in added)
    assert scopes[0].academic_level_department_id == c.target_link.id
    assert scopes[0].curriculum_subject_id == memberships[1].id
    c.map_department.assert_awaited_once_with(c.db, c.tenant, c.target_id, department_id, lock=True)
    c.validate.assert_awaited_once_with(
        c.db, tenant_id=c.tenant, academic_level_id=c.target_id, ids=[c.target_link.id]
    )
    c.db.commit.assert_awaited_once()
    c.db.rollback.assert_not_awaited()
    c.guard.assert_awaited_once_with(c.db, tenant_id=c.tenant)
    for call in c.load.call_args_list:
        assert call.args[1] == c.tenant
        assert call.kwargs["lock"] is True
    for call in c.db.execute.call_args_list:
        assert c.tenant in call.args[0].compile().params.values()


@pytest.mark.asyncio
async def test_existing_memberships_are_untouched_and_repeated_copy_is_a_noop(context):
    c = context
    c.results[1].scalars.return_value = [row.subject_id for row in c.rows]
    assert await copy(c) == {"created": 0, "skipped_existing": 2, "skipped_inactive": 0}
    c.db.add.assert_not_called()
    c.validate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("inactive", ["membership", "subject", "archived"])
async def test_inactive_source_records_are_explicitly_counted(context, inactive):
    c = context
    if inactive == "membership":
        c.rows[0].is_active = False
    elif inactive == "subject":
        c.subjects[0].is_active = False
    else:
        c.subjects[0].archived_at = "archived"
    assert await copy(c) == {"created": 1, "skipped_existing": 0, "skipped_inactive": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "same_level",
        "category",
        "source_missing",
        "target_missing",
        "source_inactive",
        "target_inactive",
        "empty",
        "missing_department",
        "invalid_department",
        "wrong_source_scope",
        "write_window",
        "integrity",
    ],
)
async def test_copy_rejects_invalid_context_and_rolls_back_everything(context, failure):
    c = context
    if failure == "same_level":
        c.source_id = c.target_id
    elif failure == "category":
        c.levels[c.source_id].category = "SENIOR_SECONDARY"
    elif failure.endswith("missing"):
        c.levels.pop(c.source_id if failure.startswith("source") else c.target_id)
    elif failure.endswith("inactive"):
        c.levels[c.source_id if failure.startswith("source") else c.target_id].status = "inactive"
    elif failure == "empty":
        c.results[0].all.return_value = []
    elif failure in ["missing_department", "invalid_department", "wrong_source_scope"]:
        c.results[2].all.return_value = [
            (
                SimpleNamespace(curriculum_subject_id=c.rows[0].id),
                SimpleNamespace(
                    department_id=uuid4(),
                    academic_level_id=uuid4() if failure == "wrong_source_scope" else c.source_id,
                ),
            )
        ]
        if failure == "missing_department":
            c.map_department.return_value = None
        elif failure == "invalid_department":
            c.validate.side_effect = ConflictException(
                "Every selected level department must be active."
            )
    elif failure == "write_window":
        c.guard.side_effect = ConflictException("Write window closed")
    elif failure == "integrity":
        c.db.flush.side_effect = [None, IntegrityError("insert", {}, Exception("duplicate"))]
    with pytest.raises((ConflictException, NotFoundException)):
        await copy(c)
    c.db.commit.assert_not_awaited()
    c.db.rollback.assert_awaited_once()
    if failure != "integrity":
        c.db.add.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"source_academic_level_id": "invalid"},
        {"source_academic_level_id": str(uuid4()), "tenant_id": str(uuid4())},
    ],
)
def test_copy_request_rejects_invalid_input_and_client_tenant_override(payload):
    with pytest.raises(ValidationError):
        CurriculumCopyRequest(**payload)


def test_copy_route_requires_authenticated_tenant_admin():
    from app.core.dependencies.route_guards import get_current_tenant_admin
    from app.modules.student_academics.curriculum_router import router

    route = next(route for route in router.routes if route.path.endswith("/curriculum/copy"))
    assert "POST" in route.methods
    assert any(
        dependency.call is get_current_tenant_admin for dependency in route.dependant.dependencies
    )
