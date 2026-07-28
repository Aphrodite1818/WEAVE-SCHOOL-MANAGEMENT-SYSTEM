"""Dedicated ARQ worker for attendance reminder and retention jobs."""

from __future__ import annotations

import uuid
from typing import Any

from arq import cron

import app.models  # noqa: F401

from app.config.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.queue.arq import ATTENDANCE_QUEUE_NAME, get_arq_redis_settings  # noqa: E402
from app.modules.attendance.repository import AttendanceRepository  # noqa: E402


async def process_attendance_retention_job(
    ctx: dict[str, Any],
    tenant_id: str | None = None,
) -> dict[str, int]:
    """Purge expired raw location evidence without deleting attendance rows."""

    _ = ctx
    parsed_tenant_id = uuid.UUID(tenant_id) if tenant_id else None
    async with AsyncSessionLocal() as db:
        result = await AttendanceRepository.purge_expired_location_evidence(
            db,
            tenant_id=parsed_tenant_id,
        )
        await db.commit()
        return result


async def poll_attendance_retention(ctx: dict[str, Any]) -> dict[str, int]:
    return await process_attendance_retention_job(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    _ = ctx
    await engine.dispose()


class WorkerSettings:
    """Settings for the dedicated attendance worker."""

    redis_settings = get_arq_redis_settings()
    queue_name = ATTENDANCE_QUEUE_NAME
    functions = [process_attendance_retention_job]
    cron_jobs = [
        cron(
            poll_attendance_retention,
            hour={1},
            minute=15,
            run_at_startup=False,
            unique=True,
            timeout=300,
            max_tries=1,
        )
    ]
    on_shutdown = shutdown
    max_jobs = 2
    job_timeout = 300
    keep_result = 300
    health_check_key = f"{ATTENDANCE_QUEUE_NAME}:health"
