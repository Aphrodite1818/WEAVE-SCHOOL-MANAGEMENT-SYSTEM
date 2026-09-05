"""Atomic curriculum additions using the canonical validation rules."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.curriculum_models import (
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.curriculum_v2_schemas import CurriculumSubjectsBulkCreate
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.subjects.models import Subject


async def add_curriculum_subjects(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    level_id: uuid.UUID,
    payload: CurriculumSubjectsBulkCreate,
):
    try:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum = await AcademicCurriculumService._curriculum(
            db, tenant_id, level_id, require_active_level=True
        )
        ids = [row.subject_id for row in payload.subjects]
        subjects = list(
            (
                await db.execute(
                    select(Subject)
                    .where(
                        Subject.tenant_id == tenant_id,
                        Subject.id.in_(ids),
                        Subject.is_active.is_(True),
                        Subject.archived_at.is_(None),
                    )
                    .with_for_update()
                )
            ).scalars()
        )
        if len(subjects) != len(ids):
            raise NotFoundException(
                "Every selected subject must be active and belong to this school."
            )
        existing = (
            await db.execute(
                select(CurriculumSubject.id).where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.curriculum_id == curriculum.id,
                    CurriculumSubject.subject_id.in_(ids),
                )
            )
        ).first()
        if existing:
            raise ConflictException(
                "A selected subject is already in this curriculum. Refresh and review your selection."
            )
        department_ids = list(
            dict.fromkeys(
                link for row in payload.subjects for link in row.academic_level_department_ids
            )
        )
        await AcademicCurriculumService._validated_level_department_ids(
            db, tenant_id=tenant_id, academic_level_id=level_id, ids=department_ids
        )
        # Validate the whole batch before writing, and commit exactly once.
        for item in payload.subjects:
            row = CurriculumSubject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                curriculum_id=curriculum.id,
                subject_id=item.subject_id,
                is_elective=item.is_elective,
                is_active=True,
            )
            db.add(row)
            await db.flush()
            for link_id in item.academic_level_department_ids:
                db.add(
                    CurriculumSubjectDepartment(
                        tenant_id=tenant_id,
                        curriculum_subject_id=row.id,
                        academic_level_department_id=link_id,
                    )
                )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException(
            "The curriculum changed while saving. Refresh and review your selection."
        ) from exc
    except Exception:
        await db.rollback()
        raise
    return {"created": len(payload.subjects)}
