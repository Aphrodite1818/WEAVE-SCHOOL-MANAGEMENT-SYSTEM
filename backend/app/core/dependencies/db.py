# ======================================#
#                db.py                 #
# ======================================#

"""Provide database session dependencies for FastAPI routes."""

from typing import Annotated, AsyncGenerator, TypeAlias

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.config.logging import get_logger
from app.core.cache.events import (
    discard_cache_invalidation_events,
    flush_cache_invalidation_events,
)

logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async database session."""
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
            from app.modules.realtime.publisher import RealtimePublisher

            await RealtimePublisher.publish_deferred_after_commit(db)
            await flush_cache_invalidation_events(db)
        except Exception:
            logger.warning("Database session rollback due to exception", exc_info=True)
            await db.rollback()
            discard_cache_invalidation_events(db)
            from app.modules.realtime.publisher import RealtimePublisher

            RealtimePublisher.discard_deferred(db)
            raise
        finally:
            await db.close()


DbSession: TypeAlias = Annotated[AsyncSession, Depends(get_db)]
