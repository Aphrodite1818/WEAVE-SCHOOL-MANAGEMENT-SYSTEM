"""Import-contract smoke tests for the placement/report-card cutover.

These deliberately import the canonical modules used by app startup and pytest
collection. They catch stale references to removed pre-launch compatibility
modules before a request reaches the API.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest


CANONICAL_MODULES = (
    "app.models",
    "app.modules.students.enrollment_schemas",
    "app.modules.students.enrollment_evidence",
    "app.modules.students.lifecycle_service",
    "app.modules.students.placement_service",
    "app.modules.students.placement_router",
    "app.modules.students.academic_context_router",
    "app.modules.tenant_admins.router",
    "app.modules.student_academics.service",
    "app.modules.report_cards.comment_models",
    "app.modules.report_cards.comment_schemas",
    "app.modules.report_cards.comment_service",
    "app.modules.report_cards.comment_router",
    "app.modules.report_cards.principal_comment_policy",
    "app.modules.report_cards.ranking_policy",
    "app.modules.report_cards.repository",
    "app.modules.report_cards.service",
    "app.modules.report_cards.model_events",
    "app.modules.report_cards.fixed_router",
    "app.modules.report_cards.router",
    "app.modules.report_cards.bulk_service",
    "app.modules.report_cards.bulk_router",
    "app.modules.cbt.sync.projectors.students",
    "app.modules.cbt.sync.projectors.curriculum",
    "app.modules.cbt.sync.projectors.bootstrap",
    "app.main",
)

REMOVED_BACKEND_REFERENCES = (
    "app.modules.students.enrollment_service",
    "app.modules.report_cards.generation_service",
    "StudentBatchClassAssignmentRequest",
    "StudentClassChangeRequest",
    "EnrollmentReportCardService",
    "ReportCardCommentsUpdate",
)

REMOVED_TEST_IMPORTS = (
    "from app.modules.students.enrollment_service",
    "import app.modules.students.enrollment_service",
    "from app.modules.report_cards.generation_service",
    "import app.modules.report_cards.generation_service",
    "ReportCardCommentsUpdate",
)


@pytest.mark.parametrize("module_name", CANONICAL_MODULES)
def test_canonical_academic_modules_import(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


def test_removed_placement_and_report_generation_modules_stay_removed() -> None:
    assert importlib.util.find_spec("app.modules.students.enrollment_service") is None
    assert importlib.util.find_spec("app.modules.report_cards.generation_service") is None


def test_removed_placement_request_symbols_are_not_reintroduced() -> None:
    schemas = importlib.import_module("app.modules.students.enrollment_schemas")

    assert not hasattr(schemas, "StudentBatchClassAssignmentRequest")
    assert not hasattr(schemas, "StudentClassChangeRequest")
    assert hasattr(schemas, "StudentClassPlacementRequest")
    assert hasattr(schemas, "StudentClassReassignmentRequest")
    assert hasattr(schemas, "StudentAcademicLevelReassignmentRequest")


def test_removed_report_card_comment_patch_schema_stays_removed() -> None:
    schemas = importlib.import_module("app.modules.report_cards.schemas")

    assert not hasattr(schemas, "ReportCardCommentsUpdate")
    assert hasattr(schemas, "ReportCardPrincipalCommentUpdate")


def test_backend_app_has_no_stale_placement_or_report_generation_references() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    app_root = backend_root / "app"
    offenders: list[str] = []

    for path in app_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for removed in REMOVED_BACKEND_REFERENCES:
            if removed in source:
                offenders.append(f"{path.relative_to(backend_root)} -> {removed}")

    assert offenders == [], "Stale academic imports/contracts remain:\n" + "\n".join(offenders)


def test_backend_tests_have_no_imports_from_removed_academic_modules() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    tests_root = backend_root / "tests"
    guard_path = Path(__file__).resolve()
    offenders: list[str] = []

    for path in tests_root.rglob("*.py"):
        if path.resolve() == guard_path:
            continue
        source = path.read_text(encoding="utf-8")
        for removed_import in REMOVED_TEST_IMPORTS:
            if removed_import in source:
                offenders.append(
                    f"{path.relative_to(backend_root)} -> {removed_import}"
                )

    assert offenders == [], "Tests still import removed academic modules:\n" + "\n".join(offenders)
