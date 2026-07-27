import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.student_academics.schemas import (
    ClassSubjectArchiveRequest,
    ClassSubjectResponse,
    ClassSubjectRestoreRequest,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(
    prefix="/class-subjects",
    tags=["Class Subjects"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


@router.post(
    "/{class_subject_id}/activate",
    response_model=ClassSubjectResponse,
)
async def activate_class_subject(
    class_subject_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    return await StudentAcademicService.activate_class_subject(
        db=db,
        tenant_id=current_admin.tenant_id,
        class_subject_id=class_subject_id,
    )


@router.post(
    "/{class_subject_id}/deactivate",
    response_model=ClassSubjectResponse,
)
async def deactivate_class_subject(
    class_subject_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    return await StudentAcademicService.deactivate_class_subject(
        db=db,
        tenant_id=current_admin.tenant_id,
        class_subject_id=class_subject_id,
    )


@router.post(
    "/{class_subject_id}/archive",
    response_model=ClassSubjectResponse,
)
async def archive_class_subject(
    class_subject_id: uuid.UUID,
    payload: ClassSubjectArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    return await StudentAcademicService.archive_class_subject(
        db=db,
        tenant_id=current_admin.tenant_id,
        class_subject_id=class_subject_id,
        admin_id=current_admin.id,
    )


@router.post(
    "/{class_subject_id}/restore",
    response_model=ClassSubjectResponse,
)
async def restore_class_subject(
    class_subject_id: uuid.UUID,
    payload: ClassSubjectRestoreRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    return await StudentAcademicService.restore_class_subject(
        db=db,
        tenant_id=current_admin.tenant_id,
        class_subject_id=class_subject_id,
    )


@router.delete(
    "/{class_subject_id}",
    response_model=ClassSubjectResponse,
)
async def delete_class_subject(
    class_subject_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    return await StudentAcademicService.delete_class_subject(
        db=db,
        tenant_id=current_admin.tenant_id,
        class_subject_id=class_subject_id,
    )
