"""Optimized bulk-import entry points for expensive dry-run validation paths."""

from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.bulk_imports.models import ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.optimized_validation import (
    preflight_student_parent_invitations_batch,
    resolve_student_class_references_batch,
)
from app.modules.bulk_imports.parsers import BulkImportParser
from app.modules.bulk_imports.repository import (
    ImportJobRepository,
    ImportRowErrorRepository,
    ImportStagedRowRepository,
)
from app.modules.bulk_imports.schemas import (
    ImportJobCreate,
    ImportJobDetailResponse,
    ImportJobUpdate,
    ImportRowErrorCreate,
)
from app.modules.bulk_imports.service import (
    BulkImportService,
    build_import_source_fingerprint,
    build_validation_error_items,
    duplicate_import_message,
    utc_now,
)
from app.modules.bulk_imports.validators import BulkImportValidator
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode
from app.modules.tenant_admins.models import TenantAdmin


class OptimizedBulkImportService:
    """Dry-run orchestration with bounded hierarchy and parent-email reads."""

    @staticmethod
    async def create_dry_run_from_upload(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        upload_file: UploadFile,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        BulkImportService.ensure_supported_resource_type(resource_type)
        await SubscriptionFeatureService.ensure_feature_enabled(
            db=db,
            tenant_id=actor.tenant_id,
            feature=FeatureCode.BULK_IMPORT,
        )

        parsed_file = await BulkImportParser.parse_upload(upload_file)
        if not parsed_file.rows:
            raise BadRequestException(detail="Import file does not contain any data rows.")

        BulkImportService.validate_import_template_contract(
            tenant_id=actor.tenant_id,
            endpoint_resource_type=resource_type,
            parsed_file=parsed_file,
        )
        row_items = BulkImportService.build_row_items(
            resource_type=resource_type,
            parsed_file=parsed_file,
        )
        source_fingerprint = build_import_source_fingerprint(
            resource_type=resource_type,
            template_version=parsed_file.metadata.get("_import_template_version"),
            rows=[
                (row_number, normalized_row)
                for row_number, _, normalized_row, _ in row_items
            ],
        )
        existing_import = await ImportJobRepository.get_confirmed_job_by_fingerprint(
            db=db,
            tenant_id=actor.tenant_id,
            resource_type=resource_type,
            source_fingerprint=source_fingerprint,
        )
        if existing_import is not None:
            raise ConflictException(detail=duplicate_import_message(existing_import))

        import_job = await ImportJobRepository.create_job(
            db=db,
            tenant_id=actor.tenant_id,
            job_data=ImportJobCreate(
                resource_type=resource_type,
                file_type=parsed_file.file_type,
                original_filename=upload_file.filename
                or f"{resource_type.value}_import.{parsed_file.file_type.value}",
                file_size_bytes=parsed_file.file_size_bytes,
                source_fingerprint=source_fingerprint,
                created_by_admin_id=actor.id,
                metadata_json={
                    "dry_run": True,
                    "confirmation_required": True,
                    "notify_on_completion": notify_on_completion,
                    "template_version": parsed_file.metadata.get("_import_template_version"),
                    "template_headers_hash": parsed_file.metadata.get("_import_headers_hash"),
                    "source_fingerprint": source_fingerprint,
                    "result_rows": [],
                },
            ),
        )
        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=ImportJobStatus.PROCESSING,
                started_at=utc_now(),
                total_rows=len(parsed_file.rows),
            ),
        )

        validation_results = BulkImportValidator.validate_rows(
            resource_type=resource_type,
            row_items=row_items,
        )
        if resource_type == ImportResourceType.STUDENTS:
            await resolve_student_class_references_batch(
                db,
                tenant_id=actor.tenant_id,
                validation_results=validation_results,
            )
            parent_preflight_summary = await preflight_student_parent_invitations_batch(
                db,
                validation_results=validation_results,
            )
        else:
            parent_preflight_summary = {}

        invalid_results = [result for result in validation_results if not result.is_valid]
        valid_results = [result for result in validation_results if result.is_valid]
        validation_error_items: list[ImportRowErrorCreate] = []
        for validation_result in invalid_results:
            validation_error_items.extend(
                build_validation_error_items(
                    import_job_id=import_job.id,
                    validation_result=validation_result,
                )
            )
        if validation_error_items:
            await ImportRowErrorRepository.create_many(
                db=db,
                tenant_id=actor.tenant_id,
                row_error_items=validation_error_items,
            )
        if valid_results:
            await ImportStagedRowRepository.create_many(
                db=db,
                tenant_id=actor.tenant_id,
                import_job_id=import_job.id,
                validation_results=valid_results,
            )

        successful_rows = len(valid_results)
        failed_rows = len(invalid_results)
        result_rows = BulkImportService.build_validation_result_rows(
            validation_results=validation_results,
        )
        final_status = BulkImportService.resolve_final_status(
            successful_rows=successful_rows,
            failed_rows=failed_rows,
        )
        metadata_json = dict(import_job.metadata_json or {})
        metadata_json["result_rows"] = sorted(
            result_rows,
            key=lambda row: int(row.get("row_number") or 0),
        )
        metadata_json["valid_rows"] = len(valid_results)
        metadata_json["invalid_rows"] = len(invalid_results)
        metadata_json["staged_valid_rows"] = len(valid_results)
        metadata_json["dry_run_completed_at"] = utc_now().isoformat()
        metadata_json.update(parent_preflight_summary)

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=final_status,
                total_rows=len(parsed_file.rows),
                processed_rows=len(parsed_file.rows),
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                skipped_rows=0,
                completed_at=utc_now(),
                metadata_json=metadata_json,
            ),
        )
        await db.commit()

        refreshed_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=import_job.id,
            include_children=True,
        )
        if refreshed_job is None:
            raise NotFoundException(detail="Import job not found after dry run.")
        return ImportJobDetailResponse.model_validate(refreshed_job)

    @staticmethod
    async def create_import_from_upload(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        upload_file: UploadFile,
        dry_run: bool = False,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        if not dry_run:
            raise BadRequestException(
                detail=(
                    "Direct bulk imports are disabled. Run dry_run=true first, "
                    "then confirm the import job."
                )
            )
        return await OptimizedBulkImportService.create_dry_run_from_upload(
            db,
            actor=actor,
            resource_type=resource_type,
            upload_file=upload_file,
            notify_on_completion=notify_on_completion,
        )