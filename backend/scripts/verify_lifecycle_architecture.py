"""Executable architecture verification for the lifecycle refactor."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from sqlalchemy.orm import configure_mappers

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models as _model_registry  # noqa: E402,F401
from app.main import app as fastapi_app  # noqa: E402
from app.modules.parents.models import Parent, ParentMembership  # noqa: E402
from app.modules.teachers.models import Teacher, TeacherMembership  # noqa: E402
from app.shared.base_model import Base  # noqa: E402


def verify_mappers_and_foreign_keys() -> None:
    configure_mappers()

    table_names = set(Base.metadata.tables)
    forbidden_tables = {
        "public.teachers",
        "teachers",
        "public.parents",
        "parents",
        "public.legacy_teachers",
        "legacy_teachers",
    }
    unexpected = table_names.intersection(forbidden_tables)
    if unexpected:
        raise AssertionError(f"Legacy actor tables remain mapped: {sorted(unexpected)}")

    for table in Base.metadata.sorted_tables:
        for foreign_key in table.foreign_keys:
            try:
                _ = foreign_key.column
            except Exception as exc:  # pragma: no cover - diagnostic boundary
                raise AssertionError(
                    f"Unresolved foreign key {table.fullname}.{foreign_key.parent.name}: "
                    f"{foreign_key.target_fullname}"
                ) from exc


def verify_actor_aliases() -> None:
    if Parent is not ParentMembership:
        raise AssertionError("Parent tenant actor must be ParentMembership")
    if Teacher is not TeacherMembership:
        raise AssertionError("Teacher tenant actor must be TeacherMembership")


def verify_routes() -> None:
    route_keys: list[tuple[str, str]] = []
    for route in fastapi_app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        if path is None:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            route_keys.append((method, path))

    duplicates = [route_key for route_key, count in Counter(route_keys).items() if count > 1]
    if duplicates:
        raise AssertionError(f"Duplicate method/path registrations detected: {duplicates}")


def main() -> None:
    verify_actor_aliases()
    verify_mappers_and_foreign_keys()
    verify_routes()
    print("Lifecycle architecture verification passed.")


if __name__ == "__main__":
    main()
