# ===================================== #
#   bulk_imports_notification_service.py #
# ===================================== #

"""Notification service for bulk import job events."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.bulk_imports.models import (
    ImportJob,
    ImportNotificationStatus,
)
from app.modules.bulk_imports.repository import ImportNotificationRepository
from app.modules.bulk_imports.schemas import ImportNotificationCreate


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


class BulkImportNotificationService:
    """Create import-specific admin notifications."""

    @staticmethod
    async def create_completion_notification(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient_admin_id: UUID | None,
        import_job: ImportJob,
    ):
        """Create an in-app notification for a completed import."""

        notification = await ImportNotificationRepository.create_notification(
            db=db,
            tenant_id=tenant_id,
            notification_data=ImportNotificationCreate(
                import_job_id=import_job.id,
                recipient_admin_id=recipient_admin_id,
                status=ImportNotificationStatus.SENT,
                title=build_completion_title(import_job=import_job),
                message=build_completion_message(import_job=import_job),
            ),
        )
        notification.sent_at = datetime.now(timezone.utc)
        return await ImportNotificationRepository.save(db=db, notification=notification)

    @staticmethod
    async def create_failure_notification(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient_admin_id: UUID | None,
        import_job: ImportJob,
    ):
        """Create an in-app notification for a failed import."""

        notification = await ImportNotificationRepository.create_notification(
            db=db,
            tenant_id=tenant_id,
            notification_data=ImportNotificationCreate(
                import_job_id=import_job.id,
                recipient_admin_id=recipient_admin_id,
                status=ImportNotificationStatus.SENT,
                title=build_failure_title(import_job=import_job),
                message=build_failure_message(import_job=import_job),
            ),
        )
        notification.sent_at = datetime.now(timezone.utc)
        return await ImportNotificationRepository.save(db=db, notification=notification)
