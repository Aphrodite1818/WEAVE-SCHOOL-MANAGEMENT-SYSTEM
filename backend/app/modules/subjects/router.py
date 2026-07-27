from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_teacher,
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode
from app.modules.subjects.models import Subject
from app.modules.subjects.schemas import (
    SubjectArchiveRequest,
    SubjectCreate,
    SubjectListResponse,
    SubjectRestoreRequest,
    SubjectResponse,
    SubjectUpdate,
)
from app.modules.subjects.service import SubjectService
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(tags=["Subjects"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentSubjectViewer: TypeAlias = Annotated[TenantAdmin | Teacher, Depends(get_current_tenant_member)]


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subject",
)
async def create_subject(
    payload: SubjectCreate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    """Create subject."""

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_user.tenant_id,
        resource=ResourceLimitCode.SUBJECTS,
    )
    subject = await SubjectService.create_subject(
        db=db,
        actor=current_user,
        subject_data=payload,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return subject


@router.get(
    "",
    response_model=SubjectListResponse,
    summary="List subjects",
)
async def list_subjects(
    db: DbSession,
    current_user: CurrentSubjectViewer,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=100),
) -> SubjectListResponse:
    """List subjects."""

    subjects, total = await SubjectService.list_subjects(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        is_active=is_active,
        include_archived=include_archived and isinstance(current_user, TenantAdmin),
        search=search,
    )

    return SubjectListResponse(
        items=[SubjectResponse.model_validate(subject) for subject in subjects],
        total=total,
    )


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Get a subject",
)
async def get_subject(
    subject_id: UUID,
    db: DbSession,
    current_user: CurrentSubjectViewer,
) -> Subject:
    """Return subject."""

    return await SubjectService.get_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )


@router.patch(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Update a subject",
)
async def update_subject(
    subject_id: UUID,
    payload: SubjectUpdate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    """Update subject."""

    return await SubjectService.update_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
        subject_data=payload,
    )


@router.post(
    "/{subject_id}/activate",
    response_model=SubjectResponse,
    summary="Activate a subject",
)
async def activate_subject(
    subject_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    """Activate subject."""

    return await SubjectService.activate_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )


@router.post(
    "/{subject_id}/deactivate",
    response_model=SubjectResponse,
    summary="Deactivate a subject",
)
async def deactivate_subject(
    subject_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    """Deactivate subject."""

    return await SubjectService.deactivate_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )


@router.post(
    "/{subject_id}/archive",
    response_model=SubjectResponse,
    summary="Archive a subject",
)
async def archive_subject(
    subject_id: UUID,
    payload: SubjectArchiveRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    return await SubjectService.archive_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )


@router.post(
    "/{subject_id}/restore",
    response_model=SubjectResponse,
    summary="Restore an archived subject",
)
async def restore_subject(
    subject_id: UUID,
    payload: SubjectRestoreRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    return await SubjectService.restore_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a subject",
)
async def delete_subject(
    subject_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> None:
    """Delete subject."""

    await SubjectService.delete_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
