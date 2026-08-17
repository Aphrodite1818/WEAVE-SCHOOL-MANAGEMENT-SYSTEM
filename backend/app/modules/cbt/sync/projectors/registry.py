"""Registry for the canonical v2 Cloud -> CBT projection contract."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.cbt.sync.projectors.academics import (
    project_academic_level,
    project_academic_session,
    project_academic_term,
    project_arm_label,
    project_class,
    project_class_term_department,
    project_department,
)
from app.modules.cbt.sync.projectors.assessments import (
    project_assessment_component,
    project_assessment_scheme,
)
from app.modules.cbt.sync.projectors.curriculum import (
    project_curriculum,
    project_curriculum_subject,
    project_subject,
    project_subject_offering,
)
from app.modules.cbt.sync.projectors.staff import (
    project_admin,
    project_teacher,
    project_teacher_assignment,
)
from app.modules.cbt.sync.projectors.students import project_student_enrollment

Projector = Callable[[Session, uuid.UUID, uuid.UUID], dict[str, Any] | None]

PROJECTORS: dict[CBTSyncEntityType, Projector] = {
    CBTSyncEntityType.ACADEMIC_LEVEL: project_academic_level,
    CBTSyncEntityType.DEPARTMENT: project_department,
    CBTSyncEntityType.ARM_LABEL: project_arm_label,
    CBTSyncEntityType.CLASS: project_class,
    CBTSyncEntityType.CLASS_TERM_DEPARTMENT: project_class_term_department,
    CBTSyncEntityType.ACADEMIC_SESSION: project_academic_session,
    CBTSyncEntityType.ACADEMIC_TERM: project_academic_term,
    CBTSyncEntityType.SUBJECT: project_subject,
    CBTSyncEntityType.CURRICULUM: project_curriculum,
    CBTSyncEntityType.CURRICULUM_SUBJECT: project_curriculum_subject,
    CBTSyncEntityType.SUBJECT_OFFERING: project_subject_offering,
    CBTSyncEntityType.ASSESSMENT_SCHEME: project_assessment_scheme,
    CBTSyncEntityType.ASSESSMENT_COMPONENT: project_assessment_component,
    CBTSyncEntityType.ADMIN: project_admin,
    CBTSyncEntityType.TEACHER: project_teacher,
    CBTSyncEntityType.TEACHER_ASSIGNMENT: project_teacher_assignment,
    CBTSyncEntityType.STUDENT_ENROLLMENT: project_student_enrollment,
}


def project_payload(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    entity_type: CBTSyncEntityType,
    entity_id: uuid.UUID,
) -> dict[str, Any] | None:
    projector = PROJECTORS[entity_type]
    return projector(session, tenant_id, entity_id)
