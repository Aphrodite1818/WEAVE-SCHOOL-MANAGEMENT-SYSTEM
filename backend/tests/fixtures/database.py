"""Shared async database fixtures for tests."""

from collections.abc import AsyncGenerator
from os import getenv

import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config.settings import settings
from app.shared.base_model import Base

# Import models so SQLAlchemy registers all tables before create_all() runs.
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.announcements import models as _announcement_models  # noqa: F401
from app.modules.auth_identity import models as _auth_identity_models  # noqa: F401
from app.modules.attendance import models as _attendance_models  # noqa: F401
from app.modules.classes import models as _classes_models  # noqa: F401
from app.modules.student_academics import models as _exams_models  # noqa: F401
from app.modules.finance import models as _finance_models  # noqa: F401
from app.modules.parents import models as _parent_models  # noqa: F401
from app.modules.results import models as _results_models  # noqa: F401
from app.modules.students import models as _students_models  # noqa: F401
from app.modules.subjects import models as _subjects_models  # noqa: F401
from app.modules.superadmin import models as _superadmin_models  # noqa: F401
from app.modules.teachers import models as _teachers_models  # noqa: F401
from app.modules.tenant_admins import models as _tenant_admin_models  # noqa: F401
from app.tenant_management import models as _tenant_models  # noqa: F401


def _resolve_test_database_url() -> str:
    """Prefer an isolated test database over the shared runtime database."""
    test_database_url = getenv("TEST_DATABASE_URL")
    if test_database_url:
        return test_database_url

    if "supabase.co" in settings.DATABASE_URL:
        raise RuntimeError(
            "Set TEST_DATABASE_URL to an isolated PostgreSQL database before running pytest. "
            "The configured DATABASE_URL points at a shared Supabase database."
        )

    return settings.DATABASE_URL


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a dedicated async engine for tests."""
    engine = create_async_engine(
        _resolve_test_database_url(),
        pool_pre_ping=True,
        connect_args={"statement_cache_size": 0},
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def _create_test_tables(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Create all ORM tables once for the test session."""
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session(
    _create_test_tables,
    test_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated async session backed by a rollbackable transaction."""
    async with test_engine.connect() as connection:
        outer_transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        await session.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def _restart_savepoint(sync_session, transaction) -> None:
            if transaction.nested and not transaction._parent.nested:
                sync_session.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await outer_transaction.rollback()
