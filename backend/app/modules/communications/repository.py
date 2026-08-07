"""Low-level communication queries."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.communications.enums import CommunicationActorType, NotificationStatus
from app.modules.communications.models import (
    Announcement,
    Conversation,
    ConversationParticipant,
    Message,
    NotificationDelivery,
)


class CommunicationRepository:
    @staticmethod
    async def save(db: AsyncSession, row):
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row

    @staticmethod
    async def get_conversation_for_actor(
        db: AsyncSession,
        *,
        conversation_id: uuid.UUID,
        actor_type: CommunicationActorType,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
    ) -> Conversation | None:
        stmt = (
            select(Conversation)
            .join(ConversationParticipant)
            .options(
                selectinload(Conversation.participants),
                selectinload(Conversation.messages),
            )
            .where(
                Conversation.id == conversation_id,
                ConversationParticipant.actor_type == actor_type,
                ConversationParticipant.actor_id == actor_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if tenant_id is not None:
            stmt = stmt.where(
                or_(
                    Conversation.tenant_id == tenant_id,
                    ConversationParticipant.tenant_id == tenant_id,
                )
            )
        return (await db.execute(stmt)).unique().scalar_one_or_none()

    @staticmethod
    async def list_conversations_for_actor(
        db: AsyncSession,
        *,
        actor_type: CommunicationActorType,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Conversation], int]:
        base = (
            select(Conversation)
            .join(ConversationParticipant)
            .where(
                ConversationParticipant.actor_type == actor_type,
                ConversationParticipant.actor_id == actor_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        if tenant_id is not None:
            base = base.where(
                or_(
                    Conversation.tenant_id == tenant_id,
                    ConversationParticipant.tenant_id == tenant_id,
                )
            )
        total = (
            await db.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    base.options(
                        selectinload(Conversation.participants),
                        selectinload(Conversation.messages),
                    )
                    .order_by(Conversation.updated_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            .unique()
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def find_direct_conversation(
        db: AsyncSession,
        *,
        sender_type: CommunicationActorType,
        sender_id: uuid.UUID,
        recipient_type: CommunicationActorType,
        recipient_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
    ) -> Conversation | None:
        left = ConversationParticipant
        subquery = (
            select(left.conversation_id)
            .where(
                left.actor_type.in_([sender_type, recipient_type]),
                left.actor_id.in_([sender_id, recipient_id]),
                left.left_at.is_(None),
            )
            .group_by(left.conversation_id)
            .having(func.count(func.distinct(left.id)) == 2)
        )
        stmt = select(Conversation).where(
            Conversation.id.in_(subquery), Conversation.closed_at.is_(None)
        )
        if tenant_id is not None:
            stmt = stmt.where(Conversation.tenant_id == tenant_id)
        return (
            (
                await db.execute(
                    stmt.options(
                        selectinload(Conversation.participants),
                        selectinload(Conversation.messages),
                    )
                )
            )
            .unique()
            .scalar_one_or_none()
        )

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        *,
        actor_type: CommunicationActorType,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        status: NotificationStatus | None,
        source_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[NotificationDelivery], int, int]:
        filters = [
            NotificationDelivery.recipient_actor_type == actor_type,
            NotificationDelivery.recipient_actor_id == actor_id,
            NotificationDelivery.status != NotificationStatus.DISMISSED,
        ]
        if tenant_id is not None:
            filters.append(
                or_(
                    NotificationDelivery.tenant_id == tenant_id,
                    NotificationDelivery.tenant_id.is_(None),
                )
            )
        if status is not None:
            filters.append(NotificationDelivery.status == status)
        if source_type:
            filters.append(NotificationDelivery.source_type == source_type)
        stmt = select(NotificationDelivery).where(and_(*filters))
        total = (
            await db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        unread = (
            await db.execute(
                select(func.count())
                .select_from(NotificationDelivery)
                .where(
                    NotificationDelivery.recipient_actor_type == actor_type,
                    NotificationDelivery.recipient_actor_id == actor_id,
                    NotificationDelivery.status == NotificationStatus.UNREAD,
                )
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    stmt.order_by(NotificationDelivery.delivered_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total), int(unread)

    @staticmethod
    async def get_notification_for_actor(
        db: AsyncSession,
        *,
        notification_id: uuid.UUID,
        actor_type: CommunicationActorType,
        actor_id: uuid.UUID,
    ) -> NotificationDelivery | None:
        return (
            await db.execute(
                select(NotificationDelivery).where(
                    NotificationDelivery.id == notification_id,
                    NotificationDelivery.recipient_actor_type == actor_type,
                    NotificationDelivery.recipient_actor_id == actor_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_announcement(
        db: AsyncSession, announcement_id: uuid.UUID
    ) -> Announcement | None:
        return (
            (
                await db.execute(
                    select(Announcement)
                    .options(selectinload(Announcement.audiences))
                    .where(Announcement.id == announcement_id)
                )
            )
            .unique()
            .scalar_one_or_none()
        )
