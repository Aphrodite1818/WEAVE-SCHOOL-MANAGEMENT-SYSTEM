# ====================================== #
#             database.py                #
# ====================================== #

"""Configure the application's async database engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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

connect_args = (
    {"statement_cache_size": 0}
    if _uses_pgbouncer(database_url)
    else {}
)

engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_use_lifo=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
