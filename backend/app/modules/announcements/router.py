import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    TenantActor,
    get_current_superadmin,
    get_current_teacher,
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.modules.announcements.models import AnnouncementReadStatus, AnnouncementStatus
from app.modules.announcements.schemas import (
    AnnouncementArchiveRequest,
    AnnouncementCreate,
    AnnouncementFeedResponse,
    AnnouncementListResponse,
    AnnouncementPublishRequest,
    AnnouncementReadResponse,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.modules.announcements.service import AnnouncementService
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


superadmin_router = APIRouter(prefix="/superadmin/announcements", tags=["Superadmin Announcements"])
tenant_admin_router = APIRouter(prefix="/tenant-admin/announcements", tags=["Tenant Admin Announcements"])
teacher_router = APIRouter(prefix="/teachers/me/announcements", tags=["Teacher Announcements"])
feed_router = APIRouter(prefix="/announcements", tags=["Announcement Feed"])

CurrentSuperadmin: TypeAlias = Annotated[SuperAdmin, Depends(get_current_superadmin)]
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]
CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentTenantMember: TypeAlias = Annotated[TenantActor, Depends(get_current_tenant_member)]


def _list_response(items, total: int) -> AnnouncementListResponse:
    return AnnouncementListResponse(
        items=[AnnouncementResponse.model_validate(item) for item in items],
        total=total,
    )


@superadmin_router.post("", response_model=AnnouncementListResponse, status_code=status.HTTP_201_CREATED)
async def create_superadmin_announcement(
    payload: AnnouncementCreate,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> AnnouncementListResponse:
    announcements = await AnnouncementService.create_platform(
        db,
        actor=current_superadmin,
        payload=payload,
    )
    return _list_response(announcements, len(announcements))


@superadmin_router.get("", response_model=AnnouncementListResponse)
async def list_superadmin_announcements(
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementListResponse:
    items, total = await AnnouncementService.list_manageable(
        db,
        actor=current_superadmin,
        status=status_filter,
        offset=skip,
        limit=limit,
    )
    return _list_response(items, total)


@superadmin_router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_superadmin_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.get_details(
        db,
        actor=current_superadmin,
        announcement_id=announcement_id,
    )
    return AnnouncementResponse.model_validate(announcement)


@superadmin_router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_superadmin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.update(
        db,
        actor=current_superadmin,
        announcement_id=announcement_id,
        payload=payload,
    )
    return AnnouncementResponse.model_validate(announcement)


@superadmin_router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_superadmin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementPublishRequest,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.publish(
        db,
        actor=current_superadmin,
        announcement_id=announcement_id,
        publish_at=payload.publish_at,
    )
    return AnnouncementResponse.model_validate(announcement)


@superadmin_router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_superadmin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementArchiveRequest,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.archive(
        db,
        actor=current_superadmin,
        announcement_id=announcement_id,
    )
    return AnnouncementResponse.model_validate(announcement)


@superadmin_router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_superadmin_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_superadmin: CurrentSuperadmin,
) -> None:
    await AnnouncementService.delete(db, actor=current_superadmin, announcement_id=announcement_id)


@tenant_admin_router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_admin_announcement(
    payload: AnnouncementCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.create(db, actor=current_admin, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_router.get("", response_model=AnnouncementListResponse)
async def list_tenant_admin_announcements(
    db: DbSession,
    current_admin: CurrentTenantAdmin,
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementListResponse:
    items, total = await AnnouncementService.list_manageable(
        db,
        actor=current_admin,
        status=status_filter,
        offset=skip,
        limit=limit,
    )
    return _list_response(items, total)


@tenant_admin_router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_tenant_admin_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.get_details(db, actor=current_admin, announcement_id=announcement_id)
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_tenant_admin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.update(db, actor=current_admin, announcement_id=announcement_id, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_tenant_admin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementPublishRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.publish(
        db,
        actor=current_admin,
        announcement_id=announcement_id,
        publish_at=payload.publish_at,
    )
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_tenant_admin_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementArchiveRequest,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.archive(db, actor=current_admin, announcement_id=announcement_id)
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_admin_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> None:
    await AnnouncementService.delete(db, actor=current_admin, announcement_id=announcement_id)


@teacher_router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_teacher_announcement(
    payload: AnnouncementCreate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.create(db, actor=current_teacher, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@teacher_router.get("", response_model=AnnouncementListResponse)
async def list_teacher_announcements(
    db: DbSession,
    current_teacher: CurrentTeacher,
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementListResponse:
    items, total = await AnnouncementService.list_manageable(
        db,
        actor=current_teacher,
        status=status_filter,
        offset=skip,
        limit=limit,
    )
    return _list_response(items, total)


@teacher_router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_teacher_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.get_details(db, actor=current_teacher, announcement_id=announcement_id)
    return AnnouncementResponse.model_validate(announcement)


@teacher_router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_teacher_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.update(db, actor=current_teacher, announcement_id=announcement_id, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@teacher_router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_teacher_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementPublishRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.publish(
        db,
        actor=current_teacher,
        announcement_id=announcement_id,
        publish_at=payload.publish_at,
    )
    return AnnouncementResponse.model_validate(announcement)


@teacher_router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_teacher_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementArchiveRequest,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> AnnouncementResponse:
    announcement = await AnnouncementService.archive(db, actor=current_teacher, announcement_id=announcement_id)
    return AnnouncementResponse.model_validate(announcement)


@teacher_router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_teacher: CurrentTeacher,
) -> None:
    await AnnouncementService.delete(db, actor=current_teacher, announcement_id=announcement_id)


@feed_router.get("/feed", response_model=AnnouncementFeedResponse)
async def get_announcement_feed(
    db: DbSession,
    current_actor: CurrentTenantMember,
    delivery_kind: str | None = Query(default=None, pattern="^(message|notice)$"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementFeedResponse:
    return await AnnouncementService.feed(
        db,
        actor=current_actor,
        delivery_kind=delivery_kind,
        offset=skip,
        limit=limit,
    )


@feed_router.post("/{announcement_id}/read", response_model=AnnouncementReadResponse)
async def mark_announcement_read(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_actor: CurrentTenantMember,
) -> AnnouncementReadResponse:
    read = await AnnouncementService.mark_read(
        db,
        actor=current_actor,
        announcement_id=announcement_id,
        status=AnnouncementReadStatus.READ,
    )
    return AnnouncementReadResponse.model_validate(read)


@feed_router.post("/{announcement_id}/acknowledge", response_model=AnnouncementReadResponse)
async def acknowledge_announcement(
    announcement_id: uuid.UUID,
    db: DbSession,
    current_actor: CurrentTenantMember,
) -> AnnouncementReadResponse:
    read = await AnnouncementService.mark_read(
        db,
        actor=current_actor,
        announcement_id=announcement_id,
        status=AnnouncementReadStatus.ACKNOWLEDGED,
    )
    return AnnouncementReadResponse.model_validate(read)
