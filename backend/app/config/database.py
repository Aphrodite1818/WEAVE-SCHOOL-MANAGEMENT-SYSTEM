# ====================================== #
#             database.py                #
# ====================================== #

"""Configure the application's async database engine and session factory."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.logging import is_development, resolve_log_level
from app.config.settings import settings


def _uses_pgbouncer(database_url: str) -> bool:
    """Detect common PgBouncer/pooler URLs that require cache disabling."""

    normalized_url = database_url.lower()
    return any(
        marker in normalized_url
        for marker in (
            "pgbouncer",
            "pooler.supabase.com",
            "-pooler.",
        )
    )


database_url = settings.DATABASE_URL
if not database_url:
    raise ValueError("DATABASE_URL must be set for the active environment.")

# asyncpg's prepared-statement cache improves repeated-query performance for a
# normal PostgreSQL connection. It must only be disabled when PgBouncer is used
# in transaction/statement mode, where backend connections are reassigned.
connect_args = (
    {"statement_cache_size": 0}
    if _uses_pgbouncer(database_url)
    else {}
)

engine = create_async_engine(
    database_url,
    echo=is_development() or resolve_log_level() <= logging.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_recycle=1800,
    pool_use_lifo=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
