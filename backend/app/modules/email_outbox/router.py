# =========================== #
#   email_outbox_router.py    #
# =========================== #

"""Tenant admin email outbox operational routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.email_outbox.schemas import (
    EmailOutboxRecoveryResponse,
    EmailOutboxRetryResponse,
    EmailOutboxSummaryResponse,
)
from app.modules.email_outbox.service import EmailOutboxService
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/email-outbox",
    tags=["Email Outbox"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.get(
    "/summary",
    response_model=EmailOutboxSummaryResponse,
)
async def get_email_outbox_summary(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    import_job_id: UUID | None = Query(default=None),
    source: str | None = Query(default=None),
) -> EmailOutboxSummaryResponse:
    """Return tenant email delivery status counts."""

    return await EmailOutboxService.summarize_tenant_outbox(
        db=db,
        tenant_id=current_user.tenant_id,
        import_job_id=import_job_id,
        source=source,
    )


@router.post(
    "/recover-stale",
    response_model=EmailOutboxRecoveryResponse,
)
async def recover_stale_email_outbox_items(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    stale_minutes: int = Query(default=10, ge=1, le=120),
) -> EmailOutboxRecoveryResponse:
    """Recover emails stuck in processing after a worker timeout/crash."""

    result = await EmailOutboxService.recover_stale_processing_emails(
        db=db,
        tenant_id=current_user.tenant_id,
        stale_minutes=stale_minutes,
    )
    return EmailOutboxRecoveryResponse(**result)


@router.post(
    "/retry-failed",
    response_model=EmailOutboxRetryResponse,
)
async def retry_failed_email_outbox_items(
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> EmailOutboxRetryResponse:
    """Queue failed emails for retry when attempts remain."""

    result = await EmailOutboxService.retry_failed_for_tenant(
        db=db,
        tenant_id=current_user.tenant_id,
    )
    return EmailOutboxRetryResponse(**result)
