"""Stable CBT projections for teachers and class-subject assignments."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import CBTTeacherAssignmentSnapshot, CBTTeacherSnapshot
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.curriculum_models import Curriculum, CurriculumSubject
from app.modules.student_academics.models import LevelSubject, TeacherAssignment
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


def _curriculum_subject_id_for_assignment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    assignment: TeacherAssignment,
) -> uuid.UUID | None:
    # TeacherAssignment still stores the legacy subject mapping internally on this
    # branch. The wire contract is curriculum-first, so translate by immutable
    # subject identity + the assignment class level. No legacy identifier leaks to CBT.
    row = session.execute(
        select(LevelSubject.subject_id, ClassRoom.academic_level_id)
        .join(ClassRoom, ClassRoom.id == assignment.class_id)
        .where(
            LevelSubject.tenant_id == tenant_id,
            LevelSubject.id == assignment.level_subject_id,
            ClassRoom.tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        return None
    subject_id, academic_level_id = row
    return session.execute(
        select(CurriculumSubject.id)
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .where(
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.subject_id == subject_id,
            CurriculumSubject.is_active.is_(True),
            Curriculum.academic_level_id == academic_level_id,
        )
    ).scalar_one_or_none()


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
    curriculum_subject_id = _curriculum_subject_id_for_assignment(
        session,
        tenant_id=tenant_id,
        assignment=assignment,
    )
    if curriculum_subject_id is None:
        return None
    return CBTTeacherAssignmentSnapshot(
        id=assignment.id,
        teacher_membership_id=assignment.teacher_membership_id,
        class_id=assignment.class_id,
        curriculum_subject_id=curriculum_subject_id,
        is_active=assignment.is_active,
    ).model_dump(mode="json")
