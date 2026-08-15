import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.modules.classes.schemas import (
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
from app.modules.students.models import Student
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

    return await ClassRoomService.create_classroom(
        db=db,
        actor=current_user,
        payload=payload,
    )


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
    return await ClassRoomService.activate_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )


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
