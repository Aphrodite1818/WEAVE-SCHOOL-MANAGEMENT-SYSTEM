"""Assessment-component examinability ORM extension.

This module adds the examinability flag to the canonical AssessmentComponent
mapper without changing the public CBT snapshot contract. Existing components
default to examinable so deployments preserve their historical behaviour until
an administrator explicitly marks a component as manual/non-examinable.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean
from sqlalchemy.orm import mapped_column

from app.modules.student_academics.models import AssessmentComponent


if "is_examinable" not in AssessmentComponent.__table__.c:
    # DeclarativeBase supports adding mapped columns to an already-declared
    # class. Keeping this extension isolated also makes the migration contract
    # explicit while the rest of the academic model remains unchanged.
    setattr(
        AssessmentComponent,
        "is_examinable",
        mapped_column(Boolean, nullable=False, default=True, server_default="true"),
    )


def is_assessment_component_examinable(component: Any) -> bool:
    """Return whether a component belongs to the CBT/exam workflow.

    The helper deliberately hides the dynamically-installed ORM attribute from
    callers so static type checking does not need to know how the mapper was
    extended. The fallback preserves pre-migration semantics for test doubles.
    """

    return bool(getattr(component, "is_examinable", True))
