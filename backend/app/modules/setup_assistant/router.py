"""Assisted setup-only actions for first-time tenant administrators."""

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.modules.classes.schemas import AcademicLevelResponse, ClassRoomResponse
from app.modules.classes.service import AcademicLevelService, ClassRoomService
from app.modules.subjects.schemas import SubjectResponse
from app.modules.subjects.service import SubjectService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.tenant_admins.models import TenantAdmin

router = APIRouter(
    prefix="/tenant-admin/setup-assistant",
    tags=["Tenant Admin Setup Assistant"],
)
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


class SetupAssistantRemoveClassRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupAssistantRemoveSubjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SetupAssistantRemoveLevelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/levels/{academic_level_id}/remove", response_model=AcademicLevelResponse)
async def remove_level_from_setup(
    academic_level_id: uuid.UUID,
    payload: SetupAssistantRemoveLevelRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> AcademicLevelResponse:
    """Remove an unused, arm-less academic level from assisted setup."""

    _ = payload
    return await AcademicLevelService.purge_setup_level(
        db=db,
        actor=current_user,
        academic_level_id=academic_level_id,
    )


@router.post("/classes/{class_id}/remove", response_model=ClassRoomResponse)
async def remove_class_from_setup(
    class_id: uuid.UUID,
    payload: SetupAssistantRemoveClassRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> ClassRoomResponse:
    """Remove a class from the assisted setup flow without lifecycle confirmations."""

    _ = payload
    classroom = await ClassRoomService.purge_setup_classroom(
        db=db,
        actor=current_user,
        class_id=class_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(
        current_user.tenant_id,
    )
    return classroom


@router.post("/subjects/{subject_id}/remove", response_model=SubjectResponse)
async def remove_subject_from_setup(
    subject_id: uuid.UUID,
    payload: SetupAssistantRemoveSubjectRequest,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> SubjectResponse:
    """Remove a never-used subject from the assisted setup flow."""

    _ = payload
    subject = await SubjectService.hard_delete_subject(
        db=db,
        actor=current_user,
        subject_id=subject_id,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(
        current_user.tenant_id,
    )
    return subject
