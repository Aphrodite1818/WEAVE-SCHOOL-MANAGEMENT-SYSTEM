"""Stable CBT projections for teachers and curriculum-subject assignments."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import CBTTeacherAssignmentSnapshot, CBTTeacherSnapshot
from app.modules.student_academics.models import TeacherAssignment
from app.modules.teachers.models import TeacherAccount, TeacherMembership


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def project_teacher(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(TeacherMembership, TeacherAccount)
        .join(TeacherAccount, TeacherAccount.id == TeacherMembership.teacher_account_id)
        .where(
            TeacherMembership.tenant_id == tenant_id,
            TeacherMembership.id == entity_id,
        )
    ).first()
    if row is None:
        return None
    membership, account = row
    return CBTTeacherSnapshot(
        id=membership.id,
        teacher_account_id=membership.teacher_account_id,
        first_name=account.first_name,
        last_name=account.last_name,
        staff_id=membership.staff_id,
        status=_value(membership.status),
    ).model_dump(mode="json")


def project_teacher_assignment(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    assignment = session.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.id == entity_id,
        )
    ).scalar_one_or_none()
    if assignment is None or not assignment.is_active or assignment.effective_to is not None:
        return None
    return CBTTeacherAssignmentSnapshot(
        id=assignment.id,
        teacher_membership_id=assignment.teacher_membership_id,
        class_id=assignment.class_id,
        curriculum_subject_id=assignment.curriculum_subject_id,
        is_active=assignment.is_active,
    ).model_dump(mode="json")
