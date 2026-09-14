"""Bounded retention for the durable CBT cursor log.

CBT machines older than the retained window recover with a fresh bootstrap. This
keeps the append-only log bounded without making long-offline appliances unsafe.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.modules.cbt.sync.repository import CBTSyncRepository

logger = get_logger(__name__)
RETENTION_DAYS = 30
PRUNE_INTERVAL_SECONDS = 60 * 60
RETENTION_LOCK_KEY = 873_421_946


class CBTSyncRetention:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="cbt-sync-retention")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.prune_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("CBT sync retention pruning failed.")
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=PRUNE_INTERVAL_SECONDS,
                )
            except TimeoutError:
                pass

    @staticmethod
    async def prune_once() -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
        async with AsyncSessionLocal() as db:
            async with db.begin():
                acquired = bool(
                    await db.scalar(
                        text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                        {"lock_key": RETENTION_LOCK_KEY},
                    )
                )
                if not acquired:
                    return 0
                deleted = await CBTSyncRepository.prune_before(db, cutoff=cutoff)
        if deleted:
            logger.info("Pruned %s expired CBT sync change rows.", deleted)
        return deleted


cbt_sync_retention = CBTSyncRetention()
