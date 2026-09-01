from fastapi.routing import APIRoute
from pydantic import ValidationError
import pytest
import uuid
from types import SimpleNamespace

from app.core.exceptions import NotFoundException
from app.modules.classes.departments_router import router
from app.modules.classes.schemas import (
    DepartmentActivateRequest,
    DepartmentArchiveRequest,
    DepartmentDeactivateRequest,
    DepartmentRestoreRequest,
)
from app.modules.classes.service import DepartmentService


def test_department_lifecycle_routes_are_exposed() -> None:
    routes = {
        (route.path, method)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    prefix = "/academic-levels/{academic_level_id}/departments/{department_id}"
    assert (f"{prefix}/activate", "POST") in routes
    assert (f"{prefix}/deactivate", "POST") in routes
    assert (f"{prefix}/archive", "POST") in routes
    assert (f"{prefix}/restore", "POST") in routes
    assert (prefix, "PATCH") in routes


@pytest.mark.parametrize(
    ("schema", "confirmation"),
    [
        (DepartmentActivateRequest, "ACTIVATE_DEPARTMENT"),
        (DepartmentDeactivateRequest, "DEACTIVATE_DEPARTMENT"),
        (DepartmentArchiveRequest, "ARCHIVE_DEPARTMENT"),
        (DepartmentRestoreRequest, "RESTORE_DEPARTMENT"),
    ],
)
def test_department_lifecycle_requires_typed_confirmation(schema, confirmation) -> None:
    assert schema(confirmation=confirmation).confirmation == confirmation
    with pytest.raises(ValidationError):
        schema(confirmation="CONFIRM")


def test_department_lifecycle_hides_records_from_a_different_level() -> None:
    department = SimpleNamespace(academic_level_id=uuid.uuid4())

    with pytest.raises(NotFoundException, match="Department not found"):
        DepartmentService._ensure_level_scope(department, uuid.uuid4())
