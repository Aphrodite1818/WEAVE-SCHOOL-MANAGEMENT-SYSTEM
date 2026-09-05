"""Import-contract smoke tests for the placement/report-card cutover.

These deliberately import the canonical modules used by app startup and pytest
collection. They catch stale references to removed pre-launch compatibility
modules before a request reaches the API.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest


CANONICAL_MODULES = (
    "app.models",
    "app.modules.students.enrollment_schemas",
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
