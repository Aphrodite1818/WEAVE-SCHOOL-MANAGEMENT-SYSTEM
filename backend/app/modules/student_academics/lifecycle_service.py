"""Atomic academic-session opening, closure, and student progression."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.parents.repository import ParentMembershipRepository
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
    StudentProgressionItemRepository,
    StudentProgressionRunRepository,
)
from app.modules.student_academics.lifecycle_schemas import (
    AcademicSessionCloseRequest,
    AcademicSessionOpenRequest,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
    StudentProgressionRunStatus,
)
from app.modules.student_academics.schemas import (
    AcademicSessionCloseResponse,
    AcademicSessionResponse,
    StudentProgressionItemResponse,
    StudentProgressionRunDetailResponse,
)
from app.modules.students.models import (
    AcademicStatus,
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademicSessionLifecycleService:
    """Coordinate current-session state and preserve progression history."""

    @staticmethod
    async def _run_response(
        db: AsyncSession,
        run: StudentProgressionRun,
    ) -> StudentProgressionRunDetailResponse:
        items = await StudentProgressionItemRepository.list_for_run(
            db,
            run.tenant_id,
            run.id,
        )
        return StudentProgressionRunDetailResponse(
            **StudentProgressionRunDetailResponse.model_validate(run).model_dump(
                exclude={"items"}
            ),
            items=[
                StudentProgressionItemResponse.model_validate(item)
                for item in items
            ],
        )

    @staticmethod
    async def open_session(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: UUID,
        payload: AcademicSessionOpenRequest,
    ) -> AcademicSessionResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            actor.tenant_id,
            session_id,
            lock=True,
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        if session.status == AcademicSessionStatus.OPEN and session.is_current:
            return AcademicSessionResponse.model_validate(session)
        if session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException("Only a draft academic session can be opened.")

        current = await AcademicSessionLifecycleRepository.get_current_open(
            db,
            actor.tenant_id,
            lock=True,
        )
        if current is not None and current.id != session.id:
            raise ConflictException(
                "Close the current academic session before opening another one."
            )

        _ = payload.reason
        session.status = AcademicSessionStatus.OPEN
        session.is_current = True
        session.is_active = True
        session.closing_started_at = None
        session.closed_at = None
        session.closed_by_admin_id = None
        await AcademicSessionLifecycleRepository.save(db, session)
        await db.commit()
        await db.refresh(session)
        return AcademicSessionResponse.model_validate(session)

    @staticmethod
    async def _validate_progression_chain(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> dict[UUID, object]:
        classrooms = await ClassRoomRepository.list_progression_chain_rows(
            db,
            tenant_id,
            lock=True,
        )
        by_id = {classroom.id: classroom for classroom in classrooms}
        for classroom in classrooms:
            student_count = await ClassRoomRepository.count_current_students(
                db,
                tenant_id,
                classroom.id,
            )
            if student_count == 0:
                continue
            if classroom.is_terminal:
                if classroom.next_class_id is not None:
                    raise ConflictException(
                        f"Terminal class {classroom.name} cannot have a next class."
                    )
                continue
            if classroom.next_class_id is None:
                raise ConflictException(
                    f"Class {classroom.name} has students but no next class mapping."
                )
            target = by_id.get(classroom.next_class_id)
            if target is None or not target.is_active:
                raise ConflictException(
                    f"The next class configured for {classroom.name} is unavailable."
                )
        return by_id

    @staticmethod
    async def _graduate_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student,
        enrollment,
        effective_date,
        reason: str,
    ) -> set[UUID]:
        enrollment.is_current = False
        enrollment.ended_on = effective_date
        enrollment.outcome = StudentEnrollmentOutcome.GRADUATED
        enrollment.reason = reason
        enrollment.changed_by_admin_id = actor.id
        await StudentEnrollmentRepository.save(db, enrollment)

        student.status = AcademicStatus.GRADUATED
        student.graduation_date = effective_date
        student.class_id = None
        student.arm = None
        student.promotion_hold = True
        student.is_active = False
        student.account_status = StudentAccountStatus.INACTIVE
        await StudentRepository.save(db, student)
        await StudentLifecycleService._revoke_student_access(
            db,
            student,
            reason="graduated",
        )

        membership_ids: set[UUID] = set()
        links = await StudentParentLinkRepository.list_for_student(
            db,
            actor.tenant_id,
            student.id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
            ],
            lock=True,
        )
        for link in links:
            link.status = StudentParentLinkStatus.ALUMNI_READ_ONLY
            link.ended_at = None
            link.end_reason = None
            await StudentParentLinkRepository.save(db, link)
            membership_ids.add(link.parent_membership_id)
        return membership_ids

    @staticmethod
    async def _promote_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student,
        enrollment,
        target_class,
        next_session: AcademicSession,
        effective_date,
        reason: str,
    ) -> StudentEnrollment:
        enrollment.is_current = False
        enrollment.ended_on = effective_date
        enrollment.outcome = StudentEnrollmentOutcome.PROMOTED
        enrollment.reason = reason
        enrollment.changed_by_admin_id = actor.id
        await StudentEnrollmentRepository.save(db, enrollment)

        next_enrollment = await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=actor.tenant_id,
                student_id=student.id,
                class_id=target_class.id,
                academic_session_id=next_session.id,
                started_on=effective_date,
                is_current=True,
                outcome=StudentEnrollmentOutcome.PROMOTED,
                reason=reason,
                changed_by_admin_id=actor.id,
            ),
        )
        student.class_id = target_class.id
        student.arm = target_class.arm
        student.status = AcademicStatus.ACTIVE
        student.promotion_hold = False
        student.is_active = True
        student.account_status = StudentAccountStatus.ACTIVE
        await StudentRepository.save(db, student)
        return next_enrollment

    @staticmethod
    async def close_session(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: UUID,
        payload: AcademicSessionCloseRequest,
    ) -> AcademicSessionCloseResponse:
        existing = await StudentProgressionRunRepository.get_by_idempotency_key(
            db,
            actor.tenant_id,
            payload.idempotency_key,
        )
        if existing is not None:
            closed = await AcademicSessionLifecycleRepository.get_by_id(
                db,
                actor.tenant_id,
                existing.academic_session_id,
            )
            opened = await AcademicSessionLifecycleRepository.get_by_id(
                db,
                actor.tenant_id,
                existing.next_academic_session_id,
            )
            if closed is None or opened is None:
                raise ConflictException("Progression history is incomplete.")
            return AcademicSessionCloseResponse(
                closed_session=AcademicSessionResponse.model_validate(closed),
                opened_session=AcademicSessionResponse.model_validate(opened),
                progression_run=await AcademicSessionLifecycleService._run_response(
                    db,
                    existing,
                ),
            )

        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            actor.tenant_id,
            session_id,
            lock=True,
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        if session.status != AcademicSessionStatus.OPEN or not session.is_current:
            raise ConflictException("Only the current open session can be closed.")
        if session.next_academic_session_id is None:
            raise BadRequestException(
                "Configure the next academic session before closing this one."
            )
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            actor.tenant_id,
            session.next_academic_session_id,
            lock=True,
        )
        if next_session is None or not next_session.is_active:
            raise NotFoundException("The configured next academic session is unavailable.")
        if next_session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException("The next academic session must still be a draft.")

        classrooms = await AcademicSessionLifecycleService._validate_progression_chain(
            db,
            tenant_id=actor.tenant_id,
        )
        now = _utc_now()
        session.status = AcademicSessionStatus.CLOSING
        session.closing_started_at = now
        await AcademicSessionLifecycleRepository.save(db, session)

        run = await StudentProgressionRunRepository.add(
            db,
            StudentProgressionRun(
                tenant_id=actor.tenant_id,
                academic_session_id=session.id,
                next_academic_session_id=next_session.id,
                idempotency_key=payload.idempotency_key,
                status=StudentProgressionRunStatus.PROCESSING,
                started_at=now,
                initiated_by_admin_id=actor.id,
            ),
        )

        promoted = graduated = skipped = failed = 0
        total = 0
        parent_membership_ids: set[UUID] = set()

        for classroom in classrooms.values():
            enrollments = await StudentEnrollmentRepository.list_current_for_class_session(
                db,
                actor.tenant_id,
                classroom.id,
                session.id,
                lock=True,
            )
            for enrollment in enrollments:
                total += 1
                student = await StudentRepository.get_by_id(
                    db,
                    actor.tenant_id,
                    enrollment.student_id,
                    lock=True,
                    include_archived=True,
                )
                if (
                    student is None
                    or student.is_archived
                    or student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}
                    or student.promotion_hold
                ):
                    skipped += 1
                    await StudentProgressionItemRepository.add(
                        db,
                        StudentProgressionItem(
                            tenant_id=actor.tenant_id,
                            progression_run_id=run.id,
                            student_id=enrollment.student_id,
                            from_enrollment_id=enrollment.id,
                            from_class_id=classroom.id,
                            action=StudentProgressionItemAction.SKIP,
                            status=StudentProgressionItemStatus.SKIPPED,
                            reason="Student is archived, inactive, or on promotion hold.",
                            processed_at=_utc_now(),
                        ),
                    )
                    continue

                if classroom.is_terminal:
                    parent_membership_ids.update(
                        await AcademicSessionLifecycleService._graduate_student(
                            db,
                            actor=actor,
                            student=student,
                            enrollment=enrollment,
                            effective_date=payload.effective_date,
                            reason=payload.reason,
                        )
                    )
                    graduated += 1
                    await StudentProgressionItemRepository.add(
                        db,
                        StudentProgressionItem(
                            tenant_id=actor.tenant_id,
                            progression_run_id=run.id,
                            student_id=student.id,
                            from_enrollment_id=enrollment.id,
                            from_class_id=classroom.id,
                            action=StudentProgressionItemAction.GRADUATE,
                            status=StudentProgressionItemStatus.GRADUATED,
                            reason=payload.reason,
                            processed_at=_utc_now(),
                        ),
                    )
                    continue

                target_class = classrooms.get(classroom.next_class_id)
                if target_class is None:
                    failed += 1
                    await StudentProgressionItemRepository.add(
                        db,
                        StudentProgressionItem(
                            tenant_id=actor.tenant_id,
                            progression_run_id=run.id,
                            student_id=student.id,
                            from_enrollment_id=enrollment.id,
                            from_class_id=classroom.id,
                            action=StudentProgressionItemAction.PROMOTE,
                            status=StudentProgressionItemStatus.FAILED,
                            reason="Next class mapping disappeared during progression.",
                            processed_at=_utc_now(),
                        ),
                    )
                    continue

                next_enrollment = await AcademicSessionLifecycleService._promote_student(
                    db,
                    actor=actor,
                    student=student,
                    enrollment=enrollment,
                    target_class=target_class,
                    next_session=next_session,
                    effective_date=payload.effective_date,
                    reason=payload.reason,
                )
                promoted += 1
                await StudentProgressionItemRepository.add(
                    db,
                    StudentProgressionItem(
                        tenant_id=actor.tenant_id,
                        progression_run_id=run.id,
                        student_id=student.id,
                        from_enrollment_id=enrollment.id,
                        to_enrollment_id=next_enrollment.id,
                        from_class_id=classroom.id,
                        to_class_id=target_class.id,
                        action=StudentProgressionItemAction.PROMOTE,
                        status=StudentProgressionItemStatus.PROMOTED,
                        reason=payload.reason,
                        processed_at=_utc_now(),
                    ),
                )

        for membership_id in parent_membership_ids:
            membership = await ParentMembershipRepository.get_by_id(
                db,
                membership_id,
                tenant_id=actor.tenant_id,
                lock=True,
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(
                    db,
                    membership,
                )

        completed_at = _utc_now()
        run.total_students = total
        run.promoted_students = promoted
        run.graduated_students = graduated
        run.skipped_students = skipped
        run.failed_students = failed
        run.status = (
            StudentProgressionRunStatus.FAILED
            if failed > 0
            else StudentProgressionRunStatus.COMPLETED
        )
        run.failure_reason = (
            "One or more students could not be progressed."
            if failed > 0
            else None
        )
        run.completed_at = completed_at
        await StudentProgressionRunRepository.save(db, run)

        session.status = AcademicSessionStatus.CLOSED
        session.is_current = False
        session.is_active = False
        session.closed_at = completed_at
        session.closed_by_admin_id = actor.id
        await AcademicSessionLifecycleRepository.save(db, session)

        next_session.status = AcademicSessionStatus.OPEN
        next_session.is_current = True
        next_session.is_active = True
        next_session.closing_started_at = None
        next_session.closed_at = None
        next_session.closed_by_admin_id = None
        await AcademicSessionLifecycleRepository.save(db, next_session)

        await db.commit()
        await db.refresh(session)
        await db.refresh(next_session)
        await db.refresh(run)
        return AcademicSessionCloseResponse(
            closed_session=AcademicSessionResponse.model_validate(session),
            opened_session=AcademicSessionResponse.model_validate(next_session),
            progression_run=await AcademicSessionLifecycleService._run_response(db, run),
        )

    @staticmethod
    async def get_progression_run(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        run_id: UUID,
    ) -> StudentProgressionRunDetailResponse:
        run = await StudentProgressionRunRepository.get_by_id(
            db,
            actor.tenant_id,
            run_id,
        )
        if run is None:
            raise NotFoundException("Progression run not found.")
        return await AcademicSessionLifecycleService._run_response(db, run)
