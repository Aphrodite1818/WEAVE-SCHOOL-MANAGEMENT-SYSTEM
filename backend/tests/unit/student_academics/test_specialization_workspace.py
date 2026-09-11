from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.modules.student_academics.specialization_workspace import specialization_workspace


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "required,assigned,expected",
    [(False, False, "not_required"), (True, False, "missing"), (True, True, "configured")],
)
async def test_workspace_uses_exact_term_tenant_and_authoritative_resolver(
    required, assigned, expected
):
    tenant_id, term_id, class_id, level_id, link_id = [uuid4() for _ in range(5)]
    term = SimpleNamespace(id=term_id, status="draft")
    level = SimpleNamespace(id=level_id, name="SS1")
    classes = MagicMock()
    classes.all.return_value = [(SimpleNamespace(id=class_id), level, SimpleNamespace(label="A"))]
    assignments = MagicMock()
    assignments.all.return_value = (
        [
            (
                SimpleNamespace(class_id=class_id, academic_level_department_id=link_id),
                SimpleNamespace(name="Science"),
            )
        ]
        if assigned
        else []
    )
    db = SimpleNamespace(execute=AsyncMock(side_effect=[classes, assignments]))
    with (
        patch(
            "app.modules.student_academics.specialization_workspace.AcademicCurriculumService._term",
            new=AsyncMock(return_value=term),
        ) as load,
        patch(
            "app.modules.student_academics.specialization_workspace.CurriculumResolutionService.specialization_is_active",
            return_value=required,
        ) as resolve,
    ):
        result = await specialization_workspace(db, tenant_id, term_id)
    load.assert_awaited_once_with(db, tenant_id, term_id)
    resolve.assert_called_once_with(level, term)
    assert result["classes"][0]["readiness"] == expected
    assert result["classes"][0]["department_name"] == ("Science" if assigned else None)
    assert result["academic_term_id"] == term_id
    assert db.execute.await_count == 2
    query = db.execute.call_args_list[1].args[0]
    compiled = query.compile()
    assert term_id in compiled.params.values()
    assert list(compiled.params.values()).count(tenant_id) == 3
    assert "academic_term_id =" in str(compiled)


def test_new_routes_keep_tenant_admin_authorization_and_typed_responses():
    from app.core.dependencies.route_guards import get_current_tenant_admin
    from app.modules.student_academics.curriculum_router import router

    routes = [
        route
        for route in router.routes
        if route.path.endswith(("/setup-readiness", "/specialization-workspace", "/subjects/bulk"))
    ]
    assert len(routes) == 3
    for route in routes:
        assert route.response_model is not None
        assert any(
            dependency.call is get_current_tenant_admin
            for dependency in route.dependant.dependencies
        )
