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
    CurriculumElectiveGroup,
    CurriculumSubject,
    CurriculumSubjectDepartment,
    ElectiveGroupLifecycle,
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

        source_group_ids = {
            row.elective_group_id
            for row in missing
            if row.is_elective and row.elective_group_id is not None
        }
        if any(row.is_elective and row.elective_group_id is None for row in missing):
            raise ConflictException(
                "The source curriculum contains a legacy elective without an elective group. "
                "Assign its group before copying this curriculum."
            )
        source_groups = {
            row.id: row
            for row in (
                await db.execute(
                    select(CurriculumElectiveGroup)
                    .where(
                        CurriculumElectiveGroup.tenant_id == tenant_id,
                        CurriculumElectiveGroup.curriculum_id == source.id,
                        CurriculumElectiveGroup.id.in_(source_group_ids),
                    )
                    .with_for_update()
                )
            ).scalars()
        }
        if source_group_ids - set(source_groups):
            raise ConflictException("A source elective group could not be resolved.")
        if any(
            group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value
            for group in source_groups.values()
        ):
            raise ConflictException(
                "Archived elective groups cannot be copied while their subjects are active."
            )

        target_groups = list(
            (
                await db.execute(
                    select(CurriculumElectiveGroup)
                    .where(
                        CurriculumElectiveGroup.tenant_id == tenant_id,
                        CurriculumElectiveGroup.curriculum_id == target.id,
                    )
                    .with_for_update()
                )
            ).scalars()
        )
        target_by_name = {row.name.casefold(): row for row in target_groups}
        group_map: dict[uuid.UUID, uuid.UUID] = {}
        for source_group in sorted(source_groups.values(), key=lambda item: item.name.casefold()):
            target_group = target_by_name.get(source_group.name.casefold())
            if target_group is None:
                target_group = CurriculumElectiveGroup(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    curriculum_id=target.id,
                    name=source_group.name,
                    minimum_choices=source_group.minimum_choices,
                    maximum_choices=source_group.maximum_choices,
                    lifecycle=ElectiveGroupLifecycle.ACTIVE.value,
                )
                db.add(target_group)
                await db.flush()
                target_by_name[source_group.name.casefold()] = target_group
            elif target_group.lifecycle != ElectiveGroupLifecycle.ACTIVE.value:
                raise ConflictException(
                    f"Restore destination elective group '{target_group.name}' before copying."
                )
            group_map[source_group.id] = target_group.id

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

        # Every validation finishes before the first subject insert. No existing row is changed.
        for source_row in missing:
            target_group_id = (
                group_map[source_row.elective_group_id]
                if source_row.is_elective and source_row.elective_group_id is not None
                else None
            )
            row = CurriculumSubject(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                curriculum_id=target.id,
                subject_id=source_row.subject_id,
                is_elective=source_row.is_elective,
                elective_group_id=target_group_id,
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
