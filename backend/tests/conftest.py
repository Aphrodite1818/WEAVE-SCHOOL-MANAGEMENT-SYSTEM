"""Pytest bootstrap for shared fixtures."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.models  # noqa: F401


def pytest_configure(config) -> None:
    """Register shared fixtures when backend is pytest's configured root."""
    for plugin in (
        "tests.fixtures.database",
        "tests.fixtures.auth",
        "tests.fixtures.tenants",
        "tests.fixtures.users",
        "tests.fixtures.teachers",
        "tests.fixtures.subjects",
    ):
        config.pluginmanager.import_plugin(plugin)
