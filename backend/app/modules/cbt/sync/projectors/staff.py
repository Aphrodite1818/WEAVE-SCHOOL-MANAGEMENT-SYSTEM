"""Stable CBT projections for admins, teachers, and class-subject assignments."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import (
    CBTAdminSnapshot,
    CBTTeacherAssignmentSnapshot,
    CBTTeacherSnapshot,
)
from app.modules.classes.models import AcademicLevel, AcademicLevelStatus, ClassRoom
from app.modules.student_academics.curriculum_models import Curriculum, CurriculumSubject
from app.modules.student_academics.models import TeacherAssignment
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def project_admin(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(TenantAdmin).where(
            TenantAdmin.tenant_id == tenant_id,
            TenantAdmin.id == entity_id,
        )
    ).scalar_one_or_none()
    if (
        row is None
        or row.account_status != TenantAdminStatus.ACTIVE
        or not row.is_active
        or not row.is_verified
    ):
        return None
    return CBTAdminSnapshot(
        id=row.id,
        email=row.email,
        status=_value(row.account_status),
    ).model_dump(mode="json")


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
    if (
        membership.status != TeacherMembershipStatus.ACTIVE
        or account.account_status != TeacherAccountStatus.ACTIVE
        or not account.is_active
    ):
        return None
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
    """Project the persistent class-subject teacher relationship.

    Curriculum eligibility is resolved and reconciled by the academic domain.
    Synchronization must not independently infer a term or specialization.
    """

    assignment_row = session.execute(
        select(TeacherAssignment, TeacherMembership, TeacherAccount)
        .join(
            TeacherMembership,
            TeacherMembership.id == TeacherAssignment.teacher_membership_id,
        )
        .join(TeacherAccount, TeacherAccount.id == TeacherMembership.teacher_account_id)
        .where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.id == entity_id,
        )
    ).first()
    if assignment_row is None:
        return None
    assignment, membership, account = assignment_row
    if (
        (assignment.effective_to is not None and assignment.effective_to < date.today())
        or membership.status != TeacherMembershipStatus.ACTIVE
        or account.account_status != TeacherAccountStatus.ACTIVE
        or not account.is_active
    ):
        return None

    context = session.execute(
        select(ClassRoom, CurriculumSubject, Curriculum, AcademicLevel)
        .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
        .join(Curriculum, Curriculum.academic_level_id == ClassRoom.academic_level_id)
        .join(CurriculumSubject, CurriculumSubject.curriculum_id == Curriculum.id)
        .where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.id == assignment.class_id,
            ClassRoom.is_active.is_(True),
            ClassRoom.archived_at.is_(None),
            AcademicLevel.tenant_id == tenant_id,
            AcademicLevel.status == AcademicLevelStatus.ACTIVE,
            Curriculum.tenant_id == tenant_id,
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == assignment.curriculum_subject_id,
            CurriculumSubject.is_active.is_(True),
        )
    ).first()
    if context is None:
        return None

    classroom, curriculum_subject, curriculum, _level = context
    if curriculum.academic_level_id != classroom.academic_level_id:
        return None
    return CBTTeacherAssignmentSnapshot(
        id=assignment.id,
        teacher_membership_id=assignment.teacher_membership_id,
        class_id=assignment.class_id,
        curriculum_subject_id=assignment.curriculum_subject_id,
        effective_from=assignment.effective_from,
        effective_to=assignment.effective_to,
    ).model_dump(mode="json")
