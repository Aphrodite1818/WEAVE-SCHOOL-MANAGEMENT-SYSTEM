"""Stable CBT projections for teachers and current class-subject assignments."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import CBTTeacherAssignmentSnapshot, CBTTeacherSnapshot
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.models import (
    AcademicTerm,
    AcademicTermStatus,
    TeacherAssignment,
)
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)


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
    """Expose an assignment only while it is usable by the current open term."""

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
    today = date.today()
    if (
        not assignment.is_active
        or assignment.effective_from > today
        or (assignment.effective_to is not None and assignment.effective_to < today)
        or membership.status != TeacherMembershipStatus.ACTIVE
        or account.account_status != TeacherAccountStatus.ACTIVE
        or not account.is_active
    ):
        return None

    term = session.execute(
        select(AcademicTerm).where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.is_current.is_(True),
            AcademicTerm.status == AcademicTermStatus.OPEN,
        )
    ).scalar_one_or_none()
    if term is None:
        return None

    context = session.execute(
        select(ClassRoom, CurriculumSubject, Curriculum)
        .join(
            Curriculum,
            Curriculum.academic_level_id == ClassRoom.academic_level_id,
        )
        .join(
            CurriculumSubject,
            CurriculumSubject.curriculum_id == Curriculum.id,
        )
        .where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.id == assignment.class_id,
            ClassRoom.is_active.is_(True),
            ClassRoom.archived_at.is_(None),
            Curriculum.tenant_id == tenant_id,
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == assignment.curriculum_subject_id,
            CurriculumSubject.is_active.is_(True),
        )
    ).first()
    if context is None:
        return None

    classroom, curriculum_subject, _curriculum = context
    class_department_id = session.execute(
        select(ClassTermDepartmentAssignment.department_id).where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.class_id == classroom.id,
            ClassTermDepartmentAssignment.academic_term_id == term.id,
        )
    ).scalar_one_or_none()

    offering_id = session.execute(
        select(CurriculumOffering.id)
        .where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.curriculum_subject_id == curriculum_subject.id,
            CurriculumOffering.academic_term_id == term.id,
            or_(
                CurriculumOffering.department_id.is_(None),
                CurriculumOffering.department_id == class_department_id,
            ),
        )
        .limit(1)
    ).scalar_one_or_none()
    if offering_id is None:
        return None

    return CBTTeacherAssignmentSnapshot(
        id=assignment.id,
        teacher_membership_id=assignment.teacher_membership_id,
        class_id=assignment.class_id,
        curriculum_subject_id=assignment.curriculum_subject_id,
        is_active=assignment.is_active,
    ).model_dump(mode="json")
