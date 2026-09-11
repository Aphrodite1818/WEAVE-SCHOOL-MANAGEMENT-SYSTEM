"""Academic write guards shared by routes, services, workers, and scripts."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_teacher,
    get_current_tenant_admin,
)
from app.core.exceptions import ConflictException
from app.modules.student_academics.academic_lock import acquire_academic_lifecycle_lock
from app.modules.student_academics.models import AcademicSession, AcademicSessionStatus
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_LIFECYCLE_WRITE_SUFFIXES = {
    "/start-closing",
    "/retry-progression",
    "/finalize-close",
}


async def ensure_academic_write_window(
    db: AsyncSession,
    *,
    tenant_id,
) -> None:
    """Reject academic writes while the tenant's current session is closing.

    The tenant academic lifecycle advisory lock is acquired before checking the
    session state and remains held until the caller's transaction commits or
    rolls back. Session lifecycle transitions use the same lock, preventing a
    structural write that observed OPEN from committing after OPEN -> CLOSING.
    """

    await acquire_academic_lifecycle_lock(db, tenant_id=tenant_id)

    closing_session = (
        await db.execute(
            select(AcademicSession.id, AcademicSession.name)
            .where(
                AcademicSession.tenant_id == tenant_id,
                AcademicSession.is_current.is_(True),
                AcademicSession.status == AcademicSessionStatus.CLOSING,
            )
            .limit(1)
        )
    ).first()
    if closing_session is not None:
        raise ConflictException(
            "Academic write activities are paused while the current session is closing.",
            payload={
                "session_id": str(closing_session.id),
                "session_name": closing_session.name,
                "session_status": AcademicSessionStatus.CLOSING.value,
                "writes_paused": True,
            },
        )


async def _ensure_write_window(
    request: Request,
    db: DbSession,
    *,
    tenant_id,
) -> None:
    if request.method.upper() in _SAFE_METHODS:
        return
    if any(request.url.path.endswith(suffix) for suffix in _LIFECYCLE_WRITE_SUFFIXES):
        return

    await ensure_academic_write_window(db, tenant_id=tenant_id)


async def ensure_admin_academic_write_window(
    request: Request,
    db: DbSession,
    current_admin: Annotated[TenantAdmin, Depends(get_current_tenant_admin)],
) -> None:
    await _ensure_write_window(
        request,
        db,
        tenant_id=current_admin.tenant_id,
    )


async def ensure_teacher_academic_write_window(
    request: Request,
    db: DbSession,
    current_teacher: Annotated[Teacher, Depends(get_current_teacher)],
) -> None:
    await _ensure_write_window(
        request,
        db,
        tenant_id=current_teacher.tenant_id,
    )
