# ===================================== #
#   bulk_imports_notification_service.py #
# ===================================== #

"""Notification service for bulk import job events."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bulk_imports.models import ImportJob
from app.modules.communications.enums import (
    CommunicationActorType,
    NotificationSourceType,
)
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import ResolvedRecipient
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def build_completion_title(*, import_job: ImportJob) -> str:
    """Build import completion notification title."""

    if import_job.failed_rows > 0 and import_job.successful_rows > 0:
        return "Bulk import partially completed"

    if import_job.failed_rows > 0:
        return "Bulk import completed with errors"

    return "Bulk import completed"


def build_completion_message(*, import_job: ImportJob) -> str:
    """Build import completion notification message."""

    return (
        f"{import_job.resource_type.value.replace('_', ' ').title()} import finished. "
        f"{import_job.successful_rows} succeeded, "
        f"{import_job.failed_rows} failed, "
        f"{import_job.skipped_rows} skipped."
    )


def build_failure_title(*, import_job: ImportJob) -> str:
    """Build import failure notification title."""

    return "Bulk import failed"


def build_failure_message(*, import_job: ImportJob) -> str:
    """Build import failure notification message."""

    reason = import_job.error_message or "The import could not be completed."
    return (
        f"{import_job.resource_type.value.replace('_', ' ').title()} import failed. "
        f"Reason: {reason}"
    )


class BulkImportCommunicationService:
    """Deliver bulk-import events into the unified notification inbox."""

    @staticmethod
    async def _recipients(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient_admin_id: UUID | None,
    ) -> list[ResolvedRecipient]:
        stmt = select(TenantAdmin).where(
            TenantAdmin.tenant_id == tenant_id,
            TenantAdmin.is_active.is_(True),
            TenantAdmin.is_verified.is_(True),
            TenantAdmin.account_status == TenantAdminStatus.ACTIVE,
        )
        if recipient_admin_id is not None:
            stmt = stmt.where(TenantAdmin.id == recipient_admin_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [
            ResolvedRecipient(
                actor_type=CommunicationActorType.TENANT_ADMIN,
                actor_id=row.id,
                tenant_id=row.tenant_id,
                label=row.email,
            )
            for row in rows
        ]

    @staticmethod
    async def create_completion_notification(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient_admin_id: UUID | None,
        import_job: ImportJob,
    ):
        """Create an in-app notification for a completed import."""

        recipients = await BulkImportCommunicationService._recipients(
            db,
            tenant_id=tenant_id,
            recipient_admin_id=recipient_admin_id,
        )
        return await NotificationService.deliver_system_event(
            db,
            recipients=recipients,
            source_type=NotificationSourceType.BULK_IMPORT,
            source_id=import_job.id,
            title=build_completion_title(import_job=import_job),
            preview=build_completion_message(import_job=import_job),
            action_path=f"/admin/imports/history/{import_job.id}",
            tenant_id=tenant_id,
        )

    @staticmethod
    async def create_failure_notification(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient_admin_id: UUID | None,
        import_job: ImportJob,
    ):
        """Create an in-app notification for a failed import."""

        recipients = await BulkImportCommunicationService._recipients(
            db,
            tenant_id=tenant_id,
            recipient_admin_id=recipient_admin_id,
        )
        return await NotificationService.deliver_system_event(
            db,
            recipients=recipients,
            source_type=NotificationSourceType.BULK_IMPORT,
            source_id=import_job.id,
            title=build_failure_title(import_job=import_job),
            preview=build_failure_message(import_job=import_job),
            action_path=f"/admin/imports/history/{import_job.id}",
            tenant_id=tenant_id,
        )
