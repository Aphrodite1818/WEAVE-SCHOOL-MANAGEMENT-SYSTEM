# ====================================== #
#      modules/realtime/publisher.py     #
# ====================================== #

"""Domain-facing API for publishing realtime events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.realtime.broker import realtime_broker
from app.modules.realtime.schemas import (
    RealtimeAudience,
    RealtimeBrokerMessage,
    RealtimeEvent,
)


class RealtimePublisher:
    """
    High-level interface used by Weave domains to publish
    realtime events.

    Domains should not interact with Redis or WebSocket
    infrastructure directly.
    """

    _PENDING_SESSION_KEY = "weave_pending_realtime_messages"

    @staticmethod
    def _actor_message(
        *,
        event_type: str,
        actor_type: str,
        actor_id: UUID,
        data: dict[str, Any],
        tenant_id: UUID | None = None,
    ) -> RealtimeBrokerMessage:
        return RealtimeBrokerMessage(
            event=RealtimeEvent(type=event_type, data=data),
            audience=RealtimeAudience(
                kind="actor",
                actor_type=actor_type,
                actor_id=actor_id,
                tenant_id=tenant_id,
            ),
        )

    @staticmethod
    async def to_actor(
        *,
        event_type: str,
        actor_type: str,
        actor_id: UUID,
        data: dict[str, Any],
        tenant_id: UUID | None = None,
    ) -> bool:
        """
        Publish an event to one authenticated actor.
        """

        message = RealtimePublisher._actor_message(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            data=data,
            tenant_id=tenant_id,
        )

        return await realtime_broker.publish(message)

    @staticmethod
    def defer_to_actor(
        db: AsyncSession,
        *,
        event_type: str,
        actor_type: str,
        actor_id: UUID,
        data: dict[str, Any],
        tenant_id: UUID | None = None,
    ) -> None:
        """Queue an actor signal that the transaction owner publishes after commit."""

        pending = db.info.setdefault(RealtimePublisher._PENDING_SESSION_KEY, [])
        pending.append(
            RealtimePublisher._actor_message(
                event_type=event_type,
                actor_type=actor_type,
                actor_id=actor_id,
                data=data,
                tenant_id=tenant_id,
            )
        )

    @staticmethod
    async def publish_deferred_after_commit(db: AsyncSession) -> None:
        """Best-effort publish of signals whose database commit already succeeded."""

        pending = db.info.pop(RealtimePublisher._PENDING_SESSION_KEY, [])
        for message in pending:
            await realtime_broker.publish(message)

    @staticmethod
    def discard_deferred(db: AsyncSession) -> None:
        db.info.pop(RealtimePublisher._PENDING_SESSION_KEY, None)

    @staticmethod
    def deferred_checkpoint(db: AsyncSession) -> int:
        session_info = getattr(db, "info", None)
        if session_info is None:
            return 0
        return len(session_info.get(RealtimePublisher._PENDING_SESSION_KEY, []))

    @staticmethod
    def discard_deferred_since(db: AsyncSession, checkpoint: int) -> None:
        session_info = getattr(db, "info", None)
        if session_info is None:
            return
        pending = session_info.get(RealtimePublisher._PENDING_SESSION_KEY, [])
        del pending[checkpoint:]
        if not pending:
            session_info.pop(RealtimePublisher._PENDING_SESSION_KEY, None)

    @staticmethod
    async def to_tenant(
        *,
        event_type: str,
        tenant_id: UUID,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish an event to all connected actors
        belonging to one tenant.
        """

        message = RealtimeBrokerMessage(
            event=RealtimeEvent(
                type=event_type,
                data=data,
            ),
            audience=RealtimeAudience(
                kind="tenant",
                tenant_id=tenant_id,
            ),
        )

        return await realtime_broker.publish(message)

    @staticmethod
    async def broadcast(
        *,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish an event to every connected realtime client.
        """

        message = RealtimeBrokerMessage(
            event=RealtimeEvent(
                type=event_type,
                data=data,
            ),
            audience=RealtimeAudience(
                kind="broadcast",
            ),
        )

        return await realtime_broker.publish(message)
