from app.main import app
from app.modules.search import service as search_service_module


def _collect_api_paths() -> set[str]:
    paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
    return paths


def test_student_and_parent_workspace_search_routes_are_removed() -> None:
    paths = _collect_api_paths()

    assert "/api/v1/students/me/search" not in paths
    assert "/api/v1/parents/me/search" not in paths


def test_teacher_and_admin_workspace_search_routes_remain() -> None:
    paths = _collect_api_paths()

    assert "/api/v1/teachers/me/search" in paths
    assert "/api/v1/tenant-admin/search" in paths
    assert "/api/v1/superadmin/search" in paths


def test_search_service_does_not_expose_student_or_parent_scopes() -> None:
    assert not hasattr(search_service_module.TenantSearchService, "search_student")
    assert not hasattr(search_service_module.TenantSearchService, "search_parent")
