"""Backend-wide import integrity checks.

This test deliberately imports every module under ``app``. It catches stale
router dependencies, removed schema names, legacy module paths, and circular
imports before Uvicorn startup or deployment.
"""

from __future__ import annotations

import importlib
import pkgutil

import app


def test_every_backend_module_imports() -> None:
    failures: list[str] = []

    module_names = sorted(
        module_info.name
        for module_info in pkgutil.walk_packages(
            app.__path__,
            prefix=f"{app.__name__}.",
        )
    )

    for module_name in module_names:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 - aggregate every import failure
            failures.append(
                f"{module_name}: {type(exc).__name__}: {exc}"
            )

    assert not failures, "Backend import failures:\n" + "\n".join(failures)
