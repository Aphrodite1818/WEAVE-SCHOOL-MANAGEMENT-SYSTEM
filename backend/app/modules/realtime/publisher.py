# ====================================== #
#      modules/realtime/publisher.py     #
# ====================================== #

"""Domain-facing API for publishing realtime events."""

from __future__ import annotations

from typing import Any
from uuid import UUID

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

        message = RealtimeBrokerMessage(
            event=RealtimeEvent(
                type=event_type,
                data=data,
            ),
            audience=RealtimeAudience(
                kind="actor",
                actor_type=actor_type,
                actor_id=actor_id,
                tenant_id=tenant_id,
            ),
        )

        return await realtime_broker.publish(message)

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
