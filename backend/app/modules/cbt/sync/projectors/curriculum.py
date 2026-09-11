"""Stable CBT projections for subjects and persistent curricula."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cbt.academics.schemas import (
    CBTCurriculumSnapshot,
    CBTCurriculumSubjectDepartmentSnapshot,
    CBTCurriculumSubjectSnapshot,
    CBTSubjectSnapshot,
)
from app.modules.classes.models import AcademicLevel, AcademicLevelDepartment, Department
from app.modules.student_academics.curriculum_models import (
    Curriculum,
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.subjects.models import Subject


def _visible(row: Any) -> bool:
    if row is None:
        return False
    status = getattr(row, "status", None)
    if status is not None and getattr(status, "value", status) != "active":
        return False
    return bool(getattr(row, "is_active", True) and getattr(row, "archived_at", None) is None)


def project_subject(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    row = session.execute(
        select(Subject).where(
            Subject.tenant_id == tenant_id,
            Subject.id == entity_id,
        )
    ).scalar_one_or_none()
    if not _visible(row):
        return None
    return CBTSubjectSnapshot(
        id=row.id,
        name=row.name,
        code=row.code,
        is_active=row.is_active,
    ).model_dump(mode="json")


def project_curriculum(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(Curriculum, AcademicLevel)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .where(
            Curriculum.tenant_id == tenant_id,
            Curriculum.id == entity_id,
            AcademicLevel.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    curriculum, level = joined
    if not _visible(level):
        return None
    return CBTCurriculumSnapshot(
        id=curriculum.id,
        academic_level_id=curriculum.academic_level_id,
    ).model_dump(mode="json")


def project_curriculum_subject(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(CurriculumSubject, Curriculum, AcademicLevel, Subject)
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .join(Subject, Subject.id == CurriculumSubject.subject_id)
        .where(
            CurriculumSubject.tenant_id == tenant_id,
            CurriculumSubject.id == entity_id,
            Curriculum.tenant_id == tenant_id,
            AcademicLevel.tenant_id == tenant_id,
            Subject.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    curriculum_subject, _curriculum, level, subject = joined
    if not _visible(curriculum_subject) or not _visible(level) or not _visible(subject):
        return None
    return CBTCurriculumSubjectSnapshot(
        id=curriculum_subject.id,
        curriculum_id=curriculum_subject.curriculum_id,
        subject_id=curriculum_subject.subject_id,
        is_elective=curriculum_subject.is_elective,
        is_active=curriculum_subject.is_active,
    ).model_dump(mode="json")


def project_curriculum_subject_department(
    session: Session, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[str, Any] | None:
    joined = session.execute(
        select(
            CurriculumSubjectDepartment,
            CurriculumSubject,
            Curriculum,
            AcademicLevel,
            AcademicLevelDepartment,
            Department,
        )
        .join(
            CurriculumSubject,
            CurriculumSubject.id == CurriculumSubjectDepartment.curriculum_subject_id,
        )
        .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
        .join(AcademicLevel, AcademicLevel.id == Curriculum.academic_level_id)
        .join(
            AcademicLevelDepartment,
            AcademicLevelDepartment.id == CurriculumSubjectDepartment.academic_level_department_id,
        )
        .join(Department, Department.id == AcademicLevelDepartment.department_id)
        .where(
            CurriculumSubjectDepartment.tenant_id == tenant_id,
            CurriculumSubjectDepartment.id == entity_id,
            CurriculumSubject.tenant_id == tenant_id,
            Curriculum.tenant_id == tenant_id,
            AcademicLevel.tenant_id == tenant_id,
            AcademicLevelDepartment.tenant_id == tenant_id,
            Department.tenant_id == tenant_id,
        )
    ).first()
    if joined is None:
        return None
    scope, curriculum_subject, curriculum, level, link, department = joined
    if (
        not _visible(curriculum_subject)
        or not _visible(level)
        or not _visible(link)
        or not _visible(department)
        or link.academic_level_id != curriculum.academic_level_id
    ):
        return None
    return CBTCurriculumSubjectDepartmentSnapshot(
        id=scope.id,
        curriculum_subject_id=scope.curriculum_subject_id,
        department_id=scope.academic_level_department_id,
    ).model_dump(mode="json")


def curriculum_subject_department_ids_for_level(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    academic_level_id: uuid.UUID,
) -> list[uuid.UUID]:
    return list(
        session.execute(
            select(CurriculumSubjectDepartment.id)
            .join(
                CurriculumSubject,
                CurriculumSubject.id == CurriculumSubjectDepartment.curriculum_subject_id,
            )
            .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
            .where(
                CurriculumSubjectDepartment.tenant_id == tenant_id,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.is_active.is_(True),
                Curriculum.tenant_id == tenant_id,
                Curriculum.academic_level_id == academic_level_id,
            )
        ).scalars()
    )
