from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.auth_identity.models import ActorType
from app.modules.bulk_imports.optimized_validation import (
    preflight_student_parent_invitations_batch,
    resolve_student_class_references_batch,
)
from app.modules.bulk_imports.validators import ImportRowValidationResult
from app.modules.classes.models import AcademicLevelStatus
from app.modules.student_academics.assessment_repository import AssessmentRepository
from app.modules.student_academics.repository import StudentAcademicRepository


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


@pytest.mark.asyncio
async def test_bulk_class_resolution_batches_repeated_references(monkeypatch) -> None:
    tenant_id = uuid4()
    level_id = uuid4()
    arm_id = uuid4()
    class_id = uuid4()
    level = SimpleNamespace(
        id=level_id,
        name="JSS1",
        normalized_name="jss1",
        status=AcademicLevelStatus.ACTIVE,
    )
    arm = SimpleNamespace(
        id=arm_id,
        label="A",
        normalized_label="a",
        is_active=True,
        archived_at=None,
    )
    classroom = SimpleNamespace(
        id=class_id,
        academic_level_id=level_id,
        arm_label_id=arm_id,
        is_active=True,
        archived_at=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult([level]),
                _ScalarResult([arm]),
                _ScalarResult([classroom]),
            ]
        )
    )
    monkeypatch.setattr(
        StudentAcademicRepository,
        "get_current_term",
        AsyncMock(return_value=None),
    )
    rows = [
        ImportRowValidationResult(
            row_number=index,
            raw_row={},
            normalized_row={"level": "JSS1", "arm": "A", "department": None},
        )
        for index in (2, 3, 4)
    ]

    await resolve_student_class_references_batch(
        db,
        tenant_id=tenant_id,
        validation_results=rows,
    )

    assert db.execute.await_count == 3
    assert all(row.errors == [] for row in rows)
    assert all(row.normalized_row["class_id"] == str(class_id) for row in rows)


@pytest.mark.asyncio
async def test_parent_preflight_uses_three_queries_for_many_emails() -> None:
    parent = SimpleNamespace(email="parent@example.com")
    identity = SimpleNamespace(
        identifier="parent@example.com",
        actor_type=ActorType.PARENT_ACCOUNT,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _ScalarResult([]),
                _ScalarResult([identity]),
                _ScalarResult([parent]),
            ]
        )
    )
    rows = [
        ImportRowValidationResult(
            row_number=index,
            raw_row={},
            normalized_row={
                "parent_email_1": "parent@example.com",
                "parent_email_2": f"other{index}@example.com",
            },
        )
        for index in range(2, 12)
    ]

    summary = await preflight_student_parent_invitations_batch(
        db,
        validation_results=rows,
    )

    assert db.execute.await_count == 3
    assert summary["parent_emails_supplied"] == 20
    assert summary["existing_parent_accounts"] == 1
    assert all(row.errors == [] for row in rows)


@pytest.mark.asyncio
async def test_assessment_components_for_many_schemes_use_one_query() -> None:
    scheme_a = uuid4()
    scheme_b = uuid4()
    components = [
        SimpleNamespace(assessment_scheme_id=scheme_a),
        SimpleNamespace(assessment_scheme_id=scheme_a),
        SimpleNamespace(assessment_scheme_id=scheme_b),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(components)))

    grouped = await AssessmentRepository.list_components_for_schemes(
        db,
        uuid4(),
        {scheme_a, scheme_b},
    )

    assert db.execute.await_count == 1
    assert len(grouped[scheme_a]) == 2
    assert len(grouped[scheme_b]) == 1