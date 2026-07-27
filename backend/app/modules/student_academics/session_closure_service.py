"""Staged, auditable academic-session closure and background progression."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementStatus,
    AnnouncementTarget,
    AnnouncementTargetType,
)
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
    StudentProgressionRepository,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
    StudentProgressionRunStatus,
)
from app.modules.student_academics.progression_service import AcademicProgressionService
from app.modules.student_academics.schemas import (
    AcademicSessionResponse,
    StudentProgressionItemResponse,
    StudentProgressionRunDetailResponse,
    StudentProgressionRunResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.student_academics.session_closure_schemas import (
    SessionClosureAuditResponse,
    SessionClosureFinalizeResponse,
    SessionClosureStartResponse,
    SessionClosureStatusResponse,
)
from app.modules.students.models import StudentEnrollment
from app.modules.tenant_admins.models import TenantAdmin


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionClosureService:
    """Own the OPEN -> CLOSING -> CLOSED lifecycle and progression hand-off."""

    CHECKED_ITEMS = [
        "A next draft academic session is configured.",
        "Every term in the current session is closed.",
        "No result remains draft, submitted, or approved-but-unlocked.",
        "No draft report card remains unpublished.",
        "No assessment-record import is pending or processing.",
        "Every enrolled non-terminal class has an active next-class target.",
        "Terminal classes do not point to another class.",
        "The next session has at least one configured term.",
        "No progression run is already processing.",
    ]

    @staticmethod
    async def _run_detail(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run: StudentProgressionRun | None,
    ) -> StudentProgressionRunDetailResponse | None:
        if run is None:
            return None
        items = await StudentProgressionRepository.list_items_for_run(
            db, tenant_id, run.id
        )
        summary = StudentProgressionRunResponse.model_validate(run)
        return StudentProgressionRunDetailResponse(
            **summary.model_dump(),
            items=[StudentProgressionItemResponse.model_validate(item) for item in items],
        )

    @staticmethod
    async def _current_enrollments(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        lock: bool = False,
    ) -> list[StudentEnrollment]:
        query = (
            select(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_session_id == session_id,
                StudentEnrollment.is_current.is_(True),
            )
            .order_by(StudentEnrollment.student_id.asc())
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def audit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> SessionClosureAuditResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, session_id
        )
        if session is None:
            raise NotFoundException("Academic session not found.")

        preview = await StudentAcademicService.academic_session_dependency_preview(
            db, tenant_id, session_id
        )
        counts = dict(preview.dependency_counts)
        blockers = list(preview.blocker_messages)
        counts.setdefault("invalid_class_progression_targets", 0)
        counts.setdefault("next_session_terms", 0)

        next_session = None
        if session.next_academic_session_id is not None:
            next_session = await AcademicSessionLifecycleRepository.get_by_id(
                db, tenant_id, session.next_academic_session_id
            )
            if next_session is None:
                blockers.append("The configured next academic session no longer exists.")
            elif next_session.status != AcademicSessionStatus.DRAFT:
                blockers.append("The next academic session must remain in draft until final closure.")
            else:
                terms = list(
                    (
                        await db.execute(
                            select(AcademicTerm).where(
                                AcademicTerm.tenant_id == tenant_id,
                                AcademicTerm.academic_session_id == next_session.id,
                            )
                        )
                    ).scalars().all()
                )
                counts["next_session_terms"] = len(terms)
                if not terms:
                    blockers.append("Create at least one term in the next session before starting closure.")

        enrollments = await SessionClosureService._current_enrollments(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        invalid_targets = 0
        checked_classes: set[uuid.UUID] = set()
        for enrollment in enrollments:
            if enrollment.class_id in checked_classes:
                continue
            checked_classes.add(enrollment.class_id)
            classroom = await ClassRoomRepository.get_by_id(
                db, tenant_id, enrollment.class_id
            )
            if classroom is None:
                invalid_targets += 1
                blockers.append(
                    f"An active enrollment references missing class {enrollment.class_id}."
                )
                continue
            if classroom.is_terminal:
                if classroom.next_class_id is not None:
                    invalid_targets += 1
                    blockers.append(
                        f"Terminal class {classroom.name} must not have a next-class target."
                    )
                continue
            if classroom.next_class_id is None:
                invalid_targets += 1
                blockers.append(
                    f"Configure a next-class target for {classroom.name}."
                )
                continue
            target = await ClassRoomRepository.get_by_id(
                db, tenant_id, classroom.next_class_id
            )
            if target is None or not target.is_active or target.archived_at is not None:
                invalid_targets += 1
                blockers.append(
                    f"The next-class target configured for {classroom.name} is unavailable."
                )
        counts["invalid_class_progression_targets"] = invalid_targets

        # De-duplicate while preserving the exact audit order.
        blockers = list(dict.fromkeys(blockers))
        ready_status = session.status in {
            AcademicSessionStatus.OPEN,
            AcademicSessionStatus.CLOSING,
        }
        is_ready = ready_status and not blockers
        return SessionClosureAuditResponse(
            session_id=session.id,
            is_ready=is_ready,
            dependency_counts=counts,
            blocker_messages=blockers,
            checked_items=list(SessionClosureService.CHECKED_ITEMS),
        )

    @staticmethod
    async def _broadcast(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        title: str,
        body: str,
        priority: AnnouncementPriority = AnnouncementPriority.HIGH,
    ) -> None:
        announcement = Announcement(
            tenant_id=tenant_id,
            title=title,
            body=body,
            category=AnnouncementCategory.SYSTEM,
            priority=priority,
            status=AnnouncementStatus.PUBLISHED,
            created_by_actor_type=AnnouncementActorType.TENANT_ADMIN,
            created_by_actor_id=actor_id,
            publish_at=_utc_now(),
            is_pinned=True,
        )
        db.add(announcement)
        await db.flush()
        db.add(
            AnnouncementTarget(
                tenant_id=tenant_id,
                announcement_id=announcement.id,
                target_type=AnnouncementTargetType.ALL,
            )
        )
        await db.flush()

    @staticmethod
    async def start_closing(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
        idempotency_key: str,
    ) -> SessionClosureStartResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, actor.tenant_id, session_id, lock=True
        )
        if session is None:
            raise NotFoundException("Academic session not found.")

        audit = await SessionClosureService.audit(
            db, tenant_id=actor.tenant_id, session_id=session.id
        )
        existing = await StudentProgressionRepository.get_run_by_session(
            db, actor.tenant_id, session.id, lock=True
        )
        if session.status == AcademicSessionStatus.CLOSING and existing is not None:
            return SessionClosureStartResponse(
                started=True,
                session=AcademicSessionResponse.model_validate(session),
                audit=audit,
                progression_run=await SessionClosureService._run_detail(
                    db, tenant_id=actor.tenant_id, run=existing
                ),
                queued=existing.status in {
                    StudentProgressionRunStatus.PENDING,
                    StudentProgressionRunStatus.PROCESSING,
                },
            )
        if session.status != AcademicSessionStatus.OPEN or not session.is_current:
            raise ConflictException("Only the current open session can enter closing.")
        if not audit.is_ready:
            return SessionClosureStartResponse(
                started=False,
                session=AcademicSessionResponse.model_validate(session),
                audit=audit,
                progression_run=await SessionClosureService._run_detail(
                    db, tenant_id=actor.tenant_id, run=existing
                ),
                queued=False,
            )
        if session.next_academic_session_id is None:
            raise ConflictException("Configure the next academic session first.")
        if existing is not None and existing.idempotency_key != idempotency_key:
            raise ConflictException("This session already has a progression run.")

        enrollments = await SessionClosureService._current_enrollments(
            db,
            tenant_id=actor.tenant_id,
            session_id=session.id,
        )
        if existing is None:
            run = await StudentProgressionRepository.add_run(
                db,
                StudentProgressionRun(
                    tenant_id=actor.tenant_id,
                    academic_session_id=session.id,
                    next_academic_session_id=session.next_academic_session_id,
                    idempotency_key=idempotency_key,
                    status=StudentProgressionRunStatus.PENDING,
                    total_students=len(enrollments),
                    initiated_by_admin_id=actor.id,
                ),
            )
        else:
            run = existing
            run.status = StudentProgressionRunStatus.PENDING
            run.total_students = len(enrollments)
            run.promoted_students = 0
            run.graduated_students = 0
            run.skipped_students = 0
            run.failed_students = 0
            run.started_at = None
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
            metadata={
                "progression_run_id": str(run.id),
                "closure_audit": audit.model_dump(mode="json"),
            },
        )
        await db.commit()
        await db.refresh(session)
        await db.refresh(run)

        from app.core.queue.arq import enqueue_session_progression_job

        queued = await enqueue_session_progression_job(
            run_id=str(run.id), tenant_id=str(actor.tenant_id)
        )
        if not queued:
            # A duplicate ARQ job id means the same run is already safely queued.
            queued = True

        return SessionClosureStartResponse(
            started=True,
            session=AcademicSessionResponse.model_validate(session),
            audit=audit,
            progression_run=await SessionClosureService._run_detail(
                db, tenant_id=actor.tenant_id, run=run
            ),
            queued=queued,
        )

    @staticmethod
    async def process_progression_run(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> dict[str, int | str]:
        run = await StudentProgressionRepository.get_run_by_id(
            db, tenant_id, run_id, lock=True
        )
        if run is None:
            raise NotFoundException("Progression run not found.")
        if run.status == StudentProgressionRunStatus.COMPLETED:
            return {"status": "completed", "processed": run.total_students}

        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, run.academic_session_id, lock=True
        )
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, run.next_academic_session_id, lock=True
        )
        if session is None or next_session is None:
            raise ConflictException("Progression session records are incomplete.")
        if session.status != AcademicSessionStatus.CLOSING:
            raise ConflictException("Progression can run only while the session is closing.")
        actor = (
            await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.id == run.initiated_by_admin_id,
                )
            )
        ).scalar_one_or_none()
        if actor is None:
            raise ConflictException("The administrator who started closure is unavailable.")

        run.status = StudentProgressionRunStatus.PROCESSING
        run.started_at = run.started_at or _utc_now()
        run.completed_at = None
        run.failure_reason = None
        await StudentProgressionRepository.save_run(db, run)
        await db.commit()

        enrollments = await AcademicProgressionService._load_progression_enrollments(
            db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
        )
        graph = await AcademicProgressionService._validate_class_graph(
            db, tenant_id=tenant_id, enrollments=enrollments
        )
        run.total_students = len(enrollments)
        run.promoted_students = 0
        run.graduated_students = 0
        run.skipped_students = 0
        run.failed_students = 0
        effective_date = session.end_date or date.today()

        for enrollment in enrollments:
            try:
                async with db.begin_nested():
                    item = await AcademicProgressionService._progress_student(
                        db,
                        actor=actor,
                        run=run,
                        enrollment=enrollment,
                        classroom=graph[enrollment.class_id],
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
            except Exception as exc:  # one student must not corrupt the full batch
                run.failed_students += 1
                db.add(
                    StudentProgressionItem(
                        tenant_id=tenant_id,
                        progression_run_id=run.id,
                        student_id=enrollment.student_id,
                        from_enrollment_id=enrollment.id,
                        from_class_id=enrollment.class_id,
                        to_class_id=None,
                        action=StudentProgressionItemAction.SKIP,
                        status=StudentProgressionItemStatus.FAILED,
                        reason=str(exc)[:1000],
                        processed_at=_utc_now(),
                    )
                )
                await db.flush()

        run.status = (
            StudentProgressionRunStatus.FAILED
            if run.failed_students > 0
            else StudentProgressionRunStatus.COMPLETED
        )
        run.completed_at = _utc_now()
        run.failure_reason = (
            f"{run.failed_students} student progression item(s) failed."
            if run.failed_students
            else None
        )
        await StudentProgressionRepository.save_run(db, run)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="session",
            entity_id=session.id,
            action="progression_failed" if run.failed_students else "progression_completed",
            previous_status=session.status.value,
            new_status=session.status.value,
            acting_admin_id=actor.id,
            reason=run.failure_reason,
            metadata={
                "progression_run_id": str(run.id),
                "promoted": run.promoted_students,
                "graduated": run.graduated_students,
                "skipped": run.skipped_students,
                "failed": run.failed_students,
            },
        )
        await SessionClosureService._broadcast(
            db,
            tenant_id=tenant_id,
            actor_id=actor.id,
            title=(
                "Academic session closing requires attention"
                if run.failed_students
                else "Academic session is closing"
            ),
            body=(
                f"Student progression finished with {run.failed_students} failure(s). "
                "The session remains in closing while the administrator reviews the audit."
                if run.failed_students
                else (
                    f"Student progression is complete: {run.promoted_students} promoted, "
                    f"{run.graduated_students} graduated and {run.skipped_students} skipped. "
                    "Academic write activities remain paused until the administrator finalizes closure."
                )
            ),
            priority=(
                AnnouncementPriority.URGENT
                if run.failed_students
                else AnnouncementPriority.HIGH
            ),
        )
        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)
        return {
            "status": run.status.value,
            "processed": run.total_students,
            "promoted": run.promoted_students,
            "graduated": run.graduated_students,
            "skipped": run.skipped_students,
            "failed": run.failed_students,
        }

    @staticmethod
    async def status(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> SessionClosureStatusResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, session_id
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        run = await StudentProgressionRepository.get_run_by_session(
            db, tenant_id, session.id
        )
        audit = await SessionClosureService.audit(
            db, tenant_id=tenant_id, session_id=session.id
        )
        can_finalize = bool(
            session.status == AcademicSessionStatus.CLOSING
            and run is not None
            and run.status == StudentProgressionRunStatus.COMPLETED
            and run.failed_students == 0
        )
        return SessionClosureStatusResponse(
            session=AcademicSessionResponse.model_validate(session),
            audit=audit,
            progression_run=await SessionClosureService._run_detail(
                db, tenant_id=tenant_id, run=run
            ),
            can_finalize=can_finalize,
            writes_paused=session.status == AcademicSessionStatus.CLOSING,
        )

    @staticmethod
    async def retry(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ) -> SessionClosureStatusResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, actor.tenant_id, session_id
        )
        run = await StudentProgressionRepository.get_run_by_session(
            db, actor.tenant_id, session_id, lock=True
        )
        if session is None or run is None:
            raise NotFoundException("Session progression run not found.")
        if session.status != AcademicSessionStatus.CLOSING:
            raise ConflictException("Only a closing session can retry progression.")
        if run.status not in {
            StudentProgressionRunStatus.FAILED,
            StudentProgressionRunStatus.PENDING,
        }:
            raise ConflictException("Only failed or pending progression can be retried.")
        run.status = StudentProgressionRunStatus.PENDING
        run.completed_at = None
        run.failure_reason = None
        run.initiated_by_admin_id = actor.id
        await StudentProgressionRepository.save_run(db, run)
        await db.commit()
        from app.core.queue.arq import enqueue_session_progression_job

        await enqueue_session_progression_job(
            run_id=str(run.id), tenant_id=str(actor.tenant_id), retry=True
        )
        return await SessionClosureService.status(
            db, tenant_id=actor.tenant_id, session_id=session_id
        )

    @staticmethod
    async def finalize(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ) -> SessionClosureFinalizeResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, actor.tenant_id, session_id, lock=True
        )
        run = await StudentProgressionRepository.get_run_by_session(
            db, actor.tenant_id, session_id, lock=True
        )
        if session is None or run is None:
            raise NotFoundException("Session progression records were not found.")
        if session.status != AcademicSessionStatus.CLOSING:
            raise ConflictException("Only a closing session can be finalized.")
        if run.status != StudentProgressionRunStatus.COMPLETED or run.failed_students:
            raise ConflictException(
                "Progression must complete without failures before final closure."
            )
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db, actor.tenant_id, run.next_academic_session_id, lock=True
        )
        if next_session is None or next_session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException("The next session is missing or is no longer draft.")

        now = _utc_now()
        session.status = AcademicSessionStatus.CLOSED
        session.is_current = False
        session.closed_at = now
        session.closed_by_admin_id = actor.id
        await AcademicSessionLifecycleRepository.save(db, session)

        next_session.status = AcademicSessionStatus.OPEN
        next_session.is_current = True
        next_session.closing_started_at = None
        next_session.closed_at = None
        next_session.closed_by_admin_id = None
        await AcademicSessionLifecycleRepository.save(db, next_session)

        next_terms = list(
            (
                await db.execute(
                    select(AcademicTerm)
                    .where(
                        AcademicTerm.tenant_id == actor.tenant_id,
                        AcademicTerm.academic_session_id == next_session.id,
                    )
                    .order_by(
                        AcademicTerm.start_date.asc().nulls_last(),
                        AcademicTerm.created_at.asc(),
                    )
                    .with_for_update()
                )
            ).scalars().all()
        )
        if not next_terms:
            raise ConflictException("The next session has no term to open.")
        first_term = next_terms[0]
        if first_term.status == AcademicTermStatus.DRAFT:
            first_term.status = AcademicTermStatus.OPEN
            first_term.is_current = True
            first_term.opened_at = now
            first_term.closed_at = None
            first_term.opened_by_admin_id = actor.id
            db.add(first_term)

        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="session",
            entity_id=session.id,
            action="closed",
            previous_status=AcademicSessionStatus.CLOSING.value,
            new_status=AcademicSessionStatus.CLOSED.value,
            acting_admin_id=actor.id,
            metadata={"progression_run_id": str(run.id)},
        )
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="session",
            entity_id=next_session.id,
            action="opened_after_progression",
            previous_status=AcademicSessionStatus.DRAFT.value,
            new_status=AcademicSessionStatus.OPEN.value,
            acting_admin_id=actor.id,
            metadata={"progression_run_id": str(run.id)},
        )
        await SessionClosureService._broadcast(
            db,
            tenant_id=actor.tenant_id,
            actor_id=actor.id,
            title=f"{next_session.name} academic session has begun",
            body=(
                f"{session.name} has been closed. {next_session.name} is now active and "
                "the first configured term has opened. Academic write activities have resumed."
            ),
            priority=AnnouncementPriority.HIGH,
        )
        await db.commit()
        await db.refresh(session)
        await db.refresh(next_session)
        return SessionClosureFinalizeResponse(
            closed_session=AcademicSessionResponse.model_validate(session),
            opened_session=AcademicSessionResponse.model_validate(next_session),
            progression_run=await SessionClosureService._run_detail(
                db, tenant_id=actor.tenant_id, run=run
            ),
        )
