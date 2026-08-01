"""Pytest bootstrap for shared fixtures."""

from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app.models  # noqa: F401

# Keep plugin registration explicit so CI loads the shared fixtures in a stable order.
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.auth",
    "tests.fixtures.tenants",
    "tests.fixtures.users",
    "tests.fixtures.teachers",
    "tests.fixtures.subjects",
]
