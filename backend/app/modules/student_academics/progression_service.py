"""Idempotent academic-session closure and student progression workflow."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.models import ClassRoom
from app.modules.classes.repository import ClassRoomRepository
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
    StudentProgressionRunStatus,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.student_academics.schemas import (
    AcademicSessionCloseResponse,
    AcademicSessionResponse,
    StudentProgressionItemResponse,
    StudentProgressionRunDetailResponse,
    StudentProgressionRunResponse,
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


class AcademicProgressionService:
    """Open sessions and close them with one atomic progression run."""

    @staticmethod
    async def open_session(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ) -> AcademicSessionResponse:
        try:
            session = await AcademicSessionLifecycleRepository.get_by_id(
                db,
                actor.tenant_id,
                session_id,
                lock=True,
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
                db,
                actor.tenant_id,
                session.id,
            )
            if not preview.can_open:
                StudentAcademicService._raise_dependency_conflict(
                    "Academic session has blockers and cannot be opened.",
                    preview,
                )

            current = await AcademicSessionLifecycleRepository.get_current_open(
                db,
                actor.tenant_id,
                lock=True,
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
            try:
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
            except IntegrityError as exc:
                await db.rollback()
                raise ConflictException(
                    "Close the current academic session before opening another."
                ) from exc
            await db.commit()
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
        rows = (
            await db.execute(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.academic_session_id == academic_session_id,
                    StudentEnrollment.is_current.is_(True),
                )
                .order_by(StudentEnrollment.student_id)
                .with_for_update()
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    async def _validate_class_graph(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollments: list[StudentEnrollment],
    ) -> dict[uuid.UUID, ClassRoom]:
        graph: dict[uuid.UUID, ClassRoom] = {}
        for class_id in {row.class_id for row in enrollments}:
            classroom = await ClassRoomRepository.get_by_id(
                db,
                tenant_id,
                class_id,
                lock=True,
            )
            if classroom is None:
                raise ConflictException(
                    f"Enrollment references missing class {class_id}."
                )

            if classroom.is_terminal:
                if classroom.next_class_id is not None:
                    raise ConflictException(
                        f"Terminal class {classroom.name} cannot have a next class."
                    )
            else:
                if classroom.next_class_id is None:
                    raise ConflictException(
                        f"Configure the next class for {classroom.name} before closure."
                    )
                next_class = await ClassRoomRepository.get_by_id(
                    db,
                    tenant_id,
                    classroom.next_class_id,
                    lock=True,
                )
                if (
                    next_class is None
                    or not next_class.is_active
                    or next_class.archived_at is not None
                ):
                    raise ConflictException(
                        f"The next class configured for {classroom.name} is unavailable."
                    )
                graph[next_class.id] = next_class

            graph[classroom.id] = classroom

        return graph

    @staticmethod
    async def _downgrade_graduated_parent_access(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> None:
        links = await StudentParentLinkRepository.list_for_student(
            db,
            tenant_id,
            student_id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
            ],
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
                db,
                membership_id,
                tenant_id=tenant_id,
                lock=True,
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(
                    db,
                    membership,
                )

    @staticmethod
    async def _progress_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        run: StudentProgressionRun,
        enrollment: StudentEnrollment,
        classroom: ClassRoom,
        graph: dict[uuid.UUID, ClassRoom],
        next_session: AcademicSession,
        effective_date: date,
    ) -> StudentProgressionItem:
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            enrollment.student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise ConflictException(
                f"Enrollment {enrollment.id} references a missing student."
            )

        if (
            student.is_archived
            or student.promotion_hold
            or student.status != AcademicStatus.ACTIVE
        ):
            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_class_id=classroom.id,
                    to_class_id=None,
                    action=StudentProgressionItemAction.SKIP,
                    status=StudentProgressionItemStatus.SKIPPED,
                    reason="Student is archived, on promotion hold, or not active.",
                    processed_at=_utc_now(),
                ),
            )

        enrollment.is_current = False
        enrollment.ended_on = effective_date
        enrollment.changed_by_admin_id = actor.id

        if classroom.is_terminal:
            enrollment.outcome = StudentEnrollmentOutcome.GRADUATED
            enrollment.reason = "Automatic terminal-class graduation"
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
            await AuthIdentityService.deactivate_for_actor(
                db,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
            )
            await AcademicProgressionService._downgrade_graduated_parent_access(
                db,
                tenant_id=actor.tenant_id,
                student_id=student.id,
            )

            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_class_id=classroom.id,
                    to_class_id=None,
                    action=StudentProgressionItemAction.GRADUATE,
                    status=StudentProgressionItemStatus.GRADUATED,
                    reason="Terminal class completed",
                    processed_at=_utc_now(),
                ),
            )

        target_class = graph[classroom.next_class_id]
        enrollment.outcome = StudentEnrollmentOutcome.PROMOTED
        enrollment.reason = "Automatic academic-session progression"
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
                reason="Automatic academic-session progression",
                changed_by_admin_id=actor.id,
            ),
        )
        student.class_id = target_class.id
        student.arm = target_class.arm
        await StudentRepository.save(db, student)

        return await StudentProgressionRepository.add_item(
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
                reason="Promoted to configured next class",
                processed_at=_utc_now(),
            ),
        )

    @staticmethod
    async def close_and_progress(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
        idempotency_key: str,
    ) -> AcademicSessionCloseResponse:
        completed_run_id: uuid.UUID | None = None

        try:
            session = await AcademicSessionLifecycleRepository.get_by_id(
                db,
                actor.tenant_id,
                session_id,
                lock=True,
            )
            if session is None:
                raise NotFoundException("Academic session not found.")

            existing = (
                await StudentProgressionRepository.get_run_by_idempotency_key(
                    db,
                    actor.tenant_id,
                    idempotency_key,
                    lock=True,
                )
            )
            if existing is None:
                existing = await StudentProgressionRepository.get_run_by_session(
                    db,
                    actor.tenant_id,
                    session.id,
                    lock=True,
                )

            if (
                existing is not None
                and existing.status == StudentProgressionRunStatus.COMPLETED
            ):
                completed_run_id = existing.id
            else:
                if (
                    session.status != AcademicSessionStatus.OPEN
                    or not session.is_current
                ):
                    raise ConflictException(
                        "Only the current open session can be closed."
                    )
                if session.next_academic_session_id is None:
                    raise BadRequestException(
                        "Configure next_academic_session_id before closure."
                    )
                preview = await StudentAcademicService.academic_session_dependency_preview(
                    db,
                    actor.tenant_id,
                    session.id,
                )
                if not preview.can_progress:
                    StudentAcademicService._raise_dependency_conflict(
                        "Academic session has blockers and cannot be closed.",
                        preview,
                    )

                next_session = await AcademicSessionLifecycleRepository.get_by_id(
                    db,
                    actor.tenant_id,
                    session.next_academic_session_id,
                    lock=True,
                )
                if next_session is None:
                    raise NotFoundException("Next academic session not found.")
                if next_session.status != AcademicSessionStatus.DRAFT:
                    raise ConflictException(
                        "The next academic session must still be draft."
                    )
                if (
                    existing is not None
                    and existing.idempotency_key != idempotency_key
                ):
                    raise ConflictException(
                        "This academic session already has a progression run."
                    )

                enrollments = (
                    await AcademicProgressionService._load_progression_enrollments(
                        db,
                        tenant_id=actor.tenant_id,
                        academic_session_id=session.id,
                    )
                )
                graph = await AcademicProgressionService._validate_class_graph(
                    db,
                    tenant_id=actor.tenant_id,
                    enrollments=enrollments,
                )

                if existing is None:
                    run = await StudentProgressionRepository.add_run(
                        db,
                        StudentProgressionRun(
                            tenant_id=actor.tenant_id,
                            academic_session_id=session.id,
                            next_academic_session_id=next_session.id,
                            idempotency_key=idempotency_key,
                            status=StudentProgressionRunStatus.PROCESSING,
                            total_students=len(enrollments),
                            started_at=_utc_now(),
                            initiated_by_admin_id=actor.id,
                        ),
                    )
                else:
                    run = existing
                    await db.execute(
                        delete(StudentProgressionItem).where(
                            StudentProgressionItem.progression_run_id == run.id
                        )
                    )
                    run.status = StudentProgressionRunStatus.PROCESSING
                    run.total_students = len(enrollments)
                    run.promoted_students = 0
                    run.graduated_students = 0
                    run.skipped_students = 0
                    run.failed_students = 0
                    run.started_at = _utc_now()
                    run.completed_at = None
                    run.failure_reason = None
                    run.initiated_by_admin_id = actor.id
                    await StudentProgressionRepository.save_run(db, run)

                previous_status = session.status
                session.status = AcademicSessionStatus.CLOSING
                session.closing_started_at = _utc_now()
                await AcademicSessionLifecycleRepository.save(db, session)
                await StudentAcademicService._record_academic_lifecycle(
                    db,
                    tenant_id=actor.tenant_id,
                    entity_type="session",
                    entity_id=session.id,
                    action="closing_started",
                    previous_status=previous_status.value,
                    new_status=session.status.value,
                    acting_admin_id=actor.id,
                    metadata={"progression_run_id": str(run.id)},
                )

                effective_date = session.end_date or date.today()
                for enrollment in enrollments:
                    classroom = graph[enrollment.class_id]
                    item = await AcademicProgressionService._progress_student(
                        db,
                        actor=actor,
                        run=run,
                        enrollment=enrollment,
                        classroom=classroom,
                        graph=graph,
                        next_session=next_session,
                        effective_date=effective_date,
                    )
                    if item.status == StudentProgressionItemStatus.PROMOTED:
                        run.promoted_students += 1
                    elif item.status == StudentProgressionItemStatus.GRADUATED:
                        run.graduated_students += 1
                    elif item.status == StudentProgressionItemStatus.SKIPPED:
                        run.skipped_students += 1

                now = _utc_now()
                previous_status = session.status
                session.status = AcademicSessionStatus.CLOSED
                session.is_current = False
                session.closed_at = now
                session.closed_by_admin_id = actor.id
                await AcademicSessionLifecycleRepository.save(db, session)
                await StudentAcademicService._record_academic_lifecycle(
                    db,
                    tenant_id=actor.tenant_id,
                    entity_type="session",
                    entity_id=session.id,
                    action="closed",
                    previous_status=previous_status.value,
                    new_status=session.status.value,
                    acting_admin_id=actor.id,
                    metadata={"progression_run_id": str(run.id)},
                )

                previous_next_status = next_session.status
                next_session.status = AcademicSessionStatus.OPEN
                next_session.is_current = True
                next_session.closing_started_at = None
                next_session.closed_at = None
                next_session.closed_by_admin_id = None
                await AcademicSessionLifecycleRepository.save(db, next_session)
                await StudentAcademicService._record_academic_lifecycle(
                    db,
                    tenant_id=actor.tenant_id,
                    entity_type="session",
                    entity_id=next_session.id,
                    action="opened",
                    previous_status=previous_next_status.value,
                    new_status=next_session.status.value,
                    acting_admin_id=actor.id,
                    metadata={"opened_by_progression_run_id": str(run.id)},
                )

                run.status = StudentProgressionRunStatus.COMPLETED
                run.completed_at = now
                await StudentProgressionRepository.save_run(db, run)
                completed_run_id = run.id
                await db.commit()

        except (BadRequestException, ConflictException, NotFoundException):
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            failed = (
                await StudentProgressionRepository.get_run_by_idempotency_key(
                    db,
                    actor.tenant_id,
                    idempotency_key,
                    lock=True,
                )
            )
            if failed is None:
                session = await AcademicSessionLifecycleRepository.get_by_id(
                    db,
                    actor.tenant_id,
                    session_id,
                )
                if (
                    session is not None
                    and session.next_academic_session_id is not None
                ):
                    failed = await StudentProgressionRepository.add_run(
                        db,
                        StudentProgressionRun(
                            tenant_id=actor.tenant_id,
                            academic_session_id=session.id,
                            next_academic_session_id=(
                                session.next_academic_session_id
                            ),
                            idempotency_key=idempotency_key,
                            status=StudentProgressionRunStatus.FAILED,
                            total_students=0,
                            failed_students=1,
                            started_at=_utc_now(),
                            completed_at=_utc_now(),
                            initiated_by_admin_id=actor.id,
                            failure_reason=str(exc)[:1000],
                        ),
                    )
                    await StudentAcademicService._record_academic_lifecycle(
                        db,
                        tenant_id=actor.tenant_id,
                        entity_type="session",
                        entity_id=session.id,
                        action="progression_failed",
                        previous_status=session.status.value,
                        new_status=session.status.value,
                        acting_admin_id=actor.id,
                        reason=str(exc)[:500],
                        metadata={"progression_run_id": str(failed.id)},
                    )
            elif failed.status != StudentProgressionRunStatus.COMPLETED:
                failed.status = StudentProgressionRunStatus.FAILED
                failed.completed_at = _utc_now()
                failed.failed_students = max(failed.failed_students, 1)
                failed.failure_reason = str(exc)[:1000]
                await StudentProgressionRepository.save_run(db, failed)
                await StudentAcademicService._record_academic_lifecycle(
                    db,
                    tenant_id=actor.tenant_id,
                    entity_type="session",
                    entity_id=failed.academic_session_id,
                    action="progression_failed",
                    previous_status=None,
                    new_status=None,
                    acting_admin_id=actor.id,
                    reason=str(exc)[:500],
                    metadata={"progression_run_id": str(failed.id)},
                )
            await db.commit()
            raise

        await AuthIdentityService.invalidate_after_commit(db)
        if completed_run_id is None:
            raise ConflictException("Progression run did not complete.")

        return await AcademicProgressionService.get_close_response(
            db,
            tenant_id=actor.tenant_id,
            progression_run_id=completed_run_id,
        )

    @staticmethod
    async def get_close_response(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        progression_run_id: uuid.UUID,
    ) -> AcademicSessionCloseResponse:
        run = await StudentProgressionRepository.get_run_by_id(
            db,
            tenant_id,
            progression_run_id,
        )
        if run is None:
            raise NotFoundException("Progression run not found.")

        items = await StudentProgressionRepository.list_items_for_run(
            db,
            tenant_id,
            run.id,
        )
        closed_session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            tenant_id,
            run.academic_session_id,
        )
        opened_session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            tenant_id,
            run.next_academic_session_id,
        )
        if closed_session is None or opened_session is None:
            raise ConflictException("Progression session records are incomplete.")

        run_summary = StudentProgressionRunResponse.model_validate(run)
        run_payload = StudentProgressionRunDetailResponse(
            **run_summary.model_dump(),
            items=[
                StudentProgressionItemResponse.model_validate(item)
                for item in items
            ],
        )

        return AcademicSessionCloseResponse(
            closed_session=AcademicSessionResponse.model_validate(closed_session),
            opened_session=AcademicSessionResponse.model_validate(opened_session),
            progression_run=run_payload,
        )
