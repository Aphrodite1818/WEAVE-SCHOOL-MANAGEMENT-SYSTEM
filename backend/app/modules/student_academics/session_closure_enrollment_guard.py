"""Enrollment invariants layered onto staged academic-session closure."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.modules.student_academics.session_closure_service import (
    SessionClosureService as BaseSessionClosureService,
)
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment
from app.modules.tenant_admins.models import TenantAdmin


class SessionClosureService(BaseSessionClosureService):
    """Prevent session closure while any enrollment would be stranded."""

    @staticmethod
    async def _unresolved_enrollment_count(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentEnrollment)
                    .join(Student, Student.id == StudentEnrollment.student_id)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.academic_session_id == session_id,
                        StudentEnrollment.ended_on.is_(None),
                        Student.tenant_id == tenant_id,
                        or_(
                            Student.is_archived.is_(True),
                            Student.promotion_hold.is_(True),
                            Student.status != AcademicStatus.ACTIVE,
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )

    @staticmethod
    async def _open_enrollment_count(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentEnrollment)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.academic_session_id == session_id,
                        StudentEnrollment.ended_on.is_(None),
                    )
                )
            ).scalar_one()
            or 0
        )

    @staticmethod
    async def audit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ):
        audit = await BaseSessionClosureService.audit(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        unresolved = await SessionClosureService._unresolved_enrollment_count(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        counts = dict(audit.dependency_counts)
        counts["unresolved_current_enrollments"] = unresolved
        blockers = list(audit.blocker_messages)
        if unresolved:
            blockers.append(
                f"{unresolved} current enrollment(s) require an explicit progression decision "
                "before this session can enter closing. Resolve suspension/promotion holds or "
                "perform the appropriate terminal exit first."
            )
        checked = list(audit.checked_items)
        checked.append("No current enrollment can be stranded in the closing session.")
        return audit.model_copy(
            update={
                "dependency_counts": counts,
                "blocker_messages": list(dict.fromkeys(blockers)),
                "checked_items": checked,
                "is_ready": bool(audit.is_ready and unresolved == 0),
            }
        )

    @staticmethod
    async def start_closing(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
        idempotency_key: str,
        allow_terminal_completion: bool = False,
    ):
        unresolved = await SessionClosureService._unresolved_enrollment_count(
            db,
            tenant_id=actor.tenant_id,
            session_id=session_id,
        )
        if unresolved:
            raise ConflictException(
                "Resolve every current student enrollment before starting session closure.",
                payload={"dependency_counts": {"unresolved_current_enrollments": unresolved}},
            )
        return await BaseSessionClosureService.start_closing(
            db,
            actor=actor,
            session_id=session_id,
            idempotency_key=idempotency_key,
            allow_terminal_completion=allow_terminal_completion,
        )

    @staticmethod
    async def status(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ):
        status = await BaseSessionClosureService.status(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        audit = await SessionClosureService.audit(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        open_enrollments = await SessionClosureService._open_enrollment_count(
            db,
            tenant_id=tenant_id,
            session_id=session_id,
        )
        return status.model_copy(
            update={
                "audit": audit,
                "can_finalize": bool(status.can_finalize and open_enrollments == 0),
            }
        )

    @staticmethod
    async def finalize(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ):
        remaining = await SessionClosureService._open_enrollment_count(
            db,
            tenant_id=actor.tenant_id,
            session_id=session_id,
        )
        if remaining:
            raise ConflictException(
                "Academic session cannot close while current enrollments still belong to it.",
                payload={"dependency_counts": {"open_enrollments": remaining}},
            )
        return await BaseSessionClosureService.finalize(
            db,
            actor=actor,
            session_id=session_id,
        )
