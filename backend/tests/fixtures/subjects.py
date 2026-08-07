import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.subjects.models import Subject
from app.tenant_management.models import Tenant


@pytest_asyncio.fixture  # used for asynchronous functions
async def subject_object(db_session: AsyncSession, tenant: Tenant) -> Subject:
    subject = Subject(
        tenant_id=tenant.id,
        name="Mathematics",
        code="MATH",
        description="Core mathematics subject",
        is_active=True,
    )

    db_session.add(subject)
    await db_session.flush()
    await db_session.refresh(subject)

    return subject


@pytest_asyncio.fixture
async def inactive_subject(
    db_session: AsyncSession,
    tenant: Tenant,
) -> Subject:
    subject = Subject(
        tenant_id=tenant.id,
        name="Physics",
        code="PHY",
        description="Physics subject",
        is_active=False,
    )

    db_session.add(subject)

    await db_session.flush()
    await db_session.refresh(subject)

    return subject


@pytest_asyncio.fixture
async def multiple_subjects(
    db_session: AsyncSession,
    tenant: Tenant,
) -> list[Subject]:
    subjects = [
        Subject(
            tenant_id=tenant.id,
            name="Mathematics",
            code="MATH",
            description="Mathematics",
            is_active=True,
        ),
        Subject(
            tenant_id=tenant.id,
            name="English",
            code="ENG",
            description="English Language",
            is_active=True,
        ),
        Subject(
            tenant_id=tenant.id,
            name="Physics",
            code="PHY",
            description="Physics",
            is_active=False,
        ),
    ]

    db_session.add_all(subjects)

    await db_session.flush()

    for subject in subjects:
        await db_session.refresh(subject)

    return subjects
