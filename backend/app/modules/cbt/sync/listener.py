"""Dedicated PostgreSQL LISTEN connection for low-latency CBT sync wakeups."""

from __future__ import annotations

import asyncio
import asyncpg
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.config.logging import get_logger
from app.config.settings import settings
from app.modules.cbt.sync.dispatcher import CBTSyncDispatcher
from app.modules.cbt.sync.manager import cbt_connection_manager
from app.modules.cbt.sync.recorder import CBT_SYNC_NOTIFY_CHANNEL
from app.modules.cbt.sync.schemas import CBTSyncNotification

logger = get_logger(__name__)
INITIAL_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 30.0
QUEUE_MAX_SIZE = 5000


def _build_asyncpg_dsn() -> str:
    database_url = getattr(settings, "CBT_SYNC_DATABASE_URL", None) or settings.DATABASE_URL
    if not database_url:
        raise ValueError("DATABASE_URL must be configured for CBT sync listener.")
    url = make_url(database_url)
    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


class CBTSyncListener:
    def __init__(self) -> None:
        self._connection: asyncpg.Connection | None = None
        self._runner_task: asyncio.Task[None] | None = None
        self._consumer_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)

    async def start(self) -> None:
        if self._runner_task is not None and not self._runner_task.done():
            return
        self._stop_event.clear()
        self._consumer_task = asyncio.create_task(
            self._consume_notifications(), name="cbt-sync-notification-consumer"
        )
        self._runner_task = asyncio.create_task(self._run(), name="cbt-sync-listener")

    async def stop(self) -> None:
        self._stop_event.set()
        connection = self._connection
        if connection is not None and not connection.is_closed():
            try:
                await connection.close(timeout=5)
            except Exception:
                connection.terminate()
        tasks = [task for task in (self._runner_task, self._consumer_task) if task]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._runner_task = self._consumer_task = None
        self._connection = None

    def _on_notification(self, _connection, _pid, _channel, payload: str) -> None:
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.error(
                "CBT sync notification queue overflowed; forcing connected machines to reconcile."
            )
            asyncio.create_task(
                cbt_connection_manager.send_to_all(
                    message={"type": "cbt.sync.reconcile", "reason": "notification_queue_overflow"}
                )
            )

    async def _consume_notifications(self) -> None:
        while True:
            payload = await self._queue.get()
            try:
                try:
                    notification = CBTSyncNotification.model_validate_json(payload)
                except ValidationError:
                    logger.warning("Ignoring invalid CBT sync notification payload.")
                    continue
                try:
                    await CBTSyncDispatcher.dispatch(
                        tenant_id=notification.tenant_id, change_id=notification.change_id
                    )
                except Exception:
                    logger.exception(
                        "Failed to dispatch CBT sync change %s.", notification.change_id
                    )
            finally:
                self._queue.task_done()

    async def _run(self) -> None:
        retry_delay = INITIAL_RETRY_DELAY_SECONDS
        while not self._stop_event.is_set():
            connection = None
            terminated = asyncio.Event()

            def on_termination(_connection):
                terminated.set()

            try:
                connection = await asyncpg.connect(_build_asyncpg_dsn())
                self._connection = connection
                connection.add_termination_listener(on_termination)
                await connection.add_listener(CBT_SYNC_NOTIFY_CHANNEL, self._on_notification)
                logger.info(
                    "CBT sync listener subscribed to PostgreSQL channel %s.",
                    CBT_SYNC_NOTIFY_CHANNEL,
                )
                # Always reconcile after LISTEN becomes active. This also closes the initial-startup gap.
                await cbt_connection_manager.send_to_all(
                    message={"type": "cbt.sync.reconcile", "reason": "listener_ready"}
                )
                retry_delay = INITIAL_RETRY_DELAY_SECONDS
                await terminated.wait()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("CBT sync PostgreSQL listener failed.")
            finally:
                if connection is not None:
                    try:
                        connection.remove_termination_listener(on_termination)
                    except Exception:
                        pass
                    if not connection.is_closed():
                        try:
                            await connection.remove_listener(
                                CBT_SYNC_NOTIFY_CHANNEL, self._on_notification
                            )
                        except Exception:
                            pass
                        try:
                            await connection.close(timeout=5)
                        except Exception:
                            connection.terminate()
                if self._connection is connection:
                    self._connection = None
            if self._stop_event.is_set():
                break
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=retry_delay)
            except TimeoutError:
                pass
            retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY_SECONDS)


cbt_sync_listener = CBTSyncListener()
