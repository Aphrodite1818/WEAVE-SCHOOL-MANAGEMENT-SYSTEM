"""Build a consistent v2 CBT bootstrap from the canonical sync projectors."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.modules.cbt.academics.schemas import (
    CBTAcademicBootstrapResponse,
    CBTAcademicLevelSnapshot,
    CBTAcademicSessionSnapshot,
    CBTAcademicTermSnapshot,
    CBTArmLabelSnapshot,
    CBTAssessmentComponentSnapshot,
    CBTAssessmentSchemeSnapshot,
    CBTClassSnapshot,
    CBTClassTermDepartmentSnapshot,
    CBTCurriculumOfferingSnapshot,
    CBTCurriculumSnapshot,
    CBTCurriculumSubjectSnapshot,
    CBTDepartmentSnapshot,
    CBTSchoolSnapshot,
    CBTServerSnapshot,
    CBTStudentEnrollmentSnapshot,
    CBTSubjectSnapshot,
    CBTSyncMetadata,
    CBTTeacherAssignmentSnapshot,
    CBTTeacherSnapshot,
)
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.models import CBTServer
from app.modules.cbt.sync.enums import CBTSyncEntityType
from app.modules.cbt.sync.projectors.registry import project_payload
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom, Department
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    AssessmentComponent,
    AssessmentScheme,
    TeacherAssignment,
)
from app.modules.students.models import StudentEnrollment
from app.modules.subjects.models import Subject
from app.modules.teachers.models import TeacherMembership
from app.tenant_management.models import Tenant

SnapshotT = TypeVar("SnapshotT", bound=BaseModel)


class CBTAcademicSyncService:
    @staticmethod
    async def build_bootstrap(
        _request_db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTAcademicBootstrapResponse:
        # Authentication may already have used the request session. A dedicated
        # REPEATABLE READ transaction guarantees that projected rows and the cursor
        # come from the same MVCC boundary.
        async with AsyncSessionLocal() as db:
            await db.connection(
                execution_options={"isolation_level": "REPEATABLE READ"}
            )
            return await CBTAcademicSyncService._build(
                db,
                current_server=current_server,
            )

    @staticmethod
    async def _ids(
        db: AsyncSession,
        *,
        model,
        tenant_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        return list(
            (
                await db.execute(
                    select(model.id).where(model.tenant_id == tenant_id).order_by(model.id)
                )
            ).scalars()
        )

    @staticmethod
    async def _project_many(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        entity_type: CBTSyncEntityType,
        entity_ids: list[uuid.UUID],
        schema: type[SnapshotT],
    ) -> list[SnapshotT]:
        """Project bootstrap entities through the exact incremental-sync contract."""

        def _project(sync_session) -> list[SnapshotT]:
            projected: list[SnapshotT] = []
            for entity_id in entity_ids:
                payload = project_payload(
                    sync_session,
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
                if payload is not None:
                    projected.append(schema.model_validate(payload))
            return projected

        return await db.run_sync(_project)

    @staticmethod
    async def _build(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTAcademicBootstrapResponse:
        tenant_id = current_server.tenant_id
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()
        server = (
            await db.execute(
                select(CBTServer).where(
                    CBTServer.id == current_server.server_id,
                    CBTServer.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

        model_contracts: tuple[
            tuple[object, CBTSyncEntityType, type[BaseModel], str], ...
        ] = (
            (AcademicSession, CBTSyncEntityType.ACADEMIC_SESSION, CBTAcademicSessionSnapshot, "sessions"),
            (AcademicTerm, CBTSyncEntityType.ACADEMIC_TERM, CBTAcademicTermSnapshot, "terms"),
            (AcademicLevel, CBTSyncEntityType.ACADEMIC_LEVEL, CBTAcademicLevelSnapshot, "levels"),
            (ArmLabel, CBTSyncEntityType.ARM_LABEL, CBTArmLabelSnapshot, "arm_labels"),
            (Department, CBTSyncEntityType.DEPARTMENT, CBTDepartmentSnapshot, "departments"),
            (ClassRoom, CBTSyncEntityType.CLASS, CBTClassSnapshot, "classes"),
            (
                ClassTermDepartmentAssignment,
                CBTSyncEntityType.CLASS_TERM_DEPARTMENT,
                CBTClassTermDepartmentSnapshot,
                "class_term_departments",
            ),
            (Subject, CBTSyncEntityType.SUBJECT, CBTSubjectSnapshot, "subjects"),
            (Curriculum, CBTSyncEntityType.CURRICULUM, CBTCurriculumSnapshot, "curricula"),
            (
                CurriculumSubject,
                CBTSyncEntityType.CURRICULUM_SUBJECT,
                CBTCurriculumSubjectSnapshot,
                "curriculum_subjects",
            ),
            (
                CurriculumOffering,
                CBTSyncEntityType.SUBJECT_OFFERING,
                CBTCurriculumOfferingSnapshot,
                "offerings",
            ),
            (
                AssessmentScheme,
                CBTSyncEntityType.ASSESSMENT_SCHEME,
                CBTAssessmentSchemeSnapshot,
                "assessment_schemes",
            ),
            (
                AssessmentComponent,
                CBTSyncEntityType.ASSESSMENT_COMPONENT,
                CBTAssessmentComponentSnapshot,
                "assessment_components",
            ),
            (TeacherMembership, CBTSyncEntityType.TEACHER, CBTTeacherSnapshot, "teachers"),
            (
                TeacherAssignment,
                CBTSyncEntityType.TEACHER_ASSIGNMENT,
                CBTTeacherAssignmentSnapshot,
                "teacher_assignments",
            ),
            (
                StudentEnrollment,
                CBTSyncEntityType.STUDENT_ENROLLMENT,
                CBTStudentEnrollmentSnapshot,
                "student_enrollments",
            ),
        )

        payloads: dict[str, list[BaseModel]] = {}
        for model, entity_type, schema, target in model_contracts:
            ids = await CBTAcademicSyncService._ids(
                db,
                model=model,
                tenant_id=tenant_id,
            )
            payloads[target] = await CBTAcademicSyncService._project_many(
                db,
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_ids=ids,
                schema=schema,
            )

        # This cursor is read after every projection inside the same repeatable-read
        # transaction. Any concurrent mutation therefore appears either in both the
        # bootstrap and cursor boundary or in neither.
        cursor = await CBTSyncRepository.get_latest_cursor(db, tenant_id=tenant_id)
        return CBTAcademicBootstrapResponse(
            metadata=CBTSyncMetadata(
                snapshot_id=uuid.uuid4(),
                generated_at=datetime.now(timezone.utc),
                cursor=cursor,
            ),
            school=CBTSchoolSnapshot(
                id=tenant.id,
                name=tenant.school_name,
                institution_type=(
                    tenant.institution_type.value if tenant.institution_type else None
                ),
                timezone=tenant.timezone,
            ),
            server=CBTServerSnapshot(id=server.id, name=server.name),
            sessions=payloads["sessions"],
            terms=payloads["terms"],
            levels=payloads["levels"],
            arm_labels=payloads["arm_labels"],
            departments=payloads["departments"],
            classes=payloads["classes"],
            class_term_departments=payloads["class_term_departments"],
            subjects=payloads["subjects"],
            curricula=payloads["curricula"],
            curriculum_subjects=payloads["curriculum_subjects"],
            offerings=payloads["offerings"],
            assessment_schemes=payloads["assessment_schemes"],
            assessment_components=payloads["assessment_components"],
            teachers=payloads["teachers"],
            teacher_assignments=payloads["teacher_assignments"],
            student_enrollments=payloads["student_enrollments"],
        )
