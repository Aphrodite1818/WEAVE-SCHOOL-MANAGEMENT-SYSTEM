"""Pytest bootstrap for repository-wide plugin registration."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.models  # noqa: F401

pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.auth",
    "tests.fixtures.tenants",
    "tests.fixtures.users",
    "tests.fixtures.teachers",
    "tests.fixtures.subjects",
]
