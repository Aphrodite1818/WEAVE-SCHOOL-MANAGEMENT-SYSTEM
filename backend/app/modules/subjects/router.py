from typing import Annotated, Literal, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.modules.subjects.models import Subject
from app.modules.subjects.repository import SubjectRepository
from app.modules.subjects.schemas import (
    SubjectActivateRequest,
    SubjectArchiveRequest,
    SubjectCreate,
    SubjectDeactivateRequest,
    SubjectDeleteRequest,
    SubjectListResponse,
    SubjectRestoreRequest,
    SubjectResponse,
    SubjectUpdate,
)
from app.modules.subjects.service import SubjectService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(tags=["Subjects"])

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentSubjectViewer: TypeAlias = Annotated[
    TenantAdmin | Teacher, Depends(get_current_tenant_member)
]


async def _subject_response(
    db: AsyncSession,
    subject: Subject,
    *,
    include_delete_eligibility: bool = False,
) -> SubjectResponse:
    response = SubjectResponse.model_validate(subject)
    if not include_delete_eligibility:
        return response

    counts = await SubjectRepository.count_dependencies(
        db=db,
        tenant_id=subject.tenant_id,
        subject_id=subject.id,
    )
    return response.model_copy(
        update={
            "dependency_counts": counts,
            "can_delete": not SubjectService._has_any_usage(counts),
        }
    )


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
    return await SubjectService.create_subject(
        db=db,
        actor=current_user,
        subject_data=payload,
    )


@router.get(
    "",
    response_model=SubjectListResponse,
    summary="List subjects",
)
async def list_subjects(
    db: DbSession,
    current_user: CurrentSubjectViewer,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    is_active: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    lifecycle_status: Literal["active", "inactive", "archived"] | None = Query(default=None),
) -> SubjectListResponse:
    subjects, total = await SubjectService.list_subjects(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        is_active=is_active,
        include_archived=include_archived and isinstance(current_user, TenantAdmin),
        search=search,
        lifecycle_status=(lifecycle_status if isinstance(current_user, TenantAdmin) else None),
    )

    if not isinstance(current_user, TenantAdmin):
        return SubjectListResponse(
            items=[SubjectResponse.model_validate(subject) for subject in subjects],
            total=total,
        )

    dependency_map = await SubjectRepository.count_total_dependencies_for_subjects(
        db=db,
        tenant_id=current_user.tenant_id,
        subject_ids=[subject.id for subject in subjects],
    )
    items: list[SubjectResponse] = []
    for subject in subjects:
        counts = dependency_map.get(subject.id, {})
        items.append(
            SubjectResponse.model_validate(subject).model_copy(
                update={
                    "dependency_counts": counts,
                    "can_delete": not any(count > 0 for count in counts.values()),
                }
            )
        )
    return SubjectListResponse(items=items, total=total)


@router.get(
    "/{subject_id}",
    response_model=SubjectResponse,
    summary="Get a subject",
)
async def get_subject(
    subject_id: UUID,
    db: DbSession,
    current_user: CurrentSubjectViewer,
) -> SubjectResponse:
    subject = await SubjectService.get_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    return await _subject_response(
        db,
        subject,
        include_delete_eligibility=isinstance(current_user, TenantAdmin),
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
    payload: SubjectActivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    _ = payload.confirmation
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
    payload: SubjectDeactivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> Subject:
    _ = payload.confirmation
    subject = await SubjectService.deactivate_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return subject


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
    _ = payload.confirmation
    subject = await SubjectService.archive_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return subject


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
    _ = payload.confirmation
    subject = await SubjectService.restore_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return subject


@router.delete(
    "/{subject_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a never-used subject",
)
async def delete_subject(
    subject_id: UUID,
    payload: SubjectDeleteRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> None:
    _ = payload.confirmation
    await SubjectService.hard_delete_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
