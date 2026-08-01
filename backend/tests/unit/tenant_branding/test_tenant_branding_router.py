from app.main import app


def _collect_api_paths() -> set[str]:
    return {
        path
        for route in app.routes
        if (path := getattr(route, "path", None))
    }


def test_tenant_branding_routes_are_registered() -> None:
    paths = _collect_api_paths()

    assert "/api/v1/tenant-admin/branding" in paths
    assert "/api/v1/tenant-admin/branding/effective" in paths
    assert "/api/v1/tenant-admin/branding/enable" in paths
    assert "/api/v1/tenant-admin/branding/disable" in paths
    assert "/api/v1/tenant-admin/branding/reset" in paths
    assert "/api/v1/workspace/branding" in paths
