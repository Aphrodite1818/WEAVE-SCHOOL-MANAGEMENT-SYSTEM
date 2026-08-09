import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.core.exceptions import NotFoundException
from app.modules.classes.schemas import (
    ClassProgressionClearRequest,
    ClassProgressionConfigureRequest,
    ClassProgressionResponse,
    ClassRoomActivateRequest,
    ClassRoomArchiveRequest,
    ClassRoomCreate,
    ClassRoomDeactivateRequest,
    ClassRoomResponse,
    ClassRoomRestoreRequest,
    ClassRoomUpdate,
)
from app.modules.classes.service import ClassRoomService
from app.modules.parents.models import Parent
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    ClassSubjectActivateRequest,
    ClassSubjectBulkCreate,
    ClassSubjectCreate,
    ClassSubjectListResponse,
    ClassSubjectResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import Student
from app.modules.subscriptions.quota_lock import acquire_resource_quota_lock
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode, ResourceLimitCode
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/classes",
    tags=["Classes"],
)
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTenantMember: TypeAlias = Annotated[
    TenantAdmin | Teacher | Student | Parent,
    Depends(get_current_tenant_member),
]


@router.post(
    "",
    response_model=ClassRoomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_classroom(
    payload: ClassRoomCreate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    """Create a new classroom."""

    await acquire_resource_quota_lock(
        db,
        tenant_id=current_user.tenant_id,
        resource=ResourceLimitCode.CLASSES,
    )
    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_user.tenant_id,
        resource=ResourceLimitCode.CLASSES,
    )
    classroom = await ClassRoomService.create_classroom(
        db=db,
        actor=current_user,
        payload=payload,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.get(
    "",
    response_model=list[ClassRoomResponse],
)
async def get_all_classrooms(
    db: DbSession,
    current_user: CurrentTenantMember,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
) -> list[ClassRoomResponse]:
    """Get classrooms visible to the current actor."""
    include_archived = include_archived and isinstance(current_user, TenantAdmin)

    if active_only:
        return await ClassRoomService.get_active_classrooms(
            db=db,
            actor=current_user,
            skip=skip,
            limit=limit,
        )

    return await ClassRoomService.get_all_classrooms(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        include_archived=include_archived,
    )


@router.get(
    "/{class_id}",
    response_model=ClassRoomResponse,
)
async def get_classroom_by_id(
    class_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantMember,
) -> ClassRoomResponse:
    """Get classroom by ID."""

    return await ClassRoomService.get_classroom_by_id(
        db=db,
        actor=current_user,
        class_id=class_id,
    )


@router.patch(
    "/{class_id}",
    response_model=ClassRoomResponse,
)
async def update_classroom(
    class_id: uuid.UUID,
    payload: ClassRoomUpdate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    """Update classroom."""

    return await ClassRoomService.update_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
        payload=payload,
    )


@router.put(
    "/{class_id}/progression",
    response_model=ClassProgressionResponse,
)
async def configure_class_progression(
    class_id: uuid.UUID,
    payload: ClassProgressionConfigureRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassProgressionResponse:
    """Configure the next-class or terminal progression state for a classroom."""

    return await ClassRoomService.configure_class_progression(
        db=db,
        actor=current_user,
        class_id=class_id,
        payload=payload,
    )


@router.post(
    "/{class_id}/progression/clear",
    response_model=ClassProgressionResponse,
)
async def clear_class_progression(
    class_id: uuid.UUID,
    payload: ClassProgressionClearRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassProgressionResponse:
    """Clear the progression configuration for a classroom."""

    return await ClassRoomService.clear_class_progression(
        db=db,
        actor=current_user,
        class_id=class_id,
        payload=payload,
    )


@router.post(
    "/{class_id}/activate",
    response_model=ClassRoomResponse,
)
async def activate_classroom(
    class_id: uuid.UUID,
    payload: ClassRoomActivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    _ = payload.confirmation
    await acquire_resource_quota_lock(
        db,
        tenant_id=current_user.tenant_id,
        resource=ResourceLimitCode.CLASSES,
    )
    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_user.tenant_id,
        resource=ResourceLimitCode.CLASSES,
    )
    classroom = await ClassRoomService.activate_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.post(
    "/{class_id}/deactivate",
    response_model=ClassRoomResponse,
)
async def deactivate_classroom(
    class_id: uuid.UUID,
    payload: ClassRoomDeactivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    """Soft delete classroom."""

    _ = payload.confirmation
    classroom = await ClassRoomService.deactivate_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.post(
    "/{class_id}/archive",
    response_model=ClassRoomResponse,
)
async def archive_classroom(
    class_id: uuid.UUID,
    payload: ClassRoomArchiveRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    _ = payload.confirmation
    classroom = await ClassRoomService.archive_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.post(
    "/{class_id}/restore",
    response_model=ClassRoomResponse,
)
async def restore_classroom(
    class_id: uuid.UUID,
    payload: ClassRoomRestoreRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    _ = payload.confirmation
    classroom = await ClassRoomService.restore_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.delete(
    "/{class_id}",
    response_model=ClassRoomResponse,
)
async def delete_classroom_compat_deactivate(
    class_id: uuid.UUID,
    payload: ClassRoomDeactivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    _ = payload.confirmation
    classroom = await ClassRoomService.deactivate_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(current_user.tenant_id)
    return classroom


@router.get(
    "/{class_id}/subjects",
    response_model=ClassSubjectListResponse,
)
async def list_class_subjects(
    class_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentTenantMember,
    active_only: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    lifecycle_status: str | None = Query(default=None, pattern="^(active|inactive|archived)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> ClassSubjectListResponse:
    items, total = await StudentAcademicService.list_class_subjects(
        db=db,
        tenant_id=current_user.tenant_id,
        class_id=class_id,
        active_only=active_only,
        include_archived=include_archived and isinstance(current_user, TenantAdmin),
        lifecycle_status=lifecycle_status,
        skip=skip,
        limit=limit,
    )
    return ClassSubjectListResponse(items=items, total=total)


@router.post(
    "/{class_id}/subjects",
    response_model=ClassSubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_class_subject(
    class_id: uuid.UUID,
    payload: ClassSubjectCreate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_user.tenant_id,
        feature=FeatureCode.ACADEMIC_SETUP,
    )
    return await StudentAcademicService.create_class_subject(
        db=db,
        tenant_id=current_user.tenant_id,
        class_id=class_id,
        payload=payload,
    )


@router.post(
    "/{class_id}/subjects/bulk",
    response_model=list[ClassSubjectResponse],
    status_code=status.HTTP_201_CREATED,
)
async def add_class_subjects_bulk(
    class_id: uuid.UUID,
    payload: ClassSubjectBulkCreate,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> list[ClassSubjectResponse]:
    await SubscriptionFeatureService.ensure_feature_enabled(
        db=db,
        tenant_id=current_user.tenant_id,
        feature=FeatureCode.ACADEMIC_SETUP,
    )
    return await StudentAcademicService.create_class_subjects_bulk(
        db=db,
        tenant_id=current_user.tenant_id,
        class_id=class_id,
        payload=payload,
    )


@router.patch(
    "/{class_id}/subjects/{class_subject_id}/activate",
    response_model=ClassSubjectResponse,
)
async def activate_class_subject(
    class_id: uuid.UUID,
    class_subject_id: uuid.UUID,
    payload: ClassSubjectActivateRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassSubjectResponse:
    """Reactivate a soft-deactivated subject link for a class."""

    _ = payload.confirmation
    class_subject = await StudentAcademicRepository.get_class_subject_by_id(
        db=db,
        tenant_id=current_user.tenant_id,
        class_subject_id=class_subject_id,
    )
    if class_subject is None or class_subject.class_id != class_id:
        raise NotFoundException("Class subject not found.")

    return await StudentAcademicService.activate_class_subject(
        db=db,
        tenant_id=current_user.tenant_id,
        class_subject_id=class_subject_id,
    )
