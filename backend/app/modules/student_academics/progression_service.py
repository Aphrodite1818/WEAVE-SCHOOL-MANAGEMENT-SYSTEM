"""Level-only academic session progression."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.category_catalog import categories_for
from app.modules.classes.models import AcademicLevel, AcademicLevelStatus
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.parents.repository import ParentMembershipRepository
from app.modules.school_calendar.repository import SchoolCalendarRepository
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
    StudentProgressionRepository,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
)
from app.modules.student_academics.schemas import AcademicSessionResponse
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentParentLinkStatus,
)
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentParentLinkRepository,
    StudentRepository,
)
from app.modules.students.service import StudentLifecycleService
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademicProgressionService:
    """Resolve automatic progression from level category and position only."""

    @staticmethod
    async def open_session(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ) -> AcademicSessionResponse:
        try:
            session = await AcademicSessionLifecycleRepository.get_by_id(
                db, actor.tenant_id, session_id, lock=True
            )
            if session is None:
                raise NotFoundException("Academic session not found.")
            if session.status != AcademicSessionStatus.DRAFT:
                raise ConflictException("Only draft sessions can be opened.")
            await StudentAcademicService._validate_session_dates(
                start_date=session.start_date,
                end_date=session.end_date,
                require_complete=True,
            )
            if await SchoolCalendarRepository.get_configuration(db, actor.tenant_id) is None:
                raise ConflictException(
                    "Configure the school calendar before opening an academic session.",
                    payload={
                        "blocker_messages": [
                            "School calendar configuration is required before session opening."
                        ]
                    },
                )
            preview = await StudentAcademicService.academic_session_dependency_preview(
                db, actor.tenant_id, session.id
            )
            if not preview.can_open:
                StudentAcademicService._raise_dependency_conflict(
                    "Academic session has blockers and cannot be opened.", preview
                )
            current = await AcademicSessionLifecycleRepository.get_current_open(
                db, actor.tenant_id, lock=True
            )
            if current is not None and current.id != session.id:
                raise ConflictException(
                    "Close the current academic session before opening another."
                )
            previous_status = session.status
            session.status = AcademicSessionStatus.OPEN
            session.is_current = True
            session.closing_started_at = None
            session.closed_at = None
            session.closed_by_admin_id = None
            await AcademicSessionLifecycleRepository.save(db, session)
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=actor.tenant_id,
                entity_type="session",
                entity_id=session.id,
                action="opened",
                previous_status=previous_status.value,
                new_status=session.status.value,
                acting_admin_id=actor.id,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Close the current academic session before opening another."
            ) from exc
        except Exception:
            await db.rollback()
            raise
        await db.refresh(session)
        return AcademicSessionResponse.model_validate(session)

    @staticmethod
    async def _load_progression_enrollments(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> list[StudentEnrollment]:
        result = await db.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_session_id == academic_session_id,
                StudentEnrollment.is_current.is_(True),
            )
            .order_by(StudentEnrollment.student_id)
            .with_for_update()
        )
        return list(result.scalars().all())

    @staticmethod
    async def resolve_next_level(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        current_level: AcademicLevel,
    ) -> AcademicLevel | None:
        """Resolve the next academic level without inferring class placement.

        Level positions are local to their category. Category ordering comes from the
        institution catalog. A missing immediately-next category configuration is a
        setup error, never an implicit graduation or a jump over that category.
        """

        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None or tenant.institution_type is None:
            raise ConflictException("Institution type is required for academic progression.")

        category_definitions = categories_for(tenant.institution_type)
        allowed_categories = [definition.value for definition in category_definitions]
        if current_level.category not in allowed_categories:
            raise ConflictException("Current academic level category is invalid for this tenant.")

        levels = await AcademicLevelRepository.list_for_tenant(db, tenant_id, active_only=True)
        same_category = [
            level
            for level in levels
            if level.category == current_level.category and level.position > current_level.position
        ]
        if same_category:
            return min(same_category, key=lambda level: level.position)

        current_category_index = allowed_categories.index(current_level.category)
        if current_category_index == len(allowed_categories) - 1:
            return None

        next_category = allowed_categories[current_category_index + 1]
        candidates = [level for level in levels if level.category == next_category]
        if not candidates:
            raise ConflictException(
                "Academic progression is incomplete: configure at least one active "
                f"{next_category.value.replace('_', ' ').title()} level before closing the session."
            )
        return min(candidates, key=lambda level: level.position)

    @staticmethod
    async def _downgrade_graduated_parent_access(
        db: AsyncSession, *, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> None:
        links = await StudentParentLinkRepository.list_for_student(
            db,
            tenant_id,
            student_id,
            statuses=[StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY],
            lock=True,
        )
        membership_ids: set[uuid.UUID] = set()
        for link in links:
            link.status = StudentParentLinkStatus.ALUMNI_READ_ONLY
            link.ended_at = None
            link.end_reason = None
            await StudentParentLinkRepository.save(db, link)
            membership_ids.add(link.parent_membership_id)
        for membership_id in membership_ids:
            membership = await ParentMembershipRepository.get_by_id(
                db, membership_id, tenant_id=tenant_id, lock=True
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(db, membership)

    @staticmethod
    async def _create_next_enrollment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student: Student,
        item: StudentProgressionItem,
        target_level: AcademicLevel,
        next_session: AcademicSession,
        created_by_admin_id: uuid.UUID | None,
    ) -> StudentProgressionItem:
        if next_session.status not in {AcademicSessionStatus.DRAFT, AcademicSessionStatus.OPEN}:
            raise ConflictException("The target academic session is not available.")
        current = await StudentEnrollmentRepository.get_current(
            db, tenant_id, student.id, lock=True
        )
        if current is not None:
            if (
                current.academic_session_id == next_session.id
                and current.academic_level_id == target_level.id
            ):
                item.to_enrollment_id = current.id
                item.to_level_id = target_level.id
                item.to_class_id = current.class_id
                item.status = StudentProgressionItemStatus.COMPLETED
                item.processed_at = _utc_now()
                return await StudentProgressionRepository.save_item(db, item)
            raise ConflictException("Student already has a different current enrollment.")

        next_enrollment = await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=student.id,
                academic_level_id=target_level.id,
                class_id=None,
                academic_session_id=next_session.id,
                started_on=next_session.start_date or date.today(),
                entry_outcome=StudentEnrollmentOutcome.PROMOTED,
                entry_reason="Automatic level progression",
                created_by_admin_id=created_by_admin_id,
            ),
        )
        item.to_enrollment_id = next_enrollment.id
        item.to_level_id = target_level.id
        item.to_class_id = None
        item.status = StudentProgressionItemStatus.COMPLETED
        item.reason = f"Progressed to {target_level.name}; class assignment is optional."
        item.processed_at = _utc_now()
        return await StudentProgressionRepository.save_item(db, item)

    @staticmethod
    async def _progress_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        run: StudentProgressionRun,
        enrollment: StudentEnrollment,
        next_session: AcademicSession,
        effective_date: date,
        allow_terminal_completion: bool = False,
    ) -> StudentProgressionItem:
        existing = await StudentProgressionRepository.get_item_by_run_and_student(
            db, run.id, enrollment.student_id, lock=True
        )
        if existing is not None:
            return existing

        student = await StudentRepository.get_by_id(
            db, actor.tenant_id, enrollment.student_id, lock=True, include_archived=True
        )
        if student is None:
            raise ConflictException(f"Enrollment {enrollment.id} references a missing student.")
        if student.is_archived or student.promotion_hold or student.status != AcademicStatus.ACTIVE:
            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_level_id=enrollment.academic_level_id,
                    from_class_id=enrollment.class_id,
                    action=StudentProgressionItemAction.SKIP,
                    status=StudentProgressionItemStatus.CANCELLED,
                    reason="Student is archived, on promotion hold, or not active.",
                    processed_at=_utc_now(),
                ),
            )

        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, enrollment.academic_level_id, lock=True
        )
        if level is None or level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException("Enrollment academic level is missing or inactive.")
        target_level = await AcademicProgressionService.resolve_next_level(
            db, tenant_id=actor.tenant_id, current_level=level
        )

        if target_level is None and not allow_terminal_completion:
            raise ConflictException(
                "Terminal academic completion requires explicit administrator confirmation."
            )

        enrollment.ended_on = effective_date
        enrollment.ended_by_admin_id = actor.id

        if target_level is None:
            enrollment.exit_outcome = StudentEnrollmentOutcome.GRADUATED
            enrollment.exit_reason = "Final configured academic level completed"
            await StudentEnrollmentRepository.save(db, enrollment)
            student.status = AcademicStatus.GRADUATED
            student.graduation_date = effective_date
            student.promotion_hold = True
            student.is_active = False
            student.account_status = StudentAccountStatus.INACTIVE
            await StudentRepository.save(db, student)
            await StudentLifecycleService._revoke_student_access(db, student, reason="graduated")
            await AuthIdentityService.deactivate_for_actor(
                db, actor_type=ActorType.STUDENT, actor_id=student.id
            )
            await AcademicProgressionService._downgrade_graduated_parent_access(
                db, tenant_id=actor.tenant_id, student_id=student.id
            )
            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_level_id=level.id,
                    from_class_id=enrollment.class_id,
                    action=StudentProgressionItemAction.COMPLETE,
                    status=StudentProgressionItemStatus.COMPLETED,
                    reason="Final configured level completed with administrator confirmation.",
                    processed_at=_utc_now(),
                ),
            )

        enrollment.exit_outcome = StudentEnrollmentOutcome.PROMOTED
        enrollment.exit_reason = "Academic session completed"
        await StudentEnrollmentRepository.save(db, enrollment)
        item = await StudentProgressionRepository.add_item(
            db,
            StudentProgressionItem(
                tenant_id=actor.tenant_id,
                progression_run_id=run.id,
                student_id=student.id,
                from_enrollment_id=enrollment.id,
                from_level_id=level.id,
                to_level_id=target_level.id,
                from_class_id=enrollment.class_id,
                action=StudentProgressionItemAction.PROGRESS,
                status=StudentProgressionItemStatus.BLOCKED,
                reason="Preparing next-session level enrollment.",
            ),
        )
        return await AcademicProgressionService._create_next_enrollment(
            db,
            tenant_id=actor.tenant_id,
            student=student,
            item=item,
            target_level=target_level,
            next_session=next_session,
            created_by_admin_id=actor.id,
        )
