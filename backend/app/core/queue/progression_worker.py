"""Dedicated ARQ worker for academic-session student progression."""

from __future__ import annotations

import uuid
from typing import Any

from app.modules import import_model_modules

import_model_modules()

from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.queue.arq import (  # noqa: E402
    SESSION_PROGRESSION_QUEUE_NAME,
    get_arq_redis_settings,
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
    async with AsyncSessionLocal() as db:
        try:
            return await SessionClosureService.process_progression_run(
                db,
                tenant_id=uuid.UUID(tenant_id),
                run_id=uuid.UUID(run_id),
            )
        except Exception:
            await db.rollback()
            raise


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
