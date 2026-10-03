from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

import app.modules.student_academics.assessment_examinability  # noqa: F401
from app.modules.cbt.sync.projectors.assessments import project_assessment_component
from app.modules.student_academics.assessment_schemas import (
    AssessmentComponentCreate,
    AssessmentComponentResponse,
    AssessmentComponentUpdate,
)
from app.modules.student_academics.models import AssessmentSchemeStatus


class _ExecuteResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _Session:
    def __init__(self, row):
        self.row = row

    def execute(self, _statement):
        return _ExecuteResult(self.row)


def _component(*, is_examinable: bool):
    return SimpleNamespace(
        id=uuid4(),
        assessment_scheme_id=uuid4(),
        name="Exam",
        code="EX",
        maximum_score=Decimal("60"),
        position=0,
        is_active=True,
        is_examinable=is_examinable,
    )


def test_component_create_defaults_to_examinable_for_backward_compatibility() -> None:
    payload = AssessmentComponentCreate(
        name="Exam",
        code="EX",
        maximum_score=Decimal("60"),
        position=0,
    )
    assert payload.is_examinable is True


def test_component_response_exposes_examinability() -> None:
    component = _component(is_examinable=False)
    response = AssessmentComponentResponse.model_validate(component)
    assert response.is_examinable is False


def test_component_update_rejects_explicit_null_examinability() -> None:
    with pytest.raises(ValidationError, match="is_examinable cannot be null"):
        AssessmentComponentUpdate(is_examinable=None)


def test_non_examinable_component_is_not_projected_to_cbt() -> None:
    component = _component(is_examinable=False)
    scheme = SimpleNamespace(status=AssessmentSchemeStatus.ACTIVE)

    assert (
        project_assessment_component(
            _Session((component, scheme)),
            uuid4(),
            component.id,
        )
        is None
    )


def test_examinable_component_projection_keeps_existing_cbt_contract() -> None:
    component = _component(is_examinable=True)
    scheme = SimpleNamespace(status=AssessmentSchemeStatus.ACTIVE)

    payload = project_assessment_component(
        _Session((component, scheme)),
        uuid4(),
        component.id,
    )

    assert payload is not None
    assert payload["id"] == str(component.id)
    assert payload["maximum_score"] == "60"
    assert "is_examinable" not in payload
