"""Staged, auditable academic-session closure and background progression."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.models import AcademicLevelStatus
from app.modules.classes.repository import AcademicLevelRepository
from app.modules.communications.enums import (
    AnnouncementPriority,
    CommunicationActorType,
    NotificationSourceType,
)
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import ResolvedRecipient
from app.modules.realtime.publisher import RealtimePublisher
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
    StudentProgressionRepository,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
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

    # The heavy worker has a one-hour job timeout. Give ARQ a small grace period
    # before a PROCESSING run is considered abandoned and manually recoverable.
    PROCESSING_STALE_AFTER = timedelta(minutes=65)

    CHECKED_ITEMS = [
        "A next draft academic session is configured.",
        "The current and next academic sessions have complete non-overlapping date ranges.",
        "Every term in the current session is closed.",
        "No result remains draft, submitted, or approved-but-unlocked.",
        "No draft report card remains unpublished.",
        "No assessment-record import is pending or processing.",
        "Every current enrollment references an active academic level.",
        "Level category and position determine progression automatically.",
        "Every non-terminal level has a configured next progression level.",
        "Terminal completion is explicitly confirmed before graduation is applied.",
        "The next session has at least one configured term.",
        "No progression run is already processing.",
    ]

    @staticmethod
    async def _publish_progression_event(
        *,
        run: StudentProgressionRun,
        event_type: str,
    ) -> None:
        if run.initiated_by_admin_id is None:
            return
        await RealtimePublisher.to_actor(
            event_type=event_type,
            actor_type="tenant_admin",
            actor_id=run.initiated_by_admin_id,
            tenant_id=run.tenant_id,
            data={
                "session_id": str(run.academic_session_id),
                "progression_run_id": str(run.id),
                "status": run.status.value,
            },
        )

    @staticmethod
    def _summarize_progression_items(
        items: list[StudentProgressionItem],
    ) -> dict[str, int]:
        summary = {
            "promoted": 0,
            "graduated": 0,
            "skipped": 0,
            "pending": 0,
            "failed": 0,
        }
        for item in items:
            if (
                item.status == StudentProgressionItemStatus.COMPLETED
                and item.action == StudentProgressionItemAction.COMPLETE
            ):
                summary["graduated"] += 1
            elif item.status == StudentProgressionItemStatus.COMPLETED:
                summary["promoted"] += 1
            elif item.status == StudentProgressionItemStatus.CANCELLED:
                summary["skipped"] += 1
            else:
                summary["failed"] += 1
        return summary

    @staticmethod
    def _next_session_date_blockers(
        *,
        session: AcademicSession,
        next_session: AcademicSession,
    ) -> list[str]:
        blockers: list[str] = []
        if session.start_date is None or session.end_date is None:
            blockers.append(
                "The current academic session must have complete start and end dates before closure."
            )
        if next_session.start_date is None or next_session.end_date is None:
            blockers.append(
                "The next academic session must have complete start and end dates before closure."
            )
            return blockers
        if next_session.end_date <= next_session.start_date:
            blockers.append("The next academic session end date must be after its start date.")
        if session.end_date is not None and next_session.start_date <= session.end_date:
            blockers.append(
                "The next academic session must start after the current academic session ends."
            )
        return blockers

    @staticmethod
    def _processing_is_stale(
        run: StudentProgressionRun,
        *,
        now: datetime | None = None,
    ) -> bool:
        if run.status != StudentProgressionRunStatus.PROCESSING:
            return False
        if run.started_at is None:
            return True
        reference = now or _utc_now()
        started_at = run.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return started_at <= reference - SessionClosureService.PROCESSING_STALE_AFTER

    @staticmethod
    async def _enqueue_progression_safely(
        *,
        run: StudentProgressionRun,
        tenant_id: uuid.UUID,
        retry: bool = False,
    ) -> bool:
        """Dispatch progression without turning a committed CLOSING state into a 500.

        ARQ returns ``None`` when the deterministic job id already exists. That is
        still a successful hand-off for the initial request. Connectivity/runtime
        exceptions are the meaningful failure signal and leave the durable run in
        PENDING so a repeated start/retry request can dispatch it again.
        """

        from app.core.queue.arq import enqueue_session_progression_job

        try:
            queued = await enqueue_session_progression_job(
                run_id=str(run.id),
                tenant_id=str(tenant_id),
                retry=retry,
            )
        except Exception:
            return False
        return bool(queued) or not retry

    @staticmethod
    async def _run_detail(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        run: StudentProgressionRun | None,
    ) -> StudentProgressionRunDetailResponse | None:
        if run is None:
            return None
        items = await StudentProgressionRepository.list_items_for_run(db, tenant_id, run.id)
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
        session = await AcademicSessionLifecycleRepository.get_by_id(db, tenant_id, session_id)
        if session is None:
            raise NotFoundException("Academic session not found.")

        preview = await StudentAcademicService.academic_session_dependency_preview(
            db, tenant_id, session_id
        )
        counts = dict(preview.dependency_counts)
        blockers = list(preview.blocker_messages)
        counts.setdefault("invalid_class_progression_targets", 0)
        counts.setdefault("manual_class_placement_routes", 0)
        counts.setdefault("next_session_terms", 0)
        counts.setdefault("terminal_students", 0)

        next_session = None
        if session.next_academic_session_id is not None:
            next_session = await AcademicSessionLifecycleRepository.get_by_id(
                db, tenant_id, session.next_academic_session_id
            )
            if next_session is None:
                blockers.append("The configured next academic session no longer exists.")
            elif next_session.status != AcademicSessionStatus.DRAFT:
                blockers.append(
                    "The next academic session must remain in draft until final closure."
                )
            else:
                blockers.extend(
                    SessionClosureService._next_session_date_blockers(
                        session=session,
                        next_session=next_session,
                    )
                )
                terms = list(
                    (
                        await db.execute(
                            select(AcademicTerm).where(
                                AcademicTerm.tenant_id == tenant_id,
                                AcademicTerm.academic_session_id == next_session.id,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                counts["next_session_terms"] = len(terms)
                if not terms:
                    blockers.append(
                        "Create at least one term in the next session before starting closure."
                    )

        enrollments = await SessionClosureService._current_enrollments(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        enrollment_counts_by_level: dict[uuid.UUID, int] = {}
        for enrollment in enrollments:
            enrollment_counts_by_level[enrollment.academic_level_id] = (
                enrollment_counts_by_level.get(enrollment.academic_level_id, 0) + 1
            )

        invalid_levels = 0
        invalid_progression_targets = 0
        terminal_students = 0
        for level_id, student_count in enrollment_counts_by_level.items():
            level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
            if level is None or level.status != AcademicLevelStatus.ACTIVE:
                invalid_levels += 1
                blockers.append(f"An active enrollment references invalid level {level_id}.")
                continue
            try:
                target_level = await AcademicProgressionService.resolve_next_level(
                    db,
                    tenant_id=tenant_id,
                    current_level=level,
                )
            except ConflictException:
                invalid_progression_targets += 1
                blockers.append(
                    f"{level.name} has no valid next progression level. Complete the academic level configuration before closing the session."
                )
                continue
            if target_level is None:
                terminal_students += student_count

        counts["invalid_enrollment_levels"] = invalid_levels
        counts["invalid_class_progression_targets"] = invalid_progression_targets
        counts["terminal_students"] = terminal_students

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
            terminal_students=terminal_students,
            requires_terminal_confirmation=terminal_students > 0,
        )

    @staticmethod
    async def _broadcast(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        actor_id: uuid.UUID,
        title: str,
        body: str,
        priority: str = "high",
    ) -> None:
        _ = priority
        await NotificationService.deliver_system_event(
            db,
            recipients=[
                ResolvedRecipient(
                    actor_type=CommunicationActorType.TENANT_ADMIN,
                    actor_id=actor_id,
                    tenant_id=tenant_id,
                    label="Tenant admin",
                )
            ],
            source_type=NotificationSourceType.ACADEMIC_LIFECYCLE,
            source_id=uuid.uuid4(),
            title=title,
            preview=body,
            action_path="/admin/academic/progression",
            tenant_id=tenant_id,
        )

    @staticmethod
    async def start_closing(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
        idempotency_key: str,
        allow_terminal_completion: bool = False,
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
            if existing.status == StudentProgressionRunStatus.PENDING:
                await db.commit()
                queued = await SessionClosureService._enqueue_progression_safely(
                    run=existing,
                    tenant_id=actor.tenant_id,
                )
            else:
                queued = existing.status == StudentProgressionRunStatus.PROCESSING
            return SessionClosureStartResponse(
                started=True,
                session=AcademicSessionResponse.model_validate(session),
                audit=audit,
                progression_run=await SessionClosureService._run_detail(
                    db, tenant_id=actor.tenant_id, run=existing
                ),
                queued=queued,
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
        if audit.requires_terminal_confirmation and not allow_terminal_completion:
            raise ConflictException(
                "Explicit confirmation is required before terminal students are graduated.",
                payload={
                    "dependency_counts": audit.dependency_counts,
                    "terminal_students": audit.terminal_students,
                    "requires_terminal_confirmation": True,
                },
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
                    terminal_completion_approved=bool(allow_terminal_completion),
                    status=StudentProgressionRunStatus.PENDING,
                    total_students=len(enrollments),
                    initiated_by_admin_id=actor.id,
                ),
            )
        else:
            run = existing
            run.status = StudentProgressionRunStatus.PENDING
            run.terminal_completion_approved = run.terminal_completion_approved or bool(
                allow_terminal_completion
            )
            if run.total_students == 0:
                run.total_students = len(enrollments)
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
                "terminal_completion_confirmed": run.terminal_completion_approved,
            },
        )
        await db.commit()
        await db.refresh(session)
        await db.refresh(run)

        queued = await SessionClosureService._enqueue_progression_safely(
            run=run,
            tenant_id=actor.tenant_id,
        )

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
        run = await StudentProgressionRepository.get_run_by_id(db, tenant_id, run_id, lock=True)
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
        if next_session.status != AcademicSessionStatus.DRAFT:
            raise ConflictException("The next academic session must remain draft during progression.")
        date_blockers = SessionClosureService._next_session_date_blockers(
            session=session,
            next_session=next_session,
        )
        if date_blockers:
            raise ConflictException(
                "Progression session dates are invalid.",
                payload={"blocker_messages": date_blockers},
            )
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

        # The worker trusts only the durable decision attached to this run. Audit
        # metadata mirrors the decision for traceability but is not the authority.
        terminal_completion_confirmed = bool(run.terminal_completion_approved)

        run.status = StudentProgressionRunStatus.PROCESSING
        run.started_at = run.started_at or _utc_now()
        run.completed_at = None
        run.failure_reason = None
        await StudentProgressionRepository.save_run(db, run)
        await db.commit()
        await SessionClosureService._publish_progression_event(
            run=run,
            event_type="academic_session.progression.started",
        )

        enrollments = await AcademicProgressionService._load_progression_enrollments(
            db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
        )
        if run.total_students == 0:
            run.total_students = len(enrollments)
        if session.end_date is None:
            raise ConflictException("The closing academic session is missing its end date.")
        effective_date = session.end_date

        for enrollment in enrollments:
            try:
                async with db.begin_nested():
                    await AcademicProgressionService._progress_student(
                        db,
                        actor=actor,
                        run=run,
                        enrollment=enrollment,
                        next_session=next_session,
                        effective_date=effective_date,
                        allow_terminal_completion=terminal_completion_confirmed,
                    )
            except Exception as exc:
                await StudentProgressionRepository.add_item(
                    db,
                    StudentProgressionItem(
                        tenant_id=tenant_id,
                        progression_run_id=run.id,
                        student_id=enrollment.student_id,
                        from_enrollment_id=enrollment.id,
                        from_level_id=enrollment.academic_level_id,
                        from_class_id=enrollment.class_id,
                        to_class_id=None,
                        action=StudentProgressionItemAction.SKIP,
                        status=StudentProgressionItemStatus.BLOCKED,
                        reason=str(exc)[:1000],
                        processed_at=_utc_now(),
                    ),
                )

        persisted_items = await StudentProgressionRepository.list_items_for_run(
            db, tenant_id, run.id
        )
        summary = SessionClosureService._summarize_progression_items(persisted_items)
        run.promoted_students = summary["promoted"]
        run.graduated_students = summary["graduated"]
        run.skipped_students = summary["skipped"]
        run.pending_students = summary["pending"]
        run.failed_students = summary["failed"]
        incomplete_students = max(run.total_students - len(persisted_items), 0)
        progression_failed = run.failed_students > 0 or incomplete_students > 0
        run.status = (
            StudentProgressionRunStatus.FAILED
            if progression_failed
            else StudentProgressionRunStatus.COMPLETED
        )
        run.completed_at = _utc_now()
        run.failure_reason = (
            f"{run.failed_students} failed and {incomplete_students} incomplete student progression item(s)."
            if run.status == StudentProgressionRunStatus.FAILED
            else None
        )
        await StudentProgressionRepository.save_run(db, run)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="session",
            entity_id=session.id,
            action=("progression_failed" if progression_failed else "progression_completed"),
            previous_status=session.status.value,
            new_status=session.status.value,
            acting_admin_id=actor.id,
            reason=run.failure_reason,
            metadata={
                "progression_run_id": str(run.id),
                "terminal_completion_confirmed": terminal_completion_confirmed,
                "promoted": run.promoted_students,
                "graduated": run.graduated_students,
                "skipped": run.skipped_students,
                "pending": run.pending_students,
                "failed": run.failed_students,
            },
        )
        await SessionClosureService._broadcast(
            db,
            tenant_id=tenant_id,
            actor_id=actor.id,
            title=(
                "Academic session closing requires attention"
                if progression_failed
                else "Academic session is closing"
            ),
            body=(
                f"Student progression finished with {run.failed_students} failed and "
                f"{incomplete_students} incomplete item(s). "
                "The session remains in closing while the administrator reviews the audit."
                if progression_failed
                else (
                    f"Student progression is complete: {run.promoted_students} promoted, "
                    f"{run.graduated_students} graduated, {run.pending_students} pending, "
                    f"and {run.skipped_students} skipped. "
                    "Academic write activities remain paused until the administrator finalizes closure."
                )
            ),
            priority=(
                AnnouncementPriority.URGENT if progression_failed else AnnouncementPriority.HIGH
            ),
        )
        await db.commit()
        await RealtimePublisher.publish_deferred_after_commit(db)
        await SessionClosureService._publish_progression_event(
            run=run,
            event_type=(
                "academic_session.progression.failed"
                if progression_failed
                else "academic_session.progression.completed"
            ),
        )
        await AuthIdentityService.invalidate_after_commit(db)
        return {
            "status": run.status.value,
            "processed": run.total_students,
            "promoted": run.promoted_students,
            "graduated": run.graduated_students,
            "skipped": run.skipped_students,
            "pending": run.pending_students,
            "failed": run.failed_students,
        }

    @staticmethod
    async def status(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> SessionClosureStatusResponse:
        session = await AcademicSessionLifecycleRepository.get_by_id(db, tenant_id, session_id)
        if session is None:
            raise NotFoundException("Academic session not found.")
        run = await StudentProgressionRepository.get_run_by_session(db, tenant_id, session.id)
        audit = await SessionClosureService.audit(db, tenant_id=tenant_id, session_id=session.id)
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
            db, actor.tenant_id, session_id, lock=True
        )
        run = await StudentProgressionRepository.get_run_by_session(
            db, actor.tenant_id, session_id, lock=True
        )
        if session is None or run is None:
            raise NotFoundException("Session progression run not found.")
        if session.status != AcademicSessionStatus.CLOSING:
            raise ConflictException("Only a closing session can retry progression.")

        allowed = run.status in {
            StudentProgressionRunStatus.FAILED,
            StudentProgressionRunStatus.PENDING,
        }
        if run.status == StudentProgressionRunStatus.PROCESSING:
            if not SessionClosureService._processing_is_stale(run):
                raise ConflictException(
                    "Progression is still processing and cannot be retried yet."
                )
            allowed = True
        if not allowed:
            raise ConflictException(
                "Only failed, pending, or stale processing progression can be retried."
            )

        run.status = StudentProgressionRunStatus.PENDING
        run.started_at = None
        run.completed_at = None
        run.failure_reason = None
        run.initiated_by_admin_id = actor.id
        await StudentProgressionRepository.save_run(db, run)
        await db.commit()

        queued = await SessionClosureService._enqueue_progression_safely(
            run=run,
            tenant_id=actor.tenant_id,
            retry=True,
        )
        if not queued:
            raise ConflictException(
                "Progression is pending but could not be queued. Retry the progression request."
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
        date_blockers = SessionClosureService._next_session_date_blockers(
            session=session,
            next_session=next_session,
        )
        if date_blockers:
            raise ConflictException(
                "Academic session dates are no longer valid for closure.",
                payload={"blocker_messages": date_blockers},
            )

        now = _utc_now()
        session.status = AcademicSessionStatus.CLOSED
        session.is_current = False
        session.closed_at = now
        session.closed_by_admin_id = actor.id
        await AcademicSessionLifecycleRepository.save(db, session)

        from app.modules.school_calendar.service import SchoolCalendarService

        await SchoolCalendarService.archive_session_calendars(
            db,
            tenant_id=actor.tenant_id,
            academic_session_id=session.id,
            acting_admin_id=actor.id,
        )

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
            action="retained_draft_after_progression",
            previous_status=next_session.status.value,
            new_status=next_session.status.value,
            acting_admin_id=actor.id,
            metadata={"progression_run_id": str(run.id)},
        )
        await SessionClosureService._broadcast(
            db,
            tenant_id=actor.tenant_id,
            actor_id=actor.id,
            title=f"{session.name} academic session has closed",
            body=(
                f"{session.name} has been closed. {next_session.name} remains in draft "
                "for calendar setup and a separate opening step."
            ),
            priority=AnnouncementPriority.HIGH,
        )
        await db.commit()
        await db.refresh(session)
        await db.refresh(next_session)
        return SessionClosureFinalizeResponse(
            closed_session=AcademicSessionResponse.model_validate(session),
            next_session=AcademicSessionResponse.model_validate(next_session),
            progression_run=await SessionClosureService._run_detail(
                db, tenant_id=actor.tenant_id, run=run
            ),
        )
