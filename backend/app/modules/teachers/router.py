from datetime import datetime, timezone
from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_teacher, get_current_teacher_account
from app.core.exceptions import NotFoundException
from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementRead,
    AnnouncementReadStatus,
    AnnouncementRecipientRole,
    AnnouncementStatus,
    AnnouncementTarget,
    AnnouncementTargetType,
)
from app.modules.announcements.repository import AnnouncementReadRepository
from app.modules.announcements.schemas import (
    AnnouncementFeedItemResponse,
    AnnouncementFeedResponse,
    AnnouncementReadResponse,
)
from app.modules.subjects.schemas import SubjectListResponse, SubjectResponse
from app.modules.teachers.models import Teacher, TeacherAccount
from app.modules.teachers.schemas import (
    TeacherAccountOnboardingRequest,
    TeacherAccountProfileUpdateRequest,
    TeacherAccountRegisterRequest,
    TeacherAccountResponse,
    TeacherOnboardingStatusResponse,
    TeacherOnboardingUpdate,
    TeacherResponse,
)
from app.modules.teachers.service import TeacherAccountService
from app.modules.teachers.tenant_service import TeacherService


router = APIRouter(tags=["Teachers"])

CurrentTeacher: TypeAlias = Annotated[Teacher, Depends(get_current_teacher)]
CurrentTeacherAccount: TypeAlias = Annotated[
    TeacherAccount,
    Depends(get_current_teacher_account),
]


@router.post(
    "/accounts/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a global teacher account",
)
async def register_teacher_account(
    payload: TeacherAccountRegisterRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> dict:
    """Register a global teacher login account."""

    return await TeacherAccountService.register_account(
        db=db,
        payload=payload,
        background_tasks=background_tasks,
    )


@router.get(
    "/accounts/me/onboarding-status",
    summary="Get my global teacher account onboarding status",
)
async def get_my_teacher_account_onboarding_status(
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> dict:
    """Return onboarding state for the logged-in global teacher account."""

    return await TeacherAccountService.get_onboarding_status(
        db=db,
        account_id=current_account.id,
    )


@router.post(
    "/accounts/me/onboarding",
    response_model=TeacherAccountResponse,
    summary="Complete my global teacher account onboarding",
)
async def complete_my_teacher_account_onboarding(
    payload: TeacherAccountOnboardingRequest,
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> TeacherAccountResponse:
    """Complete required global teacher account profile fields."""

    return await TeacherAccountService.complete_onboarding(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


@router.patch(
    "/accounts/me/profile",
    response_model=TeacherAccountResponse,
    summary="Update my global teacher account profile",
)
async def update_my_teacher_account_profile(
    payload: TeacherAccountProfileUpdateRequest,
    db: DbSession,
    current_account: CurrentTeacherAccount,
) -> TeacherAccountResponse:
    """Update teacher-controlled global account profile fields."""

    return await TeacherAccountService.update_profile(
        db=db,
        account_id=current_account.id,
        payload=payload,
    )


def _teacher_direct_message_query(current_user: Teacher):
    now = datetime.now(timezone.utc)
    return (
        select(Announcement)
        .join(AnnouncementTarget, AnnouncementTarget.announcement_id == Announcement.id)
        .options(selectinload(Announcement.targets), selectinload(Announcement.reads))
        .where(
            Announcement.tenant_id == current_user.tenant_id,
            Announcement.status == AnnouncementStatus.PUBLISHED,
            Announcement.created_by_actor_type != AnnouncementActorType.SUPERADMIN,
            or_(Announcement.publish_at.is_(None), Announcement.publish_at <= now),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
            AnnouncementTarget.target_type == AnnouncementTargetType.SPECIFIC_TEACHER,
            AnnouncementTarget.teacher_id == current_user.id,
        )
        .distinct()
    )


async def _ensure_teacher_direct_message(
    db: DbSession,
    current_user: Teacher,
    announcement_id: UUID,
) -> None:
    exists = (
        await db.execute(
            _teacher_direct_message_query(current_user).where(Announcement.id == announcement_id)
        )
    ).scalar_one_or_none()

    if exists is None:
        raise NotFoundException(detail="Message not found")


@router.get(
    "/me",
    response_model=TeacherResponse,
    summary="Get my teacher profile",
)
async def get_my_teacher_profile(
    db: DbSession,
    current_user: CurrentTeacher,
) -> Teacher:
    """Return the current teacher profile."""

    return await TeacherService.get_my_teacher_profile(
        db=db,
        actor=current_user,
    )


@router.patch(
    "/me/profile",
    response_model=TeacherResponse,
    summary="Update my teacher profile",
)
async def update_my_teacher_profile(
    payload: TeacherOnboardingUpdate,
    db: DbSession,
    current_user: CurrentTeacher,
) -> Teacher:
    """Allow a teacher to update their own profile."""

    return await TeacherService.update_my_teacher_profile(
        db=db,
        actor=current_user,
        teacher_data=payload,
    )


@router.get(
    "/me/onboarding-status",
    response_model=TeacherOnboardingStatusResponse,
    summary="Get my teacher onboarding status",
)
async def get_my_teacher_onboarding_status(
    db: DbSession,
    current_user: CurrentTeacher,
) -> TeacherOnboardingStatusResponse:
    """Return the current teacher onboarding status."""

    return await TeacherService.get_my_onboarding_status(
        db=db,
        actor=current_user,
    )


@router.get(
    "/me/messages",
    response_model=AnnouncementFeedResponse,
    summary="List my direct admin messages",
)
async def get_my_teacher_messages(
    db: DbSession,
    current_user: CurrentTeacher,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementFeedResponse:
    """Return published direct messages targeted to the current teacher."""

    base_query = _teacher_direct_message_query(current_user)

    total = (
        await db.execute(select(func.count()).select_from(base_query.subquery()))
    ).scalar_one()

    announcements = (
        await db.execute(
            base_query
            .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).scalars().unique().all()

    read_by_id = {}
    if announcements:
        reads = (
            await db.execute(
                select(AnnouncementRead).where(
                    AnnouncementRead.tenant_id == current_user.tenant_id,
                    AnnouncementRead.actor_type == AnnouncementRecipientRole.TEACHER,
                    AnnouncementRead.actor_id == current_user.id,
                    AnnouncementRead.announcement_id.in_([item.id for item in announcements]),
                )
            )
        ).scalars().all()
        read_by_id = {read.announcement_id: read for read in reads}

    items = []
    unread_count = 0
    for announcement in announcements:
        read = read_by_id.get(announcement.id)
        is_read = read is not None and read.status in {
            AnnouncementReadStatus.READ,
            AnnouncementReadStatus.ACKNOWLEDGED,
        }
        is_acknowledged = read is not None and read.status == AnnouncementReadStatus.ACKNOWLEDGED
        if not is_read:
            unread_count += 1

        items.append(
            AnnouncementFeedItemResponse(
                id=announcement.id,
                title=announcement.title,
                body=announcement.body,
                category=announcement.category,
                priority=announcement.priority,
                status=announcement.status,
                publish_at=announcement.publish_at,
                expires_at=announcement.expires_at,
                is_pinned=announcement.is_pinned,
                is_read=is_read,
                is_acknowledged=is_acknowledged,
                read_at=read.read_at if read else None,
                acknowledged_at=read.acknowledged_at if read else None,
                created_at=announcement.created_at,
                updated_at=announcement.updated_at,
            )
        )

    return AnnouncementFeedResponse(items=items, total=int(total), unread_count=unread_count)


@router.post(
    "/me/messages/{announcement_id}/read",
    response_model=AnnouncementReadResponse,
    summary="Mark my direct message as read",
)
async def mark_my_teacher_message_read(
    announcement_id: UUID,
    db: DbSession,
    current_user: CurrentTeacher,
) -> AnnouncementReadResponse:
    await _ensure_teacher_direct_message(db, current_user, announcement_id)
    read = await AnnouncementReadRepository.upsert_read_state(
        db,
        tenant_id=current_user.tenant_id,
        announcement_id=announcement_id,
        actor_type=AnnouncementRecipientRole.TEACHER,
        actor_id=current_user.id,
        status=AnnouncementReadStatus.READ,
    )
    await db.commit()
    return AnnouncementReadResponse.model_validate(read)


@router.post(
    "/me/messages/{announcement_id}/acknowledge",
    response_model=AnnouncementReadResponse,
    summary="Acknowledge my direct message",
)
async def acknowledge_my_teacher_message(
    announcement_id: UUID,
    db: DbSession,
    current_user: CurrentTeacher,
) -> AnnouncementReadResponse:
    await _ensure_teacher_direct_message(db, current_user, announcement_id)
    read = await AnnouncementReadRepository.upsert_read_state(
        db,
        tenant_id=current_user.tenant_id,
        announcement_id=announcement_id,
        actor_type=AnnouncementRecipientRole.TEACHER,
        actor_id=current_user.id,
        status=AnnouncementReadStatus.ACKNOWLEDGED,
    )
    await db.commit()
    return AnnouncementReadResponse.model_validate(read)


@router.get(
    "/me/subjects",
    response_model=SubjectListResponse,
    summary="List my assigned subjects",
)
async def get_my_subjects(
    db: DbSession,
    current_user: CurrentTeacher,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
) -> SubjectListResponse:
    """Return subjects assigned to the current teacher."""

    subjects, total = await TeacherService.get_my_subjects(
        db=db,
        actor=current_user,
        skip=skip,
        limit=limit,
        is_active=is_active,
        search=search,
    )
    return SubjectListResponse(
        items=[SubjectResponse.model_validate(subject) for subject in subjects],
        total=total,
    )
