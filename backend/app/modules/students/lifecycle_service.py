"""Student lifecycle integration for immutable enrollment segments."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository
from app.modules.student_academics.models import AcademicSessionStatus
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.enrollment_service import StudentEnrollmentService
from app.modules.students.models import AcademicStatus, StudentEnrollmentOutcome
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentLifecycleTransitionResponse, StudentResponse
from app.modules.students.service import StudentLifecycleService as LegacyStudentLifecycleService
from app.modules.tenant_admins.models import TenantAdmin


class StudentLifecycleService(LegacyStudentLifecycleService):
    """Lifecycle operations that preserve placement chronology."""

    @staticmethod
    async def _ensure_terminal_exit_safe(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        effective_date: date,
    ) -> None:
        current = await StudentEnrollmentRepository.get_current(
            db,
            tenant_id,
            student_id,
            lock=True,
        )
        if current is None:
            return
        if effective_date < current.started_on:
            raise ConflictException("Lifecycle exit cannot predate the current enrollment.")

        # ended_on is inclusive for terminal exits. Evidence on the final day is
        # valid; only evidence after that day contradicts a backdated exit.
        if effective_date < date.today():
            counts = await StudentEnrollmentService._segment_dependency_counts(
                db,
                tenant_id=tenant_id,
                enrollment_id=current.id,
                on_or_after=effective_date + timedelta(days=1),
            )
            blockers = {key: value for key, value in counts.items() if value > 0}
            if blockers:
                raise ConflictException(
                    "The lifecycle exit cannot be backdated across preserved academic evidence.",
                    payload={"dependency_counts": blockers},
                )

    @staticmethod
    async def withdraw(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        effective_date: date,
    ) -> StudentLifecycleTransitionResponse:
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await StudentLifecycleService._ensure_terminal_exit_safe(
            db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
            effective_date=effective_date,
        )
        return await LegacyStudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.WITHDRAWN,
            reason=reason,
            effective_date=effective_date,
        )

    @staticmethod
    async def expel(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        effective_date: date,
    ) -> StudentLifecycleTransitionResponse:
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await StudentLifecycleService._ensure_terminal_exit_safe(
            db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
            effective_date=effective_date,
        )
        return await LegacyStudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.EXPELLED,
            reason=reason,
            effective_date=effective_date,
        )

    @staticmethod
    async def graduate(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
        graduation_date: date,
    ) -> StudentLifecycleTransitionResponse:
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        await StudentLifecycleService._ensure_terminal_exit_safe(
            db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
            effective_date=graduation_date,
        )
        return await LegacyStudentLifecycleService._transition(
            db,
            actor=actor,
            student_id=student_id,
            target_status=AcademicStatus.GRADUATED,
            reason=reason,
            effective_date=graduation_date,
        )

    @staticmethod
    async def archive(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        reason: str,
    ) -> StudentResponse:
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)
        current = await StudentEnrollmentRepository.get_current(
            db,
            actor.tenant_id,
            student_id,
            lock=True,
        )
        if current is not None:
            raise ConflictException(
                "End the student's current academic enrollment before archiving the profile."
            )
        return await LegacyStudentLifecycleService.archive(
            db,
            actor=actor,
            student_id=student_id,
            reason=reason,
        )

    @staticmethod
    async def reinstate_expelled(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        target_class_id: UUID,
        academic_session_id: UUID,
        effective_date: date,
        reason: str,
    ) -> StudentLifecycleTransitionResponse:
        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            student_id,
            lock=True,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if await StudentEnrollmentRepository.get_current(
            db,
            actor.tenant_id,
            student_id,
            lock=True,
        ) is not None:
            raise ConflictException("Student already has a current enrollment.")

        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            actor.tenant_id,
            academic_session_id,
            lock=True,
        )
        if (
            session is None
            or not session.is_current
            or session.status != AcademicSessionStatus.OPEN
        ):
            raise ConflictException("Reinstatement requires the current open academic session.")

        history = await StudentEnrollmentRepository.list_for_student(
            db,
            actor.tenant_id,
            student_id,
        )
        previous = max(history, key=lambda row: row.ended_on or date.max, default=None)
        if previous is not None:
            if previous.ended_on is None:
                raise ConflictException("Student already has a current enrollment.")
            if effective_date <= previous.ended_on:
                raise ConflictException(
                    "Reinstatement must begin after the previous enrollment ended."
                )

        response = await LegacyStudentLifecycleService.reinstate_expelled(
            db,
            actor=actor,
            student_id=student_id,
            target_class_id=target_class_id,
            academic_session_id=academic_session_id,
            effective_date=effective_date,
            reason=reason,
        )

        # The inherited service records this as reclassification because the old
        # model lacked a reinstatement entry event. Correct the new segment before
        # returning so history states the actual reason it began.
        current = await StudentEnrollmentRepository.get_current(
            db,
            actor.tenant_id,
            student_id,
            lock=True,
        )
        if current is not None:
            current.entry_outcome = StudentEnrollmentOutcome.REINSTATED
            current.entry_reason = reason
            current.created_by_admin_id = actor.id
            await StudentEnrollmentRepository.save(db, current)
            await db.commit()
        return response
