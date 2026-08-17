"""Stable CBT projections for assessment schemes and components."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import (
    CBTAssessmentComponentSnapshot,
    CBTAssessmentSchemeSnapshot,
)
from app.modules.student_academics.models import AssessmentComponent, AssessmentScheme


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def project_assessment_scheme(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(AssessmentScheme).where(
            AssessmentScheme.tenant_id == tenant_id,
            AssessmentScheme.id == entity_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return CBTAssessmentSchemeSnapshot(
        id=row.id,
        name=row.name,
        status=_value(row.status),
    ).model_dump(mode="json")


def project_assessment_component(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(AssessmentComponent).where(
            AssessmentComponent.tenant_id == tenant_id,
            AssessmentComponent.id == entity_id,
        )
    ).scalar_one_or_none()
    if row is None or not row.is_active:
        return None
    return CBTAssessmentComponentSnapshot(
        id=row.id,
        assessment_scheme_id=row.assessment_scheme_id,
        name=row.name,
        code=row.code,
        maximum_score=row.maximum_score,
        position=row.position,
        is_active=row.is_active,
    ).model_dump(mode="json")
