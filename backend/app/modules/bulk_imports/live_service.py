# ================================= #
#   bulk_imports_live_service.py    #
# ================================= #

"""Live/background confirmation flow for bulk imports."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.bulk_imports.chunking import chunk_import_items
from app.modules.bulk_imports.models import ImportJob, ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.notification_service import BulkImportNotificationService
from app.modules.bulk_imports.repository import (
    ImportJobRepository,
    ImportRowErrorRepository,
    ImportStagedRowRepository,
)
from app.modules.bulk_imports.schemas import ImportJobDetailResponse, ImportJobUpdate, ImportRowErrorCreate
from app.modules.bulk_imports.service import (
    BulkImportService,
    build_failed_result_row,
    compact_validation_error,
    utc_now,
)
from app.modules.bulk_imports.validators import ImportRowValidationResult
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.repository import TenantRepository


LIVE_IMPORT_CHUNK_SIZE = 25
ACTIVE_IMPORT_STATUSES = {ImportJobStatus.PENDING, ImportJobStatus.PROCESSING}


def _sorted_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort result rows by source row number."""

    return sorted(rows, key=lambda row: int(row.get("row_number") or 0))


def _build_processing_error_item(
    *,
    import_job_id: UUID,
    validation_result: ImportRowValidationResult,
    error_code: str,
    error_message: str,
) -> ImportRowErrorCreate:
    """Build a row-level processing error."""

    return ImportRowErrorCreate(
        import_job_id=import_job_id,
        row_number=validation_result.row_number,
        field_name=None,
        error_code=error_code,
        error_message=error_message,
        raw_row=validation_result.raw_row,
        normalized_row=validation_result.normalized_row,
    )


def _validation_result_from_staged_row(staged_row) -> ImportRowValidationResult:
    """Build a validation-result-like object from a staged row."""

    return ImportRowValidationResult(
        row_number=staged_row.row_number,
        raw_row=staged_row.raw_row,
        normalized_row=staged_row.normalized_row,
    )


class BulkImportLiveService:
    """Queue and process confirmed dry-run imports with live DB progress."""

    @staticmethod
    async def queue_confirmed_import(
        db: AsyncSession,
        *,
        actor,
        job_id: UUID,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        """Confirm a dry-run job, enqueue background processing, and return immediately."""

        await SubscriptionFeatureService.ensure_feature_enabled(
            db=db,
            tenant_id=actor.tenant_id,
            feature=FeatureCode.BULK_IMPORT,
        )

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
            lock=True,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")

        metadata_json = dict(import_job.metadata_json or {})
        if not metadata_json.get("dry_run"):
            raise BadRequestException(detail="Only dry-run import jobs can be confirmed.")

        if metadata_json.get("confirmed_at"):
            raise BadRequestException(detail="This import job has already been confirmed.")

        staged_rows = await ImportStagedRowRepository.list_by_job(
            db=db,
            tenant_id=actor.tenant_id,
            import_job_id=import_job.id,
        )
        if not staged_rows:
            raise BadRequestException(detail="This dry-run job has no valid staged rows to confirm.")

        await SubscriptionFeatureService.ensure_resource_limit_available(
            db=db,
            tenant_id=actor.tenant_id,
            resource=BulkImportService.resource_limit_code(import_job.resource_type),
            increment=len(staged_rows),
        )

        invalid_rows = int(metadata_json.get("invalid_rows") or 0)
        now = utc_now()
        metadata_json.update(
            {
                "dry_run": False,
                "confirmed_from_dry_run": True,
                "confirmation_required": False,
                "confirmed_at": now.isoformat(),
                "queued_at": now.isoformat(),
                "live_progress": True,
                "notify_on_completion": notify_on_completion,
                "valid_rows": len(staged_rows),
                "invalid_rows": invalid_rows,
            }
        )

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=ImportJobStatus.PROCESSING,
                started_at=now,
                completed_at=None,
                successful_rows=0,
                failed_rows=invalid_rows,
                processed_rows=invalid_rows,
                skipped_rows=0,
                metadata_json=metadata_json,
            ),
        )
        await db.commit()

        try:
            from app.core.queue.arq import enqueue_bulk_import_job

            await enqueue_bulk_import_job(
                job_id=str(import_job.id),
                tenant_id=str(actor.tenant_id),
                actor_id=str(actor.id),
                notify_on_completion=notify_on_completion,
            )
        except Exception as exc:
            failed_job = await ImportJobRepository.get_job_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                job_id=import_job.id,
                lock=True,
            )
            if failed_job is not None:
                failed_metadata = dict(failed_job.metadata_json or {})
                failed_metadata["queue_error"] = str(exc)
                await ImportJobRepository.update_job(
                    db=db,
                    import_job=failed_job,
                    job_update=ImportJobUpdate(
                        status=ImportJobStatus.FAILED,
                        error_message="Could not queue the background import worker.",
                        completed_at=utc_now(),
                        metadata_json=failed_metadata,
                    ),
                )
                await db.commit()
            raise BadRequestException(detail="Could not queue the background import worker.") from exc

        refreshed_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=import_job.id,
            include_children=True,
        )
        if refreshed_job is None:
            raise NotFoundException(detail="Import job not found after queueing confirmation.")

        return ImportJobDetailResponse.model_validate(refreshed_job)

    @staticmethod
    async def _mark_job_failed(
        db: AsyncSession,
        *,
        import_job: ImportJob,
        error_message: str,
    ) -> None:
        """Mark a live import job as failed."""

        metadata_json = dict(import_job.metadata_json or {})
        metadata_json["background_import_failed_at"] = utc_now().isoformat()
        metadata_json["background_import_error"] = error_message
        await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=ImportJobStatus.FAILED,
                error_message=error_message,
                completed_at=utc_now(),
                metadata_json=metadata_json,
            ),
        )
        await db.commit()

    @staticmethod
    async def process_confirmed_import_job(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        job_id: UUID,
        notify_on_completion: bool = True,
    ) -> dict[str, int | str]:
        """Process one confirmed import job while updating counters after every chunk."""

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=tenant_id,
            job_id=job_id,
            lock=True,
        )
        if import_job is None:
            return {"status": "not_found", "processed": 0, "created": 0, "failed": 0}

        metadata_json = dict(import_job.metadata_json or {})
        if import_job.status not in ACTIVE_IMPORT_STATUSES:
            return {
                "status": import_job.status.value,
                "processed": int(import_job.processed_rows or 0),
                "created": int(import_job.successful_rows or 0),
                "failed": int(import_job.failed_rows or 0),
            }

        if metadata_json.get("background_import_started_at"):
            return {
                "status": "already_started",
                "processed": int(import_job.processed_rows or 0),
                "created": int(import_job.successful_rows or 0),
                "failed": int(import_job.failed_rows or 0),
            }

        metadata_json["background_import_started_at"] = utc_now().isoformat()
        await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(metadata_json=metadata_json),
        )
        await db.commit()

        actor = await TenantAdminRepository.get_by_id(db=db, admin_id=actor_id)
        if actor is None:
            await BulkImportLiveService._mark_job_failed(
                db=db,
                import_job=import_job,
                error_message="Tenant admin that started the import no longer exists.",
            )
            return {"status": "failed", "processed": 0, "created": 0, "failed": 1}

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=tenant_id)
        if tenant is None:
            await BulkImportLiveService._mark_job_failed(
                db=db,
                import_job=import_job,
                error_message="Tenant not found for background import.",
            )
            return {"status": "failed", "processed": 0, "created": 0, "failed": 1}

        staged_rows = await ImportStagedRowRepository.list_by_job(
            db=db,
            tenant_id=tenant_id,
            import_job_id=job_id,
        )
        if not staged_rows:
            await BulkImportLiveService._mark_job_failed(
                db=db,
                import_job=import_job,
                error_message="No staged rows found for background import.",
            )
            return {"status": "failed", "processed": 0, "created": 0, "failed": 1}

        metadata_json = dict(import_job.metadata_json or {})
        invalid_rows = int(metadata_json.get("invalid_rows") or 0)
        existing_result_rows = list(metadata_json.get("result_rows") or [])
        invalid_result_rows = [row for row in existing_result_rows if row.get("status") == "failed"]

        created_count = 0
        processing_failed_count = 0
        result_rows: list[dict[str, Any]] = list(invalid_result_rows)

        validation_results = [_validation_result_from_staged_row(row) for row in staged_rows]

        try:
            for chunk in chunk_import_items(items=validation_results, chunk_size=LIVE_IMPORT_CHUNK_SIZE):
                chunk_errors: list[ImportRowErrorCreate] = []

                for validation_result in chunk.items:
                    try:
                        async with db.begin_nested():
                            result_row = await BulkImportService.process_valid_row(
                                db=db,
                                actor=actor,
                                resource_type=import_job.resource_type,
                                validation_result=validation_result,
                                school_name=tenant.school_name,
                            )
                        created_count += 1
                        result_rows.append(result_row)

                    except (BadRequestException, ConflictException, NotFoundException, ValidationError) as exc:
                        processing_failed_count += 1
                        error_message = (
                            compact_validation_error(exc)
                            if isinstance(exc, ValidationError)
                            else str(exc.detail if hasattr(exc, "detail") else exc)
                        )
                        chunk_errors.append(
                            _build_processing_error_item(
                                import_job_id=job_id,
                                validation_result=validation_result,
                                error_code="processing_error",
                                error_message=error_message,
                            )
                        )
                        result_rows.append(
                            build_failed_result_row(
                                row_number=validation_result.row_number,
                                normalized_row=validation_result.normalized_row,
                                error_message=error_message,
                            )
                        )

                    except IntegrityError:
                        processing_failed_count += 1
                        error_message = "Row failed because of a duplicate or invalid database value."
                        chunk_errors.append(
                            _build_processing_error_item(
                                import_job_id=job_id,
                                validation_result=validation_result,
                                error_code="integrity_error",
                                error_message=error_message,
                            )
                        )
                        result_rows.append(
                            build_failed_result_row(
                                row_number=validation_result.row_number,
                                normalized_row=validation_result.normalized_row,
                                error_message=error_message,
                            )
                        )

                if chunk_errors:
                    await ImportRowErrorRepository.create_many(
                        db=db,
                        tenant_id=tenant_id,
                        row_error_items=chunk_errors,
                    )

                processed_rows = invalid_rows + created_count + processing_failed_count
                metadata_json = dict(import_job.metadata_json or {})
                metadata_json["result_rows"] = _sorted_result_rows(result_rows)
                metadata_json["last_progress_at"] = utc_now().isoformat()
                metadata_json["processed_valid_rows"] = created_count + processing_failed_count

                import_job = await ImportJobRepository.update_job(
                    db=db,
                    import_job=import_job,
                    job_update=ImportJobUpdate(
                        status=ImportJobStatus.PROCESSING,
                        processed_rows=min(processed_rows, import_job.total_rows),
                        successful_rows=created_count,
                        failed_rows=invalid_rows + processing_failed_count,
                        skipped_rows=0,
                        metadata_json=metadata_json,
                    ),
                )
                await db.commit()

            successful_rows = created_count
            failed_rows = invalid_rows + processing_failed_count
            final_status = BulkImportService.resolve_final_status(
                successful_rows=successful_rows,
                failed_rows=failed_rows,
            )

            metadata_json = dict(import_job.metadata_json or {})
            metadata_json["result_rows"] = _sorted_result_rows(result_rows)
            metadata_json["background_import_completed_at"] = utc_now().isoformat()
            metadata_json["processed_valid_rows"] = len(staged_rows)

            import_job = await ImportJobRepository.update_job(
                db=db,
                import_job=import_job,
                job_update=ImportJobUpdate(
                    status=final_status,
                    processed_rows=import_job.total_rows,
                    successful_rows=successful_rows,
                    failed_rows=failed_rows,
                    skipped_rows=0,
                    completed_at=utc_now(),
                    metadata_json=metadata_json,
                ),
            )

            if notify_on_completion:
                if final_status == ImportJobStatus.FAILED:
                    await BulkImportNotificationService.create_failure_notification(
                        db=db,
                        tenant_id=tenant_id,
                        recipient_admin_id=actor_id,
                        import_job=import_job,
                    )
                else:
                    await BulkImportNotificationService.create_completion_notification(
                        db=db,
                        tenant_id=tenant_id,
                        recipient_admin_id=actor_id,
                        import_job=import_job,
                    )

            if successful_rows > 0:
                await SubscriptionFeatureService.invalidate_tenant_subscription_state(tenant_id)

            await db.commit()

            if successful_rows > 0:
                try:
                    from app.modules.metrics.cache import (
                        invalidate_superadmin_dashboard_cache,
                        invalidate_tenant_admin_dashboard_cache,
                    )

                    await invalidate_tenant_admin_dashboard_cache(tenant_id)
                    await invalidate_superadmin_dashboard_cache()
                except Exception:
                    pass

            if successful_rows > 0 and import_job.resource_type in {ImportResourceType.TEACHERS, ImportResourceType.PARENTS}:
                try:
                    from app.core.queue.arq import enqueue_email_outbox_batch

                    await enqueue_email_outbox_batch()
                except Exception:
                    pass

            return {
                "status": final_status.value,
                "processed": int(import_job.processed_rows or 0),
                "created": successful_rows,
                "failed": failed_rows,
            }

        except Exception as exc:
            latest_job = await ImportJobRepository.get_job_by_id(
                db=db,
                tenant_id=tenant_id,
                job_id=job_id,
                lock=True,
            )
            if latest_job is not None:
                await BulkImportLiveService._mark_job_failed(
                    db=db,
                    import_job=latest_job,
                    error_message=str(exc),
                )
            return {"status": "failed", "processed": created_count + processing_failed_count, "created": created_count, "failed": processing_failed_count + 1}
