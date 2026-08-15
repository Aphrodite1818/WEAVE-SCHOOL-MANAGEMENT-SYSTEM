import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin, get_current_tenant_member
from app.modules.parents.models import Parent
from app.modules.student_academics.schemas import (
    LevelSubjectActivateRequest,
    LevelSubjectArchiveRequest,
    LevelSubjectBulkCreate,
    LevelSubjectCreate,
    LevelSubjectDeactivateRequest,
    LevelSubjectDeleteRequest,
    LevelSubjectListResponse,
    LevelSubjectResponse,
    LevelSubjectRestoreRequest,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(prefix="/academic-levels", tags=["Level Subjects"])
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent, Depends(get_current_tenant_member)
]


@router.get("/{academic_level_id}/subjects", response_model=LevelSubjectListResponse)
async def list_level_subjects(
    academic_level_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantMember,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> LevelSubjectListResponse:
    items, total = await StudentAcademicService.list_level_subjects(
        db,
        current_user.tenant_id,
        academic_level_id=academic_level_id,
        active_only=active_only,
        include_archived=include_archived and isinstance(current_user, TenantAdmin),
    )
    return LevelSubjectListResponse(items=items, total=total)


@router.post(
    "/{academic_level_id}/subjects",
    response_model=LevelSubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_level_subject(
    academic_level_id: uuid.UUID,
    payload: LevelSubjectCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    return await StudentAcademicService.create_level_subject(
        db, current_admin.tenant_id, academic_level_id, payload
    )


@router.post(
    "/{academic_level_id}/subjects/bulk",
    response_model=list[LevelSubjectResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_level_subjects_bulk(
    academic_level_id: uuid.UUID,
    payload: LevelSubjectBulkCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> list[LevelSubjectResponse]:
    return await StudentAcademicService.create_level_subjects_bulk(
        db, current_admin.tenant_id, academic_level_id, payload
    )


@router.post("/subjects/{level_subject_id}/activate", response_model=LevelSubjectResponse)
async def activate_level_subject(
    level_subject_id: uuid.UUID,
    payload: LevelSubjectActivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    _ = payload.confirmation
    return await StudentAcademicService.activate_level_subject(
        db, current_admin.tenant_id, level_subject_id
    )


@router.post("/subjects/{level_subject_id}/deactivate", response_model=LevelSubjectResponse)
async def deactivate_level_subject(
    level_subject_id: uuid.UUID,
    payload: LevelSubjectDeactivateRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    _ = payload.confirmation
    return await StudentAcademicService.deactivate_level_subject(
        db, current_admin.tenant_id, level_subject_id
    )


@router.post("/subjects/{level_subject_id}/archive", response_model=LevelSubjectResponse)
async def archive_level_subject(
    level_subject_id: uuid.UUID,
    payload: LevelSubjectArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    _ = payload.confirmation
    return await StudentAcademicService.archive_level_subject(
        db, current_admin.tenant_id, level_subject_id, current_admin.id
    )


@router.post("/subjects/{level_subject_id}/restore", response_model=LevelSubjectResponse)
async def restore_level_subject(
    level_subject_id: uuid.UUID,
    payload: LevelSubjectRestoreRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    _ = payload.confirmation
    return await StudentAcademicService.restore_level_subject(
        db, current_admin.tenant_id, level_subject_id
    )


@router.delete("/subjects/{level_subject_id}", response_model=LevelSubjectResponse)
async def delete_level_subject(
    level_subject_id: uuid.UUID,
    payload: LevelSubjectDeleteRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> LevelSubjectResponse:
    _ = payload.confirmation
    return await StudentAcademicService.delete_level_subject(
        db, current_admin.tenant_id, level_subject_id
    )
