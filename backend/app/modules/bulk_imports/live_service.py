# ================================= #
#   bulk_imports_live_service.py    #
# ================================= #

"""Live/background confirmation flow for bulk imports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.bulk_imports.chunking import chunk_import_items
from app.modules.bulk_imports.models import ImportJob, ImportJobStatus
from app.modules.bulk_imports.notification_service import BulkImportCommunicationService
from app.modules.bulk_imports.repository import (
    ImportJobRepository,
    ImportRowErrorRepository,
    ImportStagedRowRepository,
)
from app.modules.bulk_imports.schemas import (
    ImportJobDetailResponse,
    ImportJobUpdate,
    ImportRowErrorCreate,
)
from app.modules.bulk_imports.service import (
    BulkImportService,
    build_failed_result_row,
    build_import_source_fingerprint,
    compact_validation_error,
    duplicate_import_message,
    utc_now,
)
from app.modules.bulk_imports.validators import ImportRowValidationResult
from app.modules.realtime.publisher import RealtimePublisher
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.tenant_management.repository import TenantRepository

LIVE_IMPORT_CHUNK_SIZE = 25
ACTIVE_IMPORT_STATUSES = {ImportJobStatus.PENDING, ImportJobStatus.PROCESSING}
TERMINAL_ROW_STATUSES = {"created", "failed"}


async def _publish_job_event(
    *,
    event_type: str,
    tenant_id: UUID,
    actor_id: UUID,
    import_job: ImportJob,
) -> None:
    await RealtimePublisher.to_actor(
        event_type=event_type,
        actor_type="tenant_admin",
        actor_id=actor_id,
        tenant_id=tenant_id,
        data={
            "job_id": str(import_job.id),
            "status": import_job.status.value,
            "processed_rows": int(import_job.processed_rows or 0),
            "total_rows": int(import_job.total_rows or 0),
        },
    )


def _sorted_result_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: int(row.get("row_number") or 0))


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _job_is_stale(import_job: ImportJob, metadata_json: dict[str, Any]) -> bool:
    reference = (
        _parse_timestamp(metadata_json.get("last_progress_at"))
        or _parse_timestamp(metadata_json.get("background_import_started_at"))
        or import_job.updated_at
        or import_job.started_at
    )
    if reference is None:
        return True
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return utc_now() - reference >= timedelta(minutes=settings.BULK_IMPORT_STALE_AFTER_MINUTES)


def _terminal_result_rows(metadata_json: dict[str, Any]) -> list[dict[str, Any]]:
    rows = metadata_json.get("result_rows") or []
    return [
        dict(row)
        for row in rows
        if isinstance(row, dict) and str(row.get("status") or "").lower() in TERMINAL_ROW_STATUSES
    ]


def _build_processing_error_item(
    *,
    import_job_id: UUID,
    validation_result: ImportRowValidationResult,
    error_code: str,
    error_message: str,
) -> ImportRowErrorCreate:
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
    return ImportRowValidationResult(
        row_number=staged_row.row_number,
        raw_row=staged_row.raw_row,
        normalized_row=staged_row.normalized_row,
    )


class BulkImportLiveService:
    """Queue, resume, and process confirmed dry-run imports."""

    @staticmethod
    async def queue_confirmed_import(
        db: AsyncSession,
        *,
        actor,
        job_id: UUID,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
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
        staged_rows = await ImportStagedRowRepository.list_by_job(
            db=db,
            tenant_id=actor.tenant_id,
            import_job_id=import_job.id,
        )
        BulkImportService.validate_dry_run_confirmation_contract(
            import_job=import_job,
            staged_row_count=len(staged_rows),
        )

        source_fingerprint = import_job.source_fingerprint or build_import_source_fingerprint(
            resource_type=import_job.resource_type,
            template_version=metadata_json.get("template_version"),
            rows=[(row.row_number, row.normalized_row) for row in staged_rows],
        )
        existing_import = await ImportJobRepository.get_confirmed_job_by_fingerprint(
            db=db,
            tenant_id=actor.tenant_id,
            resource_type=import_job.resource_type,
            source_fingerprint=source_fingerprint,
            exclude_job_id=import_job.id,
        )
        if existing_import is not None:
            raise ConflictException(detail=duplicate_import_message(existing_import))

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
                source_fingerprint=source_fingerprint,
                confirmed_fingerprint=source_fingerprint,
                metadata_json=metadata_json,
            ),
        )
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            duplicate = await ImportJobRepository.get_confirmed_job_by_fingerprint(
                db=db,
                tenant_id=actor.tenant_id,
                resource_type=import_job.resource_type,
                source_fingerprint=source_fingerprint,
                exclude_job_id=import_job.id,
            )
            if duplicate is not None:
                raise ConflictException(detail=duplicate_import_message(duplicate)) from exc
            raise

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
                failed_metadata["dry_run"] = True
                failed_metadata["confirmation_required"] = True
                failed_metadata.pop("confirmed_at", None)
                failed_metadata.pop("queued_at", None)
                await ImportJobRepository.update_job(
                    db=db,
                    import_job=failed_job,
                    job_update=ImportJobUpdate(
                        status=ImportJobStatus.COMPLETED,
                        error_message="Could not queue the background import worker. Try confirming again.",
                        completed_at=utc_now(),
                        confirmed_fingerprint=None,
                        metadata_json=failed_metadata,
                    ),
                )
                await db.commit()
            raise BadRequestException(
                detail="Could not queue the background import worker."
            ) from exc

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
    async def retry_stale_import(
        db: AsyncSession,
        *,
        actor,
        job_id: UUID,
    ) -> ImportJobDetailResponse:
        """Requeue a stale processing job without replaying committed rows."""

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
            lock=True,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")
        if import_job.status != ImportJobStatus.PROCESSING:
            raise BadRequestException(detail="Only processing import jobs can be retried.")

        metadata_json = dict(import_job.metadata_json or {})
        if not _job_is_stale(import_job, metadata_json):
            raise ConflictException(
                detail=(
                    "This import is still active. Retry is available only after progress has been stale for "
                    f"{settings.BULK_IMPORT_STALE_AFTER_MINUTES} minutes."
                )
            )

        retry_attempt = int(metadata_json.get("retry_attempt") or 0) + 1
        metadata_json["retry_attempt"] = retry_attempt
        metadata_json["retry_requested_at"] = utc_now().isoformat()
        metadata_json.pop("background_import_started_at", None)
        await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(metadata_json=metadata_json, error_message=None),
        )
        await db.commit()

        from app.core.queue.arq import enqueue_bulk_import_job

        queued = await enqueue_bulk_import_job(
            job_id=str(import_job.id),
            tenant_id=str(actor.tenant_id),
            actor_id=str(actor.id),
            notify_on_completion=bool(metadata_json.get("notify_on_completion", True)),
            retry_attempt=retry_attempt,
        )
        if not queued:
            raise ConflictException(detail="This stale import retry is already queued.")

        refreshed_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
            include_children=True,
        )
        if refreshed_job is None:
            raise NotFoundException(detail="Import job not found after retry queueing.")
        return ImportJobDetailResponse.model_validate(refreshed_job)

    @staticmethod
    async def _mark_job_failed(
        db: AsyncSession,
        *,
        import_job: ImportJob,
        actor_id: UUID,
        error_message: str,
    ) -> None:
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
        await RealtimePublisher.publish_deferred_after_commit(db)
        await _publish_job_event(
            event_type="bulk_import.failed",
            tenant_id=import_job.tenant_id,
            actor_id=actor_id,
            import_job=import_job,
        )

    @staticmethod
    async def process_confirmed_import_job(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        job_id: UUID,
        notify_on_completion: bool = True,
    ) -> dict[str, int | str]:
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

        already_started = bool(metadata_json.get("background_import_started_at"))
        if already_started and not _job_is_stale(import_job, metadata_json):
            return {
                "status": "already_started",
                "processed": int(import_job.processed_rows or 0),
                "created": int(import_job.successful_rows or 0),
                "failed": int(import_job.failed_rows or 0),
            }

        if already_started:
            metadata_json["background_import_recovered_at"] = utc_now().isoformat()
            metadata_json["recovery_count"] = int(metadata_json.get("recovery_count") or 0) + 1
        metadata_json["background_import_started_at"] = utc_now().isoformat()
        metadata_json["last_progress_at"] = utc_now().isoformat()
        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(metadata_json=metadata_json),
        )
        await db.commit()
        await _publish_job_event(
            event_type="bulk_import.started",
            tenant_id=tenant_id,
            actor_id=actor_id,
            import_job=import_job,
        )

        actor = await TenantAdminRepository.get_by_id(db=db, admin_id=actor_id)
        if actor is None:
            await BulkImportLiveService._mark_job_failed(
                db=db,
                import_job=import_job,
                actor_id=actor_id,
                error_message="Tenant admin that started the import no longer exists.",
            )
            return {"status": "failed", "processed": 0, "created": 0, "failed": 1}

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=tenant_id)
        if tenant is None:
            await BulkImportLiveService._mark_job_failed(
                db=db,
                import_job=import_job,
                actor_id=actor_id,
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
                actor_id=actor_id,
                error_message="No staged rows found for background import.",
            )
            return {"status": "failed", "processed": 0, "created": 0, "failed": 1}

        metadata_json = dict(import_job.metadata_json or {})
        invalid_rows = int(metadata_json.get("invalid_rows") or 0)
        result_rows = _terminal_result_rows(metadata_json)
        completed_row_numbers = {
            int(row.get("row_number") or 0)
            for row in result_rows
            if int(row.get("row_number") or 0) > 0
        }
        created_count = sum(1 for row in result_rows if row.get("status") == "created")
        processing_failed_count = sum(1 for row in result_rows if row.get("status") == "failed")

        remaining_staged_rows = [
            row for row in staged_rows if row.row_number not in completed_row_numbers
        ]
        validation_results = [
            _validation_result_from_staged_row(row) for row in remaining_staged_rows
        ]

        try:
            for chunk in chunk_import_items(
                items=validation_results,
                chunk_size=LIVE_IMPORT_CHUNK_SIZE,
            ):
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
                    except (
                        BadRequestException,
                        ConflictException,
                        NotFoundException,
                        ValidationError,
                    ) as exc:
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
                        error_message = (
                            "Row failed because of a duplicate or invalid database value."
                        )
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
                await _publish_job_event(
                    event_type="bulk_import.progress",
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    import_job=import_job,
                )
                if created_count > 0:
                    await AuthIdentityService.invalidate_after_commit(db)

            successful_rows = created_count
            failed_rows = invalid_rows + processing_failed_count
            final_status = BulkImportService.resolve_final_status(
                successful_rows=successful_rows,
                failed_rows=failed_rows,
            )

            metadata_json = dict(import_job.metadata_json or {})
            metadata_json["result_rows"] = _sorted_result_rows(result_rows)
            metadata_json["background_import_completed_at"] = utc_now().isoformat()
            metadata_json["last_progress_at"] = utc_now().isoformat()
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
                    await BulkImportCommunicationService.create_failure_notification(
                        db=db,
                        tenant_id=tenant_id,
                        recipient_admin_id=actor_id,
                        import_job=import_job,
                    )
                else:
                    await BulkImportCommunicationService.create_completion_notification(
                        db=db,
                        tenant_id=tenant_id,
                        recipient_admin_id=actor_id,
                        import_job=import_job,
                    )

            if successful_rows > 0:
                await SubscriptionFeatureService.invalidate_tenant_subscription_state(tenant_id)

            await db.commit()
            await RealtimePublisher.publish_deferred_after_commit(db)
            await _publish_job_event(
                event_type=f"bulk_import.{final_status.value}",
                tenant_id=tenant_id,
                actor_id=actor_id,
                import_job=import_job,
            )

            if successful_rows > 0:
                await AuthIdentityService.invalidate_after_commit(db)
                try:
                    from app.modules.metrics.cache import (
                        invalidate_superadmin_dashboard_cache,
                        invalidate_tenant_admin_dashboard_cache,
                    )

                    await invalidate_tenant_admin_dashboard_cache(tenant_id)
                    await invalidate_superadmin_dashboard_cache()
                except Exception:
                    pass

            return {
                "status": final_status.value,
                "processed": int(import_job.processed_rows or 0),
                "created": successful_rows,
                "failed": failed_rows,
            }
        except Exception as exc:
            AuthIdentityService.discard_pending_invalidations(db)
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
                    actor_id=actor_id,
                    error_message=str(exc),
                )
            return {
                "status": "failed",
                "processed": created_count + processing_failed_count,
                "created": created_count,
                "failed": processing_failed_count + 1,
            }
