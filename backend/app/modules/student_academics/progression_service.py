"""Level-only academic session progression."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

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


_PROGRESSION_CONTEXT_KEY = "academic_progression_context"


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
    async def _prime_progression_context(
        db: AsyncSession,
        *,
        run: StudentProgressionRun,
        items: list[StudentProgressionItem],
    ) -> None:
        """Batch-lock immutable/shared progression reads once for the worker run."""

        student_ids = {item.student_id for item in items}
        level_ids = {item.from_level_id for item in items if item.from_level_id is not None}

        students: dict[uuid.UUID, Student] = {}
        if student_ids:
            result = await db.execute(
                select(Student)
                .where(
                    Student.tenant_id == run.tenant_id,
                    Student.id.in_(student_ids),
                )
                .order_by(Student.id.asc())
                .with_for_update()
            )
            students = {student.id: student for student in result.scalars().all()}

        levels: dict[uuid.UUID, AcademicLevel] = {}
        if level_ids:
            result = await db.execute(
                select(AcademicLevel)
                .where(
                    AcademicLevel.tenant_id == run.tenant_id,
                    AcademicLevel.status == AcademicLevelStatus.ACTIVE,
                )
                .order_by(AcademicLevel.id.asc())
                .with_for_update()
            )
            levels = {level.id: level for level in result.scalars().all()}

        tenant = await TenantRepository.get_by_id(db, run.tenant_id)

        target_enrollments: dict[uuid.UUID, StudentEnrollment] = {}
        if student_ids and run.next_academic_session_id is not None:
            result = await db.execute(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.tenant_id == run.tenant_id,
                    StudentEnrollment.student_id.in_(student_ids),
                    StudentEnrollment.academic_session_id == run.next_academic_session_id,
                )
                .order_by(StudentEnrollment.student_id.asc(), StudentEnrollment.created_at.asc())
                .with_for_update()
            )
            for enrollment in result.scalars().all():
                target_enrollments.setdefault(enrollment.student_id, enrollment)

        contexts = db.info.setdefault(_PROGRESSION_CONTEXT_KEY, {})
        contexts[run.id] = {
            "items": {item.student_id: item for item in items},
            "students": students,
            "levels": levels,
            "tenant": tenant,
            "target_enrollments": target_enrollments,
        }

    @staticmethod
    def _progression_context(db: AsyncSession, run_id: uuid.UUID) -> dict[str, Any] | None:
        contexts = db.info.get(_PROGRESSION_CONTEXT_KEY)
        if not isinstance(contexts, dict):
            return None
        context = contexts.get(run_id)
        return context if isinstance(context, dict) else None

    @staticmethod
    async def _load_progression_enrollments(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> list[StudentEnrollment]:
        """Load the immutable enrollment manifest captured when closure started.

        Never rediscover the worker population from live ``is_current`` state. A
        withdrawal, reassignment, graduation, or other state change after closure
        starts must still leave that frozen student explicitly accounted for.
        """

        run = await StudentProgressionRepository.get_run_by_session(
            db,
            tenant_id,
            academic_session_id,
            lock=True,
        )
        if run is None:
            return []
        items = await StudentProgressionRepository.reconcile_legacy_manifest(db, run)

        result = await db.execute(
            select(StudentEnrollment)
            .join(
                StudentProgressionItem,
                StudentProgressionItem.from_enrollment_id == StudentEnrollment.id,
            )
            .join(
                StudentProgressionRun,
                StudentProgressionRun.id == StudentProgressionItem.progression_run_id,
            )
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentProgressionItem.tenant_id == tenant_id,
                StudentProgressionRun.tenant_id == tenant_id,
                StudentProgressionRun.academic_session_id == academic_session_id,
            )
            .order_by(StudentProgressionItem.student_id.asc())
            .with_for_update()
        )
        enrollments = list(result.scalars().all())
        await AcademicProgressionService._prime_progression_context(db, run=run, items=items)
        return enrollments

    @staticmethod
    async def resolve_next_level(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        current_level: AcademicLevel,
        tenant: Any | None = None,
        levels: list[AcademicLevel] | None = None,
    ) -> AcademicLevel | None:
        """Resolve the next academic level without inferring class placement."""

        if tenant is None:
            tenant = await TenantRepository.get_by_id(db, tenant_id)
        if tenant is None or tenant.institution_type is None:
            raise ConflictException("Institution type is required for academic progression.")

        category_definitions = categories_for(tenant.institution_type)
        allowed_categories = [definition.value for definition in category_definitions]
        if current_level.category not in allowed_categories:
            raise ConflictException("Current academic level category is invalid for this tenant.")

        if levels is None:
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
        existing_target: StudentEnrollment | None = None,
        target_lookup_complete: bool = False,
    ) -> StudentProgressionItem:
        if next_session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException(
                "The target academic session must remain draft during progression."
            )
        if next_session.start_date is None:
            raise ConflictException("The target academic session is missing its start date.")

        if not target_lookup_complete:
            result = await db.execute(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.student_id == student.id,
                    StudentEnrollment.academic_session_id == next_session.id,
                )
                .order_by(StudentEnrollment.created_at.asc())
                .limit(1)
                .with_for_update()
            )
            existing_target = result.scalar_one_or_none()

        if existing_target is not None:
            if existing_target.academic_level_id != target_level.id:
                raise ConflictException(
                    "Student already has a different enrollment in the target academic session."
                )
            item.to_enrollment_id = existing_target.id
            item.to_level_id = target_level.id
            item.to_class_id = existing_target.class_id
            item.status = StudentProgressionItemStatus.COMPLETED
            item.processed_at = _utc_now()
            return await StudentProgressionRepository.save_item(db, item)

        next_enrollment = await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=student.id,
                academic_level_id=target_level.id,
                class_id=None,
                academic_session_id=next_session.id,
                started_on=next_session.start_date,
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
        context = AcademicProgressionService._progression_context(db, run.id)

        existing = None
        if context is not None:
            existing = context["items"].get(enrollment.student_id)
        if existing is None:
            existing = await StudentProgressionRepository.get_item_by_run_and_student(
                db, run.id, enrollment.student_id, lock=True
            )
        if existing is not None and existing.status != StudentProgressionItemStatus.BLOCKED:
            return existing
        if existing is not None and existing.from_enrollment_id not in {None, enrollment.id}:
            raise ConflictException("Progression manifest enrollment does not match the frozen target.")

        student = None
        if context is not None:
            student = context["students"].get(enrollment.student_id)
        if student is None:
            student = await StudentRepository.get_by_id(
                db, actor.tenant_id, enrollment.student_id, lock=True, include_archived=True
            )
        if student is None:
            raise ConflictException(f"Enrollment {enrollment.id} references a missing student.")

        if enrollment.exit_outcome is not None:
            item = existing or StudentProgressionItem(
                tenant_id=actor.tenant_id,
                progression_run_id=run.id,
                student_id=student.id,
            )
            item.from_enrollment_id = enrollment.id
            item.from_level_id = enrollment.academic_level_id
            item.from_class_id = enrollment.class_id
            item.action = StudentProgressionItemAction.SKIP
            item.status = StudentProgressionItemStatus.CANCELLED
            item.reason = (
                "Frozen enrollment changed before progression was applied "
                f"({enrollment.exit_outcome.value})."
            )
            item.processed_at = _utc_now()
            return await StudentProgressionRepository.save_item(db, item) if existing else await StudentProgressionRepository.add_item(db, item)

        if student.is_archived or student.promotion_hold or student.status != AcademicStatus.ACTIVE:
            item = existing or StudentProgressionItem(
                tenant_id=actor.tenant_id,
                progression_run_id=run.id,
                student_id=student.id,
            )
            item.from_enrollment_id = enrollment.id
            item.from_level_id = enrollment.academic_level_id
            item.from_class_id = enrollment.class_id
            item.action = StudentProgressionItemAction.SKIP
            item.status = StudentProgressionItemStatus.CANCELLED
            item.reason = "Student is archived, on promotion hold, or not active."
            item.processed_at = _utc_now()
            return await StudentProgressionRepository.save_item(db, item) if existing else await StudentProgressionRepository.add_item(db, item)

        level = None
        if context is not None:
            level = context["levels"].get(enrollment.academic_level_id)
        if level is None:
            level = await AcademicLevelRepository.get_by_id(
                db, actor.tenant_id, enrollment.academic_level_id, lock=True
            )
        if level is None or level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException("Enrollment academic level is missing or inactive.")

        target_level = await AcademicProgressionService.resolve_next_level(
            db,
            tenant_id=actor.tenant_id,
            current_level=level,
            tenant=context["tenant"] if context is not None else None,
            levels=list(context["levels"].values()) if context is not None else None,
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
            item = existing or StudentProgressionItem(
                tenant_id=actor.tenant_id,
                progression_run_id=run.id,
                student_id=student.id,
            )
            item.from_enrollment_id = enrollment.id
            item.from_level_id = level.id
            item.from_class_id = enrollment.class_id
            item.action = StudentProgressionItemAction.COMPLETE
            item.status = StudentProgressionItemStatus.COMPLETED
            item.reason = "Final configured level completed with administrator confirmation."
            item.processed_at = _utc_now()
            return await StudentProgressionRepository.save_item(db, item) if existing else await StudentProgressionRepository.add_item(db, item)

        enrollment.exit_outcome = StudentEnrollmentOutcome.PROMOTED
        enrollment.exit_reason = "Academic session completed"
        await StudentEnrollmentRepository.save(db, enrollment)

        item = existing or StudentProgressionItem(
            tenant_id=actor.tenant_id,
            progression_run_id=run.id,
            student_id=student.id,
        )
        item.from_enrollment_id = enrollment.id
        item.from_level_id = level.id
        item.to_level_id = target_level.id
        item.from_class_id = enrollment.class_id
        item.action = StudentProgressionItemAction.PROGRESS
        item.status = StudentProgressionItemStatus.BLOCKED
        item.reason = "Preparing next-session level enrollment."
        if existing:
            item = await StudentProgressionRepository.save_item(db, item)
        else:
            item = await StudentProgressionRepository.add_item(db, item)

        existing_target = None
        target_lookup_complete = False
        if context is not None:
            existing_target = context["target_enrollments"].get(student.id)
            target_lookup_complete = True

        completed = await AcademicProgressionService._create_next_enrollment(
            db,
            tenant_id=actor.tenant_id,
            student=student,
            item=item,
            target_level=target_level,
            next_session=next_session,
            created_by_admin_id=actor.id,
            existing_target=existing_target,
            target_lookup_complete=target_lookup_complete,
        )
        return completed
