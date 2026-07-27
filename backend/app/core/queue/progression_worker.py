"""Dedicated ARQ worker for academic-session student progression."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.modules import import_model_modules

import_model_modules()

from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    SESSION_PROGRESSION_QUEUE_NAME,
    get_arq_redis_settings,
)
from app.modules.announcements.models import AnnouncementPriority  # noqa: E402
from app.modules.student_academics.lifecycle_repository import (  # noqa: E402
    StudentProgressionRepository,
)
from app.modules.student_academics.models import (  # noqa: E402
    StudentProgressionRunStatus,
)
from app.modules.student_academics.session_closure_service import (  # noqa: E402
    SessionClosureService,
)


async def process_session_progression_job(
    ctx: dict[str, Any],
    run_id: str,
    tenant_id: str,
) -> dict[str, int | str]:
    """Progress all eligible students without closing the academic session.

    Responsibilities:
    - validate that the session is still in CLOSING;
    - promote students into next-session enrollments;
    - graduate terminal-class students;
    - preserve historical enrollment records;
    - skip ineligible or held students;
    - isolate per-student failures;
    - persist a complete progression audit;
    - notify the tenant when progression finishes;
    - leave final session closure to the tenant administrator.
    """

    _ = ctx
    parsed_run_id = uuid.UUID(run_id)
    parsed_tenant_id = uuid.UUID(tenant_id)
    async with AsyncSessionLocal() as db:
        try:
            return await SessionClosureService.process_progression_run(
                db,
                tenant_id=parsed_tenant_id,
                run_id=parsed_run_id,
            )
        except Exception as exc:
            await db.rollback()

    # Persist terminal worker failure outside the rolled-back processing transaction.
    async with AsyncSessionLocal() as failure_db:
        run = await StudentProgressionRepository.get_run_by_id(
            failure_db,
            parsed_tenant_id,
            parsed_run_id,
            lock=True,
        )
        if run is not None and run.status != StudentProgressionRunStatus.COMPLETED:
            run.status = StudentProgressionRunStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.failed_students = max(run.failed_students, 1)
            run.failure_reason = str(exc)[:1000]
            await StudentProgressionRepository.save_run(failure_db, run)
            if run.initiated_by_admin_id is not None:
                await SessionClosureService._broadcast(
                    failure_db,
                    tenant_id=parsed_tenant_id,
                    actor_id=run.initiated_by_admin_id,
                    title="Academic session progression failed",
                    body=(
                        "The session remains in closing and academic writes remain paused. "
                        f"Review the progression status before retrying. Reason: {str(exc)[:500]}"
                    ),
                    priority=AnnouncementPriority.URGENT,
                )
            await failure_db.commit()
        raise exc


async def shutdown(ctx: dict[str, Any]) -> None:
    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """Settings for the dedicated session-progression worker."""

    redis_settings = get_arq_redis_settings()
    queue_name = SESSION_PROGRESSION_QUEUE_NAME
    functions = [process_session_progression_job]
    on_shutdown = shutdown

    # Session progression is intentionally serialized per worker process.
    max_jobs = 1
    job_timeout = 3600
    keep_result = 3600
    max_tries = 3
    health_check_key = f"{SESSION_PROGRESSION_QUEUE_NAME}:health"
