"""Notification delivery service."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.communications.enums import (
    NotificationSourceType,
    NotificationStatus,
)
from app.modules.communications.models import NotificationDelivery
from app.modules.communications.recipient_resolver import (
    ResolvedRecipient,
    actor_tenant_id,
    actor_type_for,
)
from app.modules.communications.repository import CommunicationRepository


logger = logging.getLogger(__name__)


class NotificationService:
    @staticmethod
    async def deliver(
        db: AsyncSession,
        *,
        recipients: list[ResolvedRecipient],
        source_type: NotificationSourceType,
        source_id: uuid.UUID,
        title: str,
        preview: str,
        action_path: str | None,
        tenant_id: uuid.UUID | None,
    ) -> list[NotificationDelivery]:
        deliveries: list[NotificationDelivery] = []
        for recipient in recipients:
            existing = (
                await db.execute(
                    select(NotificationDelivery).where(
                        NotificationDelivery.recipient_actor_type
                        == recipient.actor_type,
                        NotificationDelivery.recipient_actor_id == recipient.actor_id,
                        NotificationDelivery.source_type == source_type,
                        NotificationDelivery.source_id == source_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                deliveries.append(existing)
                continue
            delivery = NotificationDelivery(
                tenant_id=(
                    recipient.tenant_id
                    if recipient.tenant_id is not None
                    else tenant_id
                ),
                recipient_actor_type=recipient.actor_type,
                recipient_actor_id=recipient.actor_id,
                source_type=source_type,
                source_id=source_id,
                title=title[:200],
                preview=preview[:500],
                action_path=action_path,
            )
            db.add(delivery)
            deliveries.append(delivery)
        await db.flush()
        return deliveries

    @staticmethod
    async def deliver_system_event(
        db: AsyncSession,
        *,
        recipients: list[ResolvedRecipient],
        source_type: NotificationSourceType,
        source_id: uuid.UUID,
        title: str,
        preview: str,
        action_path: str | None = None,
        tenant_id: uuid.UUID | None = None,
    ) -> list[NotificationDelivery]:
        """Deliver a non-critical system event without risking its source transaction.

        Worker jobs and lifecycle operations must remain durable even when the
        notification schema, recipient query, or delivery insert fails. A nested
        transaction confines any delivery failure to its savepoint while the
        caller retains control of the surrounding business transaction.
        """

        try:
            async with db.begin_nested():
                return await NotificationService.deliver(
                    db,
                    recipients=recipients,
                    source_type=source_type,
                    source_id=source_id,
                    title=title,
                    preview=preview,
                    action_path=action_path,
                    tenant_id=tenant_id,
                )
        except Exception:
            logger.exception(
                "System notification delivery failed",
                extra={
                    "notification_source_type": source_type.value,
                    "notification_source_id": str(source_id),
                    "notification_recipient_count": len(recipients),
                },
            )
            return []

    @staticmethod
    async def list_for_actor(
        db: AsyncSession,
        *,
        actor,
        status: NotificationStatus | None,
        source_type: str | None,
        offset: int,
        limit: int,
    ):
        return await CommunicationRepository.list_notifications(
            db,
            actor_type=actor_type_for(actor),
            actor_id=actor.id,
            tenant_id=actor_tenant_id(actor),
            status=status,
            source_type=source_type,
            offset=offset,
            limit=limit,
        )

    @staticmethod
    async def update_status(
        db: AsyncSession,
        *,
        actor,
        notification_id: uuid.UUID,
        status: NotificationStatus,
    ) -> NotificationDelivery:
        delivery = await CommunicationRepository.get_notification_for_actor(
            db,
            notification_id=notification_id,
            actor_type=actor_type_for(actor),
            actor_id=actor.id,
        )
        if delivery is None:
            raise NotFoundException("Notification not found")
        now = datetime.now(timezone.utc)
        delivery.status = status
        if status == NotificationStatus.READ:
            delivery.read_at = delivery.read_at or now
        elif status == NotificationStatus.ACKNOWLEDGED:
            delivery.read_at = delivery.read_at or now
            delivery.acknowledged_at = delivery.acknowledged_at or now
        elif status == NotificationStatus.DISMISSED:
            delivery.dismissed_at = delivery.dismissed_at or now
        return await CommunicationRepository.save(db, delivery)
