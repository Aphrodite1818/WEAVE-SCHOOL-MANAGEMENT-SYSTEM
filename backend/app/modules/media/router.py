# ========================== #
#      media/router.py       #
# ========================== #

"""Tenant and profile media API routes."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_actor, get_current_tenant_admin
from app.core.exceptions import ForbiddenException
from app.modules.media.global_teacher_profile import GlobalTeacherProfileMediaService
from app.modules.media.models import (
    MediaOwnerType,
    MediaPurpose,
    MediaStatus,
    MediaVisibility,
)
from app.modules.media.schemas import (
    MediaAssetListResponse,
    MediaAssetResponse,
    MediaDeleteResponse,
    MediaSignedUrlResponse,
    MediaUploadResponse,
)
from app.modules.media.service import MediaService
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher, TeacherAccount


router = APIRouter(
    prefix="/media",
    tags=["Media"],
)

CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentProfileMediaActor: TypeAlias = Annotated[
    TenantAdmin | TeacherAccount | Teacher | Student | object,
    Depends(get_current_actor),
]


@router.post(
    "/school-logo",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_school_logo(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    file: UploadFile = File(...),
) -> MediaUploadResponse:
    """Upload or replace the current tenant school logo."""

    return await MediaService.upload_school_logo(
        db=db,
        actor=current_user,
        file=file,
    )


@router.delete(
    "/school-logo",
    response_model=MediaDeleteResponse,
)
async def delete_school_logo(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    delete_object: bool = Query(default=False),
) -> MediaDeleteResponse:
    """Delete/detach the current tenant school logo."""

    return await MediaService.delete_current_school_logo(
        db=db,
        actor=current_user,
        delete_object=delete_object,
    )


@router.post(
    "/students/{student_id}/passport-photo",
    response_model=MediaUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_student_passport_photo(
    student_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    file: UploadFile = File(...),
) -> MediaUploadResponse:
    """Upload or replace a student's passport photo."""

    return await MediaService.upload_student_passport(
        db=db,
        actor=current_user,
        student_id=student_id,
        file=file,
    )


@router.delete(
    "/students/{student_id}/passport-photo",
    response_model=MediaDeleteResponse,
)
async def delete_student_passport_photo(
    student_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    delete_object: bool = Query(default=False),
) -> MediaDeleteResponse:
    """Delete/detach a student's current passport photo."""

    return await MediaService.delete_current_student_passport(
        db=db,
        actor=current_user,
        student_id=student_id,
        delete_object=delete_object,
    )


@router.post(
    "/teachers/{teacher_id}/passport-photo",
    status_code=status.HTTP_201_CREATED,
)
async def upload_teacher_passport_photo(
    teacher_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    file: UploadFile = File(...),
) -> dict[str, object]:
    """Upload a teacher-account photo through one tenant membership."""

    return await GlobalTeacherProfileMediaService.upload_for_membership(
        db=db,
        tenant_id=current_user.tenant_id,
        membership_id=teacher_id,
        file=file,
    )


@router.delete(
    "/teachers/{teacher_id}/passport-photo",
)
async def delete_teacher_passport_photo(
    teacher_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    delete_object: bool = Query(default=True),
) -> dict[str, object]:
    """Delete a teacher account's current photo through a membership."""

    return await GlobalTeacherProfileMediaService.delete_for_membership(
        db=db,
        tenant_id=current_user.tenant_id,
        membership_id=teacher_id,
        delete_object=delete_object,
    )


@router.post(
    "/profile/passport-photo",
    status_code=status.HTTP_201_CREATED,
)
async def upload_profile_passport_photo(
    db: DbSession,
    current_user: CurrentProfileMediaActor,
    file: UploadFile = File(...),
) -> MediaUploadResponse | dict[str, object]:
    """Upload the authenticated actor's supported profile photo."""

    if isinstance(current_user, (TeacherAccount, Teacher)):
        return await GlobalTeacherProfileMediaService.upload(
            db=db,
            actor=current_user,
            file=file,
        )

    if isinstance(current_user, (TenantAdmin, Student)):
        return await MediaService.upload_profile_passport(
            db=db,
            actor=current_user,
            file=file,
        )

    raise ForbiddenException(detail="This account does not support profile photo uploads")


@router.delete(
    "/profile/passport-photo",
)
async def delete_profile_passport_photo(
    db: DbSession,
    current_user: CurrentProfileMediaActor,
    delete_object: bool = Query(default=True),
) -> MediaDeleteResponse | dict[str, object]:
    """Delete the authenticated actor's supported profile photo."""

    if isinstance(current_user, (TeacherAccount, Teacher)):
        return await GlobalTeacherProfileMediaService.delete(
            db=db,
            actor=current_user,
            delete_object=delete_object,
        )

    if isinstance(current_user, (TenantAdmin, Student)):
        return await MediaService.delete_current_profile_passport(
            db=db,
            actor=current_user,
            delete_object=delete_object,
        )

    raise ForbiddenException(detail="This account does not support profile photo uploads")


@router.get(
    "/assets",
    response_model=MediaAssetListResponse,
)
async def list_media_assets(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    owner_type: MediaOwnerType | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    purpose: MediaPurpose | None = Query(default=None),
    visibility: MediaVisibility | None = Query(default=None),
    status_filter: MediaStatus | None = Query(default=None, alias="status"),
    current_only: bool = Query(default=True),
) -> MediaAssetListResponse:
    """List media assets for the current tenant."""

    return await MediaService.list_media_assets(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        owner_type=owner_type,
        owner_id=owner_id,
        purpose=purpose,
        visibility=visibility,
        status=status_filter,
        current_only=current_only,
    )


@router.get(
    "/assets/current",
    response_model=MediaAssetResponse,
)
async def get_current_media_asset(
    db: DbSession,
    current_user: CurrentTenantAdmin,
    owner_type: MediaOwnerType = Query(...),
    owner_id: UUID = Query(...),
    purpose: MediaPurpose = Query(...),
) -> MediaAssetResponse:
    """Return the current media asset for an owner/purpose pair."""

    return await MediaService.get_current_media_for_owner(
        db=db,
        actor=current_user,
        owner_type=owner_type,
        owner_id=owner_id,
        purpose=purpose,
    )


@router.get(
    "/assets/{media_asset_id}",
    response_model=MediaAssetResponse,
)
async def get_media_asset(
    media_asset_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
) -> MediaAssetResponse:
    """Return one media asset by ID."""

    return await MediaService.get_media_asset(
        db=db,
        actor=current_user,
        media_asset_id=media_asset_id,
    )


@router.get(
    "/assets/{media_asset_id}/signed-url",
    response_model=MediaSignedUrlResponse,
)
async def create_media_signed_url(
    media_asset_id: UUID,
    db: DbSession,
    current_user: CurrentTenantAdmin,
    expires_in_seconds: int = Query(default=300, ge=60, le=3600),
) -> MediaSignedUrlResponse:
    """Create a temporary signed URL for a private media asset."""

    return await MediaService.create_signed_url_for_asset(
        db=db,
        actor=current_user,
        media_asset_id=media_asset_id,
        expires_in_seconds=expires_in_seconds,
    )
