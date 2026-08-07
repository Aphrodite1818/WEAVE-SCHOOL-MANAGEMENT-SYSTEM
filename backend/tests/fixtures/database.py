"""Shared async database fixtures for tests."""

from collections.abc import AsyncGenerator
from os import getenv

import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config.settings import settings
from app.shared.base_model import Base

# Import models so SQLAlchemy registers all tables before create_all() runs.
from app.modules.auth import models as _auth_models  # noqa: F401
from app.modules.communications import models as _communication_models  # noqa: F401
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


async def _ensure_archive_columns(
    test_engine: AsyncEngine,
    *,
    table_name: str,
    check_constraint_name: str,
    index_name: str,
) -> None:
    """Repair archive columns on long-lived local test tables."""

    async with test_engine.begin() as connection:
        await connection.execute(
            text(f"""
                ALTER TABLE public.{table_name}
                ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text(f"""
                ALTER TABLE public.{table_name}
                ADD COLUMN IF NOT EXISTS archived_by_admin_id UUID
                """)
        )
        await connection.execute(
            text(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = '{check_constraint_name}'
                    ) THEN
                        ALTER TABLE public.{table_name}
                        ADD CONSTRAINT {check_constraint_name}
                        CHECK (archived_at IS NULL OR is_active = false);
                    END IF;
                END $$;
                """)
        )
        await connection.execute(
            text(f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON public.{table_name} (tenant_id, archived_at)
                """)
        )


async def _ensure_test_schema_compatibility(test_engine: AsyncEngine) -> None:
    """Bring long-lived local test databases up to the current ORM baseline.

    SQLAlchemy's create_all() only creates missing tables; it does not alter an
    existing table when new model columns are added. Keep this narrow so tests
    fail loudly for unrelated schema drift.
    """

    await _ensure_archive_columns(
        test_engine,
        table_name="classes",
        check_constraint_name="ck_classes_archived_requires_inactive",
        index_name="ix_classes_tenant_archived",
    )
    await _ensure_archive_columns(
        test_engine,
        table_name="subjects",
        check_constraint_name="ck_subjects_archived_requires_inactive",
        index_name="ix_subjects_tenant_archived",
    )
    await _ensure_archive_columns(
        test_engine,
        table_name="class_subjects",
        check_constraint_name="ck_class_subjects_archived_requires_inactive",
        index_name="ix_class_subjects_tenant_archived",
    )
    async with test_engine.begin() as connection:
        await connection.execute(
            text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typname = 'academic_session_status'
                          AND n.nspname = 'public'
                    ) THEN
                        CREATE TYPE public.academic_session_status
                        AS ENUM ('draft', 'open', 'closed', 'closing');
                    END IF;
                END $$;
                """)
        )
        await connection.execute(
            text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typname = 'academic_term_status'
                          AND n.nspname = 'public'
                    ) THEN
                        CREATE TYPE public.academic_term_status
                        AS ENUM ('draft', 'open', 'closed');
                    END IF;
                END $$;
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_sessions
                ADD COLUMN IF NOT EXISTS status public.academic_session_status
                NOT NULL DEFAULT 'draft'
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_sessions
                ADD COLUMN IF NOT EXISTS closing_started_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_sessions
                ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_sessions
                ADD COLUMN IF NOT EXISTS closed_by_admin_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_sessions
                ADD COLUMN IF NOT EXISTS next_academic_session_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_terms
                ADD COLUMN IF NOT EXISTS status public.academic_term_status
                NOT NULL DEFAULT 'draft'
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_terms
                ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_terms
                ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_terms
                ADD COLUMN IF NOT EXISTS opened_by_admin_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.academic_terms
                ADD COLUMN IF NOT EXISTS closed_by_admin_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TYPE public.academic_result_status
                ADD VALUE IF NOT EXISTS 'approved'
                """)
        )
        await connection.execute(
            text("""
                ALTER TYPE public.academic_result_status
                ADD VALUE IF NOT EXISTS 'locked'
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS submitted_by_actor_type VARCHAR(50)
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS submitted_by_actor_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS approved_by_admin_id UUID
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITH TIME ZONE
                """)
        )
        await connection.execute(
            text("""
                ALTER TABLE public.student_subject_results
                ADD COLUMN IF NOT EXISTS locked_by_admin_id UUID
                """)
        )


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
    await _ensure_test_schema_compatibility(test_engine)
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
