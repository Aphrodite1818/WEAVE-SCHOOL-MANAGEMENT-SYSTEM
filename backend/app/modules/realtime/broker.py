# ====================================== #
#        modules/realtime/broker.py      #
# ====================================== #


"""Redis pub/sub transport for Weave realtime events"""

from __future__ import annotations

import asyncio
import json

from redis.asyncio import Redis

from app.config.logging import get_logger
from app.config.settings import settings
from app.modules.realtime.manager import realtime_manager
from app.modules.realtime.schemas import RealtimeBrokerMessage


logger = get_logger(__name__)

REALTIME_CHANNEL = "weave:realtime:v1"


class RealtimeRedisBroker:
    """
    Cross-process transport for ephemeral realtime events.

    Redis is only responsible for fan-out.
    PostgreSQL remains the source of truth.
    """

    def __init__(self):
        self._publisher: Redis | None = None
        self._subscriber: Redis | None = None
        self._pubsub = None
        self._listener_task: asyncio.Task | None = None

    @staticmethod
    def _create_redis_client() -> Redis:
        redis_url = settings.REALTIME_REDIS_URL or settings.REDIS_URL
        if not redis_url:
            raise RuntimeError("REALTIME_REDIS_URL or REDIS_URL is required for realtime Pub/Sub.")

        return Redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            health_check_interval=30,
        )

    async def start(self) -> bool:
        """
        Start this API process' realtime Redis subscription
        """

        if self._listener_task is not None:
            return True

        redis_url = settings.REALTIME_REDIS_URL or settings.REDIS_URL

        if not redis_url:
            logger.warning("Realtime broker not started because Redis is not configured")
            return False

        try:
            self._subscriber = self._create_redis_client()
            self._pubsub = self._subscriber.pubsub()
            await self._pubsub.subscribe(REALTIME_CHANNEL)
            self._listener_task = asyncio.create_task(
                self._listen(),
                name="weave-realtime-listener",
            )
        except Exception:
            logger.exception("Failed to start realtime Redis subscriber.")
            await self._close_redis_resources()
            return False

        logger.info("Realtime Redis subscriber started")
        return True

    async def _listen(self) -> None:
        """
        Continuously listen for realtime messages from Redis
        and dispatch them to matching local WebSocket connections.
        """

        if self._pubsub is None:
            return

        try:
            async for raw_message in self._pubsub.listen():
                if raw_message.get("type") != "message":
                    continue

                try:
                    message = RealtimeBrokerMessage.model_validate_json(raw_message["data"])

                    await realtime_manager.dispatch(
                        event=message.event,
                        audience=message.audience,
                    )

                except Exception:
                    logger.exception("Failed to process realtime Redis message.")

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Realtime Redis listener stopped unexpectedly.")

    async def publish(
        self,
        message: RealtimeBrokerMessage,
    ) -> bool:
        """
        Publish a realtime event to Redis.

        Realtime delivery is best-effort.
        Business state must already be stored elsewhere.
        """

        try:
            if self._publisher is None:
                self._publisher = self._create_redis_client()

            payload = json.dumps(
                message.model_dump(mode="json"),
                separators=(",", ":"),
            )

            await self._publisher.publish(
                REALTIME_CHANNEL,
                payload,
            )

            return True

        except Exception:
            logger.exception(
                "Failed to publish realtime event.",
                extra={
                    "event_type": message.event.type,
                    "event_id": str(message.event.event_id),
                },
            )

            return False

    async def stop(self) -> None:
        """
        Stop realtime Redis resources cleanly.
        """

        if self._listener_task is not None:
            self._listener_task.cancel()

            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

            self._listener_task = None

        await self._close_redis_resources()

        logger.info("Realtime Redis broker stopped.")

    async def _close_redis_resources(self) -> None:
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(REALTIME_CHANNEL)
            except Exception:
                logger.exception("Failed to unsubscribe realtime Redis Pub/Sub.")
            finally:
                try:
                    await self._pubsub.aclose()
                except Exception:
                    logger.exception("Failed to close realtime Redis Pub/Sub.")
                self._pubsub = None

        if self._subscriber is not None:
            try:
                await self._subscriber.aclose()
            except Exception:
                logger.exception("Failed to close realtime Redis subscriber.")
            self._subscriber = None

        if self._publisher is not None:
            try:
                await self._publisher.aclose()
            except Exception:
                logger.exception("Failed to close realtime Redis publisher.")
            self._publisher = None


realtime_broker = RealtimeRedisBroker()
