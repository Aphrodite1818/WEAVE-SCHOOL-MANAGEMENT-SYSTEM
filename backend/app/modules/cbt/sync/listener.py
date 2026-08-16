# ======================================#
# backend.app.modules.cbt.sync.listener
# ======================================#

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


def _build_asyncpg_dsn() -> str:
    """
    Convert the SQLAlchemy PostgreSQL URL into a DSN asyncpg can use.

    Example:

    postgresql+asyncpg://...
        ↓
    postgresql://...
    """

    database_url = settings.DATABASE_URL

    if not database_url:
        raise ValueError(
            "DATABASE_URL must be configured for CBT sync listener."
        )

    url = make_url(database_url)

    if url.drivername.startswith("postgresql+"):
        url = url.set(drivername="postgresql")

    return url.render_as_string(
        hide_password=False,
    )


class CBTSyncListener:
    """
    Maintain one dedicated PostgreSQL LISTEN connection for this
    API process.

    PostgreSQL NOTIFY is only the live wake-up mechanism.

    CBTSyncChange remains the durable synchronization source of truth.
    """

    def __init__(self) -> None:
        self._connection: asyncpg.Connection | None = None

        self._runner_task: asyncio.Task[None] | None = None
        self._consumer_task: asyncio.Task[None] | None = None

        self._stop_event = asyncio.Event()

        # Notifications are consumed sequentially so this process does
        # not reorder CBT changes while dispatching them.
        self._queue: asyncio.Queue[str] = asyncio.Queue()

        self._connected_once = False

    async def start(self) -> None:
        """Start the PostgreSQL notification listener."""

        if (
            self._runner_task is not None
            and not self._runner_task.done()
        ):
            return

        self._stop_event.clear()

        self._consumer_task = asyncio.create_task(
            self._consume_notifications(),
            name="cbt-sync-notification-consumer",
        )

        self._runner_task = asyncio.create_task(
            self._run(),
            name="cbt-sync-listener",
        )

    async def stop(self) -> None:
        """Stop the listener and release its dedicated DB connection."""

        self._stop_event.set()

        connection = self._connection

        if (
            connection is not None
            and not connection.is_closed()
        ):
            try:
                await connection.close(timeout=5)
            except Exception:
                connection.terminate()

        tasks = [
            task
            for task in (
                self._runner_task,
                self._consumer_task,
            )
            if task is not None
        ]

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        self._runner_task = None
        self._consumer_task = None
        self._connection = None

    def _on_notification(
        self,
        _connection: asyncpg.Connection,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        """
        Receive a PostgreSQL notification.

        Do not perform database or WebSocket work inside the asyncpg
        callback. Queue it for ordered asynchronous processing.
        """

        self._queue.put_nowait(payload)

    async def _consume_notifications(self) -> None:
        """Process PostgreSQL notifications in arrival order."""

        while True:
            payload = await self._queue.get()

            try:
                try:
                    notification = (
                        CBTSyncNotification.model_validate_json(
                            payload
                        )
                    )
                except ValidationError:
                    logger.warning(
                        "Ignoring invalid CBT sync notification payload."
                    )
                    continue

                try:
                    await CBTSyncDispatcher.dispatch(
                        tenant_id=notification.tenant_id,
                        change_id=notification.change_id,
                    )
                except Exception:
                    # A failed live dispatch must not destroy the listener.
                    #
                    # The durable CBTSyncChange remains available through
                    # cursor-based REST recovery.
                    logger.exception(
                        "Failed to dispatch CBT sync change %s.",
                        notification.change_id,
                    )

            finally:
                self._queue.task_done()

    async def _run(self) -> None:
        """
        Maintain the dedicated LISTEN connection.

        Reconnect automatically with bounded exponential backoff when
        PostgreSQL connectivity is interrupted.
        """

        retry_delay = INITIAL_RETRY_DELAY_SECONDS

        while not self._stop_event.is_set():
            connection: asyncpg.Connection | None = None
            terminated = asyncio.Event()

            def on_termination(
                _connection: asyncpg.Connection,
            ) -> None:
                terminated.set()

            try:
                connection = await asyncpg.connect(
                    _build_asyncpg_dsn()
                )

                self._connection = connection

                connection.add_termination_listener(
                    on_termination
                )

                await connection.add_listener(
                    CBT_SYNC_NOTIFY_CHANNEL,
                    self._on_notification,
                )

                logger.info(
                    "CBT sync listener subscribed to PostgreSQL channel %s.",
                    CBT_SYNC_NOTIFY_CHANNEL,
                )

                # If this is a reconnect rather than the first startup,
                # notifications may have been missed while this listener
                # was disconnected.
                #
                # Tell every CBT socket owned by THIS API process to
                # reconcile using its durable cursor.
                if self._connected_once:
                    await cbt_connection_manager.send_to_all(
                        message={
                            "type": "cbt.sync.reconcile",
                            "reason": "listener_recovered",
                        }
                    )

                self._connected_once = True
                retry_delay = INITIAL_RETRY_DELAY_SECONDS

                # Remain here until asyncpg tells us that the dedicated
                # PostgreSQL connection has terminated.
                await terminated.wait()

                if not self._stop_event.is_set():
                    logger.warning(
                        "CBT sync PostgreSQL listener connection was lost."
                    )

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "CBT sync PostgreSQL listener failed."
                )

            finally:
                if connection is not None:
                    try:
                        connection.remove_termination_listener(
                            on_termination
                        )
                    except Exception:
                        pass

                    if not connection.is_closed():
                        try:
                            await connection.remove_listener(
                                CBT_SYNC_NOTIFY_CHANNEL,
                                self._on_notification,
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
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=retry_delay,
                )
            except TimeoutError:
                pass

            retry_delay = min(
                retry_delay * 2,
                MAX_RETRY_DELAY_SECONDS,
            )


cbt_sync_listener = CBTSyncListener()