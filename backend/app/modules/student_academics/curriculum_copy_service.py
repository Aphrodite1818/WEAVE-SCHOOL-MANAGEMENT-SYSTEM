"""Copy missing curriculum memberships without replacing destination configuration."""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.models import AcademicLevelDepartment, AcademicLevelStatus
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.student_academics.curriculum_models import (
    CurriculumSubject,
    CurriculumSubjectDepartment,
)
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.subjects.models import Subject


async def copy_curriculum(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    target_level_id: uuid.UUID,
    source_level_id: uuid.UUID,
):
    try:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        if source_level_id == target_level_id:
            raise ConflictException("Choose a different level to copy from.")

        # Stable lock ordering also serializes opposing copies between two levels.
        levels = {}
        for level_id in sorted([source_level_id, target_level_id], key=str):
            level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id, lock=True)
            if level is None:
                raise NotFoundException("Academic level not found.")
            if level.status != AcademicLevelStatus.ACTIVE:
                raise ConflictException("Both levels must be active to copy curriculum.")
            levels[level_id] = level
        if levels[source_level_id].category != levels[target_level_id].category:
            raise ConflictException(
                "Curriculum can only be copied between levels in the same category."
            )

        source = await AcademicCurriculumService._curriculum(db, tenant_id, source_level_id)
        target = await AcademicCurriculumService._curriculum(db, tenant_id, target_level_id)
        source_rows = (
            await db.execute(
                select(CurriculumSubject, Subject)
                .join(Subject, Subject.id == CurriculumSubject.subject_id)
                .where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.curriculum_id == source.id,
                    Subject.tenant_id == tenant_id,
                )
                .order_by(CurriculumSubject.id)
                .with_for_update()
            )
        ).all()
        existing = set(
            (
                await db.execute(
                    select(CurriculumSubject.subject_id).where(
                        CurriculumSubject.tenant_id == tenant_id,
                        CurriculumSubject.curriculum_id == target.id,
                    )
                )
            ).scalars()
        )
        inactive = sum(
            not row.is_active or not subject.is_active or subject.archived_at is not None
            for row, subject in source_rows
        )
        active = [
            row
            for row, subject in source_rows
            if row.is_active and subject.is_active and subject.archived_at is None
        ]
        if not active:
            raise ConflictException("The source curriculum has no active subjects to copy.")
        missing = [row for row in active if row.subject_id not in existing]
        scopes = {}
        if missing:
            scope_rows = (
                await db.execute(
                    select(CurriculumSubjectDepartment, AcademicLevelDepartment)
                    .join(
                        AcademicLevelDepartment,
                        AcademicLevelDepartment.id
                        == CurriculumSubjectDepartment.academic_level_department_id,
                    )
                    .where(
                        CurriculumSubjectDepartment.tenant_id == tenant_id,
                        CurriculumSubjectDepartment.curriculum_subject_id.in_(
                            [row.id for row in missing]
                        ),
                        AcademicLevelDepartment.tenant_id == tenant_id,
                    )
                    .with_for_update()
                )
            ).all()
            # A department has a different availability-link ID in each level.
            mapped = {}
            for scope, source_link in scope_rows:
                if source_link.academic_level_id != source_level_id:
                    raise ConflictException(
                        "A source department does not belong to the source level."
                    )
                department_id = source_link.department_id
                if department_id not in mapped:
                    target_link = await AcademicLevelDepartmentRepository.get_for_level_department(
                        db, tenant_id, target_level_id, department_id, lock=True
                    )
                    if target_link is None:
                        raise ConflictException(
                            "Enable the source curriculum's departments on the destination level before copying."
                        )
                    mapped[department_id] = target_link.id
                scopes.setdefault(scope.curriculum_subject_id, []).append(mapped[department_id])
            await AcademicCurriculumService._validated_level_department_ids(
                db,
                tenant_id=tenant_id,
                academic_level_id=target_level_id,
                ids=list(mapped.values()),
            )
        # Every validation finishes before the first insert. No existing row is changed.
        for source_row in missing:
            row = CurriculumSubject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                curriculum_id=target.id,
                subject_id=source_row.subject_id,
                is_elective=source_row.is_elective,
                is_active=True,
            )
            db.add(row)
            await db.flush()
            for link_id in scopes.get(source_row.id, []):
                db.add(
                    CurriculumSubjectDepartment(
                        tenant_id=tenant_id,
                        curriculum_subject_id=row.id,
                        academic_level_department_id=link_id,
                    )
                )
        await db.commit()
        return {
            "created": len(missing),
            "skipped_existing": len(active) - len(missing),
            "skipped_inactive": inactive,
        }
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException(
            "The curriculum changed while copying. Refresh and try again."
        ) from exc
    except Exception:
        await db.rollback()
        raise
