# ========================= #
#   bulk_imports_router.py  #
# ========================= #

"""Tenant admin bulk import routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.bulk_imports.models import ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.result_writer import create_result_report
from app.modules.bulk_imports.schemas import (
    ImportJobDetailResponse,
    ImportJobListResponse,
    ImportRowErrorListResponse,
    ImportTemplateResponse,
)
from app.modules.bulk_imports.service import BulkImportService
from app.modules.metrics.cache import (
    invalidate_superadmin_dashboard_cache,
    invalidate_tenant_admin_dashboard_cache,
)
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/imports",
    tags=["Bulk Imports"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.get(
    "/templates",
    response_model=list[ImportTemplateResponse],
)
async def list_import_templates(
    current_user: CurrentTenantAdmin,
) -> list[ImportTemplateResponse]:
    """List supported XLSX import templates."""

    _ = current_user
    return BulkImportService.list_templates()


@router.get(
    "/templates/{resource_type}",
    response_model=ImportTemplateResponse,
)
async def get_import_template(
    resource_type: ImportResourceType,
    current_user: CurrentTenantAdmin,
) -> ImportTemplateResponse:
    """Return one supported XLSX import template description."""

    _ = current_user
    return BulkImportService.get_template(resource_type=resource_type)


@router.get(
    "/templates/{resource_type}/download",
)
async def download_import_template(
    resource_type: ImportResourceType,
    current_user: CurrentTenantAdmin,
) -> Response:
    """Download a signed backend-generated XLSX import template file."""

    template = BulkImportService.generate_template_file(
        tenant_id=current_user.tenant_id,
        resource_type=resource_type,
    )

    return Response(
        content=template.content_bytes,
        media_type=template.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{template.filename}"',
        },
    )


@router.post(
    "/{resource_type}/dry-run",
    response_model=ImportJobDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def dry_run_bulk_import(
    resource_type: ImportResourceType,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    file: UploadFile = File(...),
    notify_on_completion: bool = Form(default=True),
) -> ImportJobDetailResponse:
    """Validate and stage a bulk import XLSX file without creating records."""

    return await BulkImportService.create_dry_run_from_upload(
        db=db,
        actor=current_user,
        resource_type=resource_type,
        upload_file=file,
        notify_on_completion=notify_on_completion,
    )


@router.post(
    "/{job_id}/confirm",
    response_model=ImportJobDetailResponse,
)
async def confirm_bulk_import(
    job_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    notify_on_completion: bool = Query(default=True),
) -> ImportJobDetailResponse:
    """Confirm a staged dry-run import and create records."""

    import_job = await BulkImportService.confirm_import_from_dry_run(
        db=db,
        actor=current_user,
        job_id=job_id,
        notify_on_completion=notify_on_completion,
    )

    if import_job.successful_rows > 0:
        await invalidate_tenant_admin_dashboard_cache(current_user.tenant_id)
        await invalidate_superadmin_dashboard_cache()

    return import_job


@router.post(
    "/{resource_type}",
    response_model=ImportJobDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_bulk_import(
    resource_type: ImportResourceType,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    file: UploadFile = File(...),
    dry_run: bool = Form(default=False),
    notify_on_completion: bool = Form(default=True),
) -> ImportJobDetailResponse:
    """Backward-compatible dry-run upload endpoint.

    Real imports now require confirming the returned dry-run import job.
    """

    return await BulkImportService.create_import_from_upload(
        db=db,
        actor=current_user,
        resource_type=resource_type,
        upload_file=file,
        dry_run=dry_run,
        notify_on_completion=notify_on_completion,
    )


@router.get(
    "",
    response_model=ImportJobListResponse,
)
async def list_bulk_import_jobs(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    resource_type: ImportResourceType | None = Query(default=None),
    status_filter: ImportJobStatus | None = Query(default=None, alias="status"),
) -> ImportJobListResponse:
    """List import jobs for the current tenant."""

    return await BulkImportService.list_jobs(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        resource_type=resource_type,
        status=status_filter,
    )


@router.get(
    "/{job_id}",
    response_model=ImportJobDetailResponse,
)
async def get_bulk_import_job(
    job_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ImportJobDetailResponse:
    """Return one import job."""

    return await BulkImportService.get_job(
        db=db,
        actor=current_user,
        job_id=job_id,
    )


@router.get(
    "/{job_id}/errors",
    response_model=ImportRowErrorListResponse,
)
async def list_bulk_import_errors(
    job_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> ImportRowErrorListResponse:
    """List row-level errors for one import job."""

    return await BulkImportService.list_job_errors(
        db=db,
        actor=current_user,
        job_id=job_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{job_id}/result",
)
async def download_bulk_import_result(
    job_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Response:
    """Download the CSV result report for one import job."""

    resource_type, result_rows = await BulkImportService.get_result_rows(
        db=db,
        actor=current_user,
        job_id=job_id,
    )
    result_file = create_result_report(
        resource_type=resource_type,
        result_rows=result_rows,
    )

    return Response(
        content=result_file.content_bytes,
        media_type=result_file.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{result_file.filename}"',
        },
    )
