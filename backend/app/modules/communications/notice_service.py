"""Notice authoring, publication, and recipient delivery."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.communications.enums import (
    CommunicationActorType,
    NoticeStatus,
    NotificationSourceType,
    NotificationStatus,
)
from app.modules.communications.models import Notice, NoticeAudience, NotificationDelivery
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import (
    RecipientResolver,
    actor_tenant_id,
    actor_type_for,
)
from app.modules.communications.repository import CommunicationRepository
from app.modules.communications.schemas import NoticeAudienceCreate
from app.modules.realtime.publisher import RealtimePublisher
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin

_NOTICE_PATHS = {
    CommunicationActorType.TENANT_ADMIN: "/admin/notices",
    CommunicationActorType.TEACHER: "/teacher/notices",
    CommunicationActorType.STUDENT: "/student/notices",
    CommunicationActorType.PARENT: "/parent/notices",
}


def _notice_action_path(actor_type: CommunicationActorType, notice_id: uuid.UUID) -> str | None:
    base = _NOTICE_PATHS.get(actor_type)
    return f"{base}?notice={notice_id}" if base else None


def _normalize_audiences(items) -> list[NoticeAudienceCreate]:
    normalized: list[NoticeAudienceCreate] = []
    for item in items:
        if isinstance(item, NoticeAudienceCreate):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(NoticeAudienceCreate.model_validate(item))
        else:
            normalized.append(
                NoticeAudienceCreate(
                    audience_type=item.audience_type,
                    tenant_target_id=item.tenant_target_id,
                    actor_id=item.actor_id,
                    class_id=item.class_id,
                )
            )
    return normalized


class NoticeService:
    @staticmethod
    def _ensure_creator(actor) -> None:
        if not isinstance(actor, (SuperAdmin, TenantAdmin, Teacher)):
            raise ForbiddenException("This actor cannot create notices")

    @staticmethod
    async def _resolve(db: AsyncSession, *, actor, audiences):
        return await RecipientResolver.resolve_notice_audience(
            db,
            sender=actor,
            audiences=_normalize_audiences(audiences),
        )

    @staticmethod
    async def create(db: AsyncSession, *, actor, payload) -> Notice:
        NoticeService._ensure_creator(actor)
        await NoticeService._resolve(db, actor=actor, audiences=payload.audiences)
        notice = Notice(
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
            status=NoticeStatus.SCHEDULED if payload.publish_at else NoticeStatus.DRAFT,
        )
        db.add(notice)
        await db.flush()
        for audience in payload.audiences:
            db.add(
                NoticeAudience(
                    notice_id=notice.id,
                    tenant_id=actor_tenant_id(actor),
                    audience_type=audience.audience_type,
                    tenant_target_id=audience.tenant_target_id,
                    actor_id=audience.actor_id,
                    class_id=audience.class_id,
                )
            )
        await db.flush()
        result = await CommunicationRepository.get_notice(db, notice.id)
        if result is None:
            raise NotFoundException("Notice not found after creation")
        return result

    @staticmethod
    async def list_manageable(
        db: AsyncSession,
        *,
        actor,
        status: NoticeStatus | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Notice], int]:
        NoticeService._ensure_creator(actor)
        stmt = (
            select(Notice)
            .options(selectinload(Notice.audiences))
            .where(
                Notice.created_by_actor_type == actor_type_for(actor),
                Notice.created_by_actor_id == actor.id,
            )
        )
        tenant_id = actor_tenant_id(actor)
        if tenant_id is not None:
            stmt = stmt.where(Notice.tenant_id == tenant_id)
        if status is not None:
            stmt = stmt.where(Notice.status == status)
        total = int(
            (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        )
        rows = (
            (
                await db.execute(
                    stmt.order_by(Notice.updated_at.desc()).offset(offset).limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        return list(rows), total

    @staticmethod
    async def get_manageable(db: AsyncSession, *, actor, notice_id: uuid.UUID) -> Notice:
        notice = await CommunicationRepository.get_notice(db, notice_id)
        if notice is None:
            raise NotFoundException("Notice not found")
        if notice.created_by_actor_type != actor_type_for(actor) or notice.created_by_actor_id != actor.id:
            raise NotFoundException("Notice not found")
        tenant_id = actor_tenant_id(actor)
        if tenant_id is not None and notice.tenant_id != tenant_id:
            raise NotFoundException("Notice not found")
        return notice

    @staticmethod
    async def update(db: AsyncSession, *, actor, notice_id: uuid.UUID, payload) -> Notice:
        notice = await NoticeService.get_manageable(db, actor=actor, notice_id=notice_id)
        if notice.status == NoticeStatus.PUBLISHED:
            raise BadRequestException("Published notices are immutable")
        if notice.status in {NoticeStatus.ARCHIVED, NoticeStatus.CANCELLED}:
            raise BadRequestException("This notice can no longer be edited")
        if payload.audiences is not None:
            await NoticeService._resolve(db, actor=actor, audiences=payload.audiences)

        data = payload.model_dump(exclude_unset=True)
        audiences = data.pop("audiences", None)
        for key, value in data.items():
            setattr(notice, key, value)
        if audiences is not None:
            notice.audiences.clear()
            await db.flush()
            for audience in audiences:
                db.add(
                    NoticeAudience(
                        notice_id=notice.id,
                        tenant_id=actor_tenant_id(actor),
                        audience_type=audience["audience_type"],
                        tenant_target_id=audience.get("tenant_target_id"),
                        actor_id=audience.get("actor_id"),
                        class_id=audience.get("class_id"),
                    )
                )
        await db.flush()
        result = await CommunicationRepository.get_notice(db, notice.id)
        if result is None:
            raise NotFoundException("Notice not found")
        return result

    @staticmethod
    async def preview(db: AsyncSession, *, actor, audiences):
        recipients, excluded = await NoticeService._resolve(
            db, actor=actor, audiences=audiences
        )
        label = recipients[0].group_label or "Audience"
        return label, recipients, excluded

    @staticmethod
    async def publish(
        db: AsyncSession,
        *,
        actor,
        notice_id: uuid.UUID,
        publish_at: datetime | None = None,
    ) -> Notice:
        notice = await NoticeService.get_manageable(db, actor=actor, notice_id=notice_id)
        if notice.status not in {NoticeStatus.DRAFT, NoticeStatus.SCHEDULED}:
            raise BadRequestException("Only draft or scheduled notices can be published")
        if publish_at is not None and publish_at > datetime.now(timezone.utc):
            notice.publish_at = publish_at
            notice.status = NoticeStatus.SCHEDULED
            await db.flush()
            return notice
        return await NoticeService._publish_now(db, actor=actor, notice=notice)

    @staticmethod
    async def _publish_now(db: AsyncSession, *, actor, notice: Notice) -> Notice:
        recipients, _ = await NoticeService._resolve(
            db,
            actor=actor,
            audiences=notice.audiences,
        )
        notice.status = NoticeStatus.PUBLISHED
        notice.publish_at = datetime.now(timezone.utc)
        await db.flush()
        for recipient in recipients:
            await NotificationService.deliver(
                db,
                recipients=[recipient],
                source_type=NotificationSourceType.NOTICE,
                source_id=notice.id,
                title=notice.title,
                preview=notice.body,
                action_path=_notice_action_path(recipient.actor_type, notice.id),
                tenant_id=notice.tenant_id,
            )
            RealtimePublisher.defer_to_actor(
                db,
                event_type="notice.published",
                actor_type=recipient.actor_type.value,
                actor_id=recipient.actor_id,
                tenant_id=recipient.tenant_id,
                data={"notice_id": str(notice.id)},
            )
        await db.flush()
        result = await CommunicationRepository.get_notice(db, notice.id)
        if result is None:
            raise NotFoundException("Notice not found")
        return result

    @staticmethod
    async def archive(db: AsyncSession, *, actor, notice_id: uuid.UUID) -> Notice:
        notice = await NoticeService.get_manageable(db, actor=actor, notice_id=notice_id)
        if notice.status != NoticeStatus.PUBLISHED:
            raise BadRequestException("Only published notices can be archived")
        notice.status = NoticeStatus.ARCHIVED
        notice.archived_at = datetime.now(timezone.utc)
        return await CommunicationRepository.save(db, notice)

    @staticmethod
    async def cancel(db: AsyncSession, *, actor, notice_id: uuid.UUID) -> Notice:
        notice = await NoticeService.get_manageable(db, actor=actor, notice_id=notice_id)
        if notice.status not in {NoticeStatus.DRAFT, NoticeStatus.SCHEDULED}:
            raise BadRequestException("Only draft or scheduled notices can be cancelled")
        notice.status = NoticeStatus.CANCELLED
        return await CommunicationRepository.save(db, notice)

    @staticmethod
    async def list_received(
        db: AsyncSession,
        *,
        actor,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Notice, NotificationDelivery]], int, int]:
        actor_type = actor_type_for(actor)
        filters = [
            NotificationDelivery.recipient_actor_type == actor_type,
            NotificationDelivery.recipient_actor_id == actor.id,
            NotificationDelivery.source_type == NotificationSourceType.NOTICE,
            NotificationDelivery.status != NotificationStatus.DISMISSED,
            Notice.id == NotificationDelivery.source_id,
            Notice.status.in_([NoticeStatus.PUBLISHED, NoticeStatus.ARCHIVED]),
        ]
        tenant_id = actor_tenant_id(actor)
        if tenant_id is not None:
            filters.append(
                (NotificationDelivery.tenant_id == tenant_id)
                | (NotificationDelivery.tenant_id.is_(None))
            )
        stmt = select(Notice, NotificationDelivery).where(*filters)
        total = int(
            (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        )
        unread = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(NotificationDelivery)
                    .where(
                        NotificationDelivery.recipient_actor_type == actor_type,
                        NotificationDelivery.recipient_actor_id == actor.id,
                        NotificationDelivery.source_type == NotificationSourceType.NOTICE,
                        NotificationDelivery.status == NotificationStatus.UNREAD,
                    )
                )
            ).scalar_one()
        )
        rows = (
            await db.execute(
                stmt.order_by(NotificationDelivery.delivered_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [(row[0], row[1]) for row in rows], total, unread

    @staticmethod
    async def mark_received_read(
        db: AsyncSession,
        *,
        actor,
        notice_id: uuid.UUID,
    ) -> NotificationDelivery:
        delivery = (
            await db.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.recipient_actor_type == actor_type_for(actor),
                    NotificationDelivery.recipient_actor_id == actor.id,
                    NotificationDelivery.source_type == NotificationSourceType.NOTICE,
                    NotificationDelivery.source_id == notice_id,
                )
            )
        ).scalar_one_or_none()
        if delivery is None:
            raise NotFoundException("Notice not found")
        return await NotificationService.update_status(
            db,
            actor=actor,
            notification_id=delivery.id,
            status=NotificationStatus.READ,
        )
