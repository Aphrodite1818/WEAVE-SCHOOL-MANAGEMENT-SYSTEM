from fastapi.routing import APIRoute
from pydantic import ValidationError
import pytest

from app.modules.classes.departments_router import router
from app.modules.classes.schemas import (
    DepartmentActivateRequest,
    DepartmentArchiveRequest,
    DepartmentDeactivateRequest,
    DepartmentRestoreRequest,
)


def test_department_lifecycle_routes_are_exposed() -> None:
    routes = {
        (route.path, method)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    pool = "/tenant-admin/academics/departments/{department_id}"
    assert (f"{pool}/activate", "POST") in routes
    assert (f"{pool}/deactivate", "POST") in routes
    assert (f"{pool}/archive", "POST") in routes
    assert (f"{pool}/restore", "POST") in routes
    assert (pool, "PATCH") in routes

    mapping = "/tenant-admin/academics/academic-levels/{academic_level_id}/departments/{link_id}"
    assert (f"{mapping}/activate", "POST") in routes
    assert (f"{mapping}/deactivate", "POST") in routes
    assert (f"{mapping}/archive", "POST") in routes
    assert (f"{mapping}/restore", "POST") in routes
    assert (mapping, "DELETE") in routes


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
