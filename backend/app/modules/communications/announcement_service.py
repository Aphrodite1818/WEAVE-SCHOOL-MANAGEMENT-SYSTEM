"""Announcement management service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.communications.enums import (
    AnnouncementStatus,
    CommunicationActorType,
    NotificationSourceType,
)
from app.modules.communications.models import Announcement, AnnouncementAudience
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import (
    RecipientResolver,
    actor_tenant_id,
    actor_type_for,
)
from app.modules.communications.repository import CommunicationRepository
from app.modules.communications.schemas import AnnouncementAudienceCreate
from app.modules.superadmin.models import SuperAdmin
from app.modules.tenant_admins.models import TenantAdmin

_ANNOUNCEMENT_INBOX_PATHS = {
    CommunicationActorType.TENANT_ADMIN: "/admin/inbox",
    CommunicationActorType.TEACHER: "/teacher/inbox",
    CommunicationActorType.STUDENT: "/student/inbox",
    CommunicationActorType.PARENT: "/parent/inbox",
}


def _announcement_action_path(
    actor_type: CommunicationActorType, announcement_id: uuid.UUID
) -> str:
    return f"{_ANNOUNCEMENT_INBOX_PATHS[actor_type]}?announcement={announcement_id}"


class AnnouncementService:
    @staticmethod
    def _ensure_creator(actor) -> None:
        if not isinstance(actor, (SuperAdmin, TenantAdmin)):
            raise ForbiddenException("Teachers, parents, and students cannot create announcements")

    @staticmethod
    async def _resolve_audience_or_raise(db: AsyncSession, *, actor, audiences):
        normalized_audiences = [
            (
                AnnouncementAudienceCreate.model_validate(audience)
                if isinstance(audience, dict)
                else audience
            )
            for audience in audiences
        ]
        return await RecipientResolver.resolve_announcement_audience(
            db, sender=actor, audiences=normalized_audiences
        )

    @staticmethod
    async def create(db: AsyncSession, *, actor, payload) -> Announcement:
        AnnouncementService._ensure_creator(actor)
        await AnnouncementService._resolve_audience_or_raise(
            db, actor=actor, audiences=payload.audiences
        )
        status = AnnouncementStatus.SCHEDULED if payload.publish_at else AnnouncementStatus.DRAFT
        announcement = Announcement(
            tenant_id=actor_tenant_id(actor),
            created_by_actor_type=actor_type_for(actor),
            created_by_actor_id=actor.id,
            title=payload.title,
            body=payload.body,
            category=payload.category,
            priority=payload.priority,
            publish_at=payload.publish_at,
            expires_at=payload.expires_at,
            is_pinned=payload.is_pinned,
            status=status,
        )
        db.add(announcement)
        await db.flush()
        for audience in payload.audiences:
            db.add(
                AnnouncementAudience(
                    announcement_id=announcement.id,
                    tenant_id=actor_tenant_id(actor),
                    audience_type=audience.audience_type,
                    tenant_target_id=audience.tenant_target_id,
                    actor_id=audience.actor_id,
                    class_id=audience.class_id,
                )
            )
        await db.flush()
        return await CommunicationRepository.get_announcement(db, announcement.id)

    @staticmethod
    async def list_manageable(
        db: AsyncSession,
        *,
        actor,
        status: AnnouncementStatus | None,
        offset: int,
        limit: int,
    ):
        AnnouncementService._ensure_creator(actor)
        stmt = (
            select(Announcement)
            .options(selectinload(Announcement.audiences))
            .where(
                Announcement.created_by_actor_type == actor_type_for(actor),
                Announcement.created_by_actor_id == actor.id,
            )
        )
        if actor_tenant_id(actor) is not None:
            stmt = stmt.where(Announcement.tenant_id == actor_tenant_id(actor))
        if status is not None:
            stmt = stmt.where(Announcement.status == status)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            (
                await db.execute(
                    stmt.order_by(Announcement.updated_at.desc()).offset(offset).limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def get_manageable(
        db: AsyncSession, *, actor, announcement_id: uuid.UUID
    ) -> Announcement:
        announcement = await CommunicationRepository.get_announcement(db, announcement_id)
        if announcement is None:
            raise NotFoundException("Announcement not found")
        if (
            announcement.created_by_actor_type != actor_type_for(actor)
            or announcement.created_by_actor_id != actor.id
        ):
            raise NotFoundException("Announcement not found")
        if actor_tenant_id(actor) is not None and announcement.tenant_id != actor_tenant_id(actor):
            raise NotFoundException("Announcement not found")
        return announcement

    @staticmethod
    async def update(
        db: AsyncSession, *, actor, announcement_id: uuid.UUID, payload
    ) -> Announcement:
        announcement = await AnnouncementService.get_manageable(
            db, actor=actor, announcement_id=announcement_id
        )
        if announcement.status == AnnouncementStatus.PUBLISHED:
            raise BadRequestException("Published announcements cannot be edited")
        if announcement.status in {
            AnnouncementStatus.ARCHIVED,
            AnnouncementStatus.CANCELLED,
        }:
            raise BadRequestException("This announcement can no longer be edited")
        if payload.audiences is not None:
            await AnnouncementService._resolve_audience_or_raise(
                db, actor=actor, audiences=payload.audiences
            )
        data = payload.model_dump(exclude_unset=True)
        audiences = data.pop("audiences", None)
        for key, value in data.items():
            setattr(announcement, key, value)
        if audiences is not None:
            announcement.audiences.clear()
            await db.flush()
            for audience in audiences:
                db.add(
                    AnnouncementAudience(
                        announcement_id=announcement.id,
                        tenant_id=actor_tenant_id(actor),
                        audience_type=audience["audience_type"],
                        tenant_target_id=audience.get("tenant_target_id"),
                        actor_id=audience.get("actor_id"),
                        class_id=audience.get("class_id"),
                    )
                )
        await db.flush()
        return await CommunicationRepository.get_announcement(db, announcement.id)

    @staticmethod
    async def preview(db: AsyncSession, *, actor, audiences):
        recipients, excluded = await AnnouncementService._resolve_audience_or_raise(
            db, actor=actor, audiences=audiences
        )
        label = recipients[0].group_label or "Audience" if recipients else "Audience"
        return label, recipients, excluded

    @staticmethod
    async def publish(
        db: AsyncSession, *, actor, announcement_id: uuid.UUID, publish_at=None
    ) -> Announcement:
        announcement = await AnnouncementService.get_manageable(
            db, actor=actor, announcement_id=announcement_id
        )
        if announcement.status not in {
            AnnouncementStatus.DRAFT,
            AnnouncementStatus.SCHEDULED,
        }:
            raise BadRequestException("Only draft or scheduled announcements can be published")
        recipients, _ = await AnnouncementService._resolve_audience_or_raise(
            db, actor=actor, audiences=announcement.audiences
        )
        if publish_at is not None:
            announcement.publish_at = publish_at
            announcement.status = AnnouncementStatus.SCHEDULED
            await db.flush()
            return announcement
        announcement.status = AnnouncementStatus.PUBLISHED
        announcement.publish_at = datetime.now(timezone.utc)
        for recipient in recipients:
            await NotificationService.deliver(
                db,
                recipients=[recipient],
                source_type=NotificationSourceType.ANNOUNCEMENT,
                source_id=announcement.id,
                title=announcement.title,
                preview=announcement.body,
                action_path=_announcement_action_path(recipient.actor_type, announcement.id),
                tenant_id=announcement.tenant_id,
            )
        await db.flush()
        return await CommunicationRepository.get_announcement(db, announcement.id)

    @staticmethod
    async def archive(db: AsyncSession, *, actor, announcement_id: uuid.UUID) -> Announcement:
        announcement = await AnnouncementService.get_manageable(
            db, actor=actor, announcement_id=announcement_id
        )
        if announcement.status != AnnouncementStatus.PUBLISHED:
            raise BadRequestException("Only published announcements can be archived")
        announcement.status = AnnouncementStatus.ARCHIVED
        announcement.archived_at = datetime.now(timezone.utc)
        return await CommunicationRepository.save(db, announcement)

    @staticmethod
    async def cancel(db: AsyncSession, *, actor, announcement_id: uuid.UUID) -> Announcement:
        announcement = await AnnouncementService.get_manageable(
            db, actor=actor, announcement_id=announcement_id
        )
        if announcement.status not in {
            AnnouncementStatus.DRAFT,
            AnnouncementStatus.SCHEDULED,
        }:
            raise BadRequestException("Only draft or scheduled announcements can be cancelled")
        announcement.status = AnnouncementStatus.CANCELLED
        return await CommunicationRepository.save(db, announcement)
