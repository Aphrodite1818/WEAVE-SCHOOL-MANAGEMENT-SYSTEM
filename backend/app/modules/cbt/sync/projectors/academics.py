"""Stable CBT projections for active academic structure and current periods."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import (
    CBTAcademicLevelSnapshot,
    CBTAcademicSessionSnapshot,
    CBTAcademicTermSnapshot,
    CBTArmLabelSnapshot,
    CBTClassSnapshot,
    CBTClassTermDepartmentSnapshot,
    CBTDepartmentSnapshot,
)
from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom, Department
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
)


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def _visible(row: Any) -> bool:
    return bool(
        row is not None
        and getattr(row, "is_active", True)
        and getattr(row, "archived_at", None) is None
    )


def project_academic_level(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(AcademicLevel).where(
            AcademicLevel.tenant_id == tenant_id,
            AcademicLevel.id == entity_id,
        )
    ).scalar_one_or_none()
    if not _visible(row):
        return None
    return CBTAcademicLevelSnapshot(
        id=row.id,
        name=row.name,
        category=_value(row.category),
        position=row.position,
    ).model_dump(mode="json")


def project_department(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(Department, AcademicLevel)
        .join(AcademicLevel, AcademicLevel.id == Department.academic_level_id)
        .where(
            Department.tenant_id == tenant_id,
            Department.id == entity_id,
            AcademicLevel.tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        return None
    department, level = row
    if not _visible(department) or not _visible(level):
        return None
    return CBTDepartmentSnapshot(
        id=department.id,
        academic_level_id=department.academic_level_id,
        name=department.name,
    ).model_dump(mode="json")


def project_arm_label(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(ArmLabel).where(
            ArmLabel.tenant_id == tenant_id,
            ArmLabel.id == entity_id,
        )
    ).scalar_one_or_none()
    if not _visible(row):
        return None
    return CBTArmLabelSnapshot(id=row.id, label=row.label).model_dump(mode="json")


def project_class(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(ClassRoom, AcademicLevel, ArmLabel)
        .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
        .join(ArmLabel, ArmLabel.id == ClassRoom.arm_label_id)
        .where(
            ClassRoom.tenant_id == tenant_id,
            ClassRoom.id == entity_id,
            AcademicLevel.tenant_id == tenant_id,
            ArmLabel.tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        return None
    classroom, level, arm = row
    if not _visible(classroom) or not _visible(level) or not _visible(arm):
        return None
    return CBTClassSnapshot(
        id=classroom.id,
        academic_level_id=classroom.academic_level_id,
        arm_label_id=classroom.arm_label_id,
        display_name=f"{level.name} {arm.label}".strip(),
        is_active=classroom.is_active,
    ).model_dump(mode="json")


def project_class_term_department(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(
            ClassTermDepartmentAssignment,
            AcademicTerm,
            ClassRoom,
            Department,
            AcademicLevel,
        )
        .join(AcademicTerm, AcademicTerm.id == ClassTermDepartmentAssignment.academic_term_id)
        .join(ClassRoom, ClassRoom.id == ClassTermDepartmentAssignment.class_id)
        .join(Department, Department.id == ClassTermDepartmentAssignment.department_id)
        .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
        .where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.id == entity_id,
            AcademicTerm.tenant_id == tenant_id,
            ClassRoom.tenant_id == tenant_id,
            Department.tenant_id == tenant_id,
            AcademicLevel.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    row, term, classroom, department, level = joined
    if (
        not term.is_current
        or term.status != AcademicTermStatus.OPEN
        or not _visible(classroom)
        or not _visible(department)
        or not _visible(level)
        or department.academic_level_id != classroom.academic_level_id
    ):
        return None
    return CBTClassTermDepartmentSnapshot(
        id=row.id,
        class_id=row.class_id,
        academic_term_id=row.academic_term_id,
        department_id=row.department_id,
    ).model_dump(mode="json")


def project_academic_session(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.id == entity_id,
        )
    ).scalar_one_or_none()
    if (
        row is None
        or not row.is_current
        or row.status not in {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
    ):
        return None
    return CBTAcademicSessionSnapshot(
        id=row.id,
        name=row.name,
        status=_value(row.status),
        is_current=row.is_current,
    ).model_dump(mode="json")


def project_academic_term(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(AcademicTerm, AcademicSession)
        .join(AcademicSession, AcademicSession.id == AcademicTerm.academic_session_id)
        .where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.id == entity_id,
            AcademicSession.tenant_id == tenant_id,
        )
    ).first()
    if row is None:
        return None
    term, academic_session = row
    if (
        not term.is_current
        or term.status not in {AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING}
        or not academic_session.is_current
        or academic_session.status
        not in {AcademicSessionStatus.OPEN, AcademicSessionStatus.CLOSING}
    ):
        return None
    return CBTAcademicTermSnapshot(
        id=term.id,
        academic_session_id=term.academic_session_id,
        name=_value(term.name),
        status=_value(term.status),
        is_current=term.is_current,
    ).model_dump(mode="json")
