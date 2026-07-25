from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementStatus,
)
from app.modules.announcements.schemas import AnnouncementUpdate
from app.modules.announcements.service import AnnouncementService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _admin(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def _announcement(tenant_id: uuid.UUID) -> Announcement:
    now = datetime.now(timezone.utc)
    return Announcement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="Assembly",
        body="Morning assembly starts early.",
        category=AnnouncementCategory.GENERAL,
        priority=AnnouncementPriority.NORMAL,
        status=AnnouncementStatus.DRAFT,
        created_by_actor_type=AnnouncementActorType.TENANT_ADMIN,
        created_by_actor_id=uuid.uuid4(),
        publish_at=now,
        expires_at=now,
        is_pinned=True,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_update_announcement_ignores_explicit_null_values() -> None:
    tenant_id = uuid.uuid4()
    announcement = _announcement(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.announcements.service.AnnouncementService._get_manageable",
            new=AsyncMock(return_value=announcement),
        ),
        patch(
            "app.modules.announcements.service.AnnouncementRepository.save",
            new=AsyncMock(return_value=announcement),
        ),
        patch(
            "app.modules.announcements.service.AnnouncementService._invalidate_after_announcement_write",
            new=AsyncMock(),
        ),
    ):
        updated = await AnnouncementService.update(
            db=db,
            actor=_admin(tenant_id),
            announcement_id=announcement.id,
            payload=AnnouncementUpdate(
                title=None,
                body=None,
                category=None,
                priority=None,
                publish_at=None,
                expires_at=None,
                is_pinned=None,
            ),
        )

    assert updated.title == "Assembly"
    assert updated.body == "Morning assembly starts early."
    assert updated.category == AnnouncementCategory.GENERAL
    assert updated.priority == AnnouncementPriority.NORMAL
    assert updated.publish_at is not None
    assert updated.expires_at is not None
    assert updated.is_pinned is True


@pytest.mark.asyncio
async def test_update_announcement_applies_explicit_values() -> None:
    tenant_id = uuid.uuid4()
    announcement = _announcement(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.announcements.service.AnnouncementService._get_manageable",
            new=AsyncMock(return_value=announcement),
        ),
        patch(
            "app.modules.announcements.service.AnnouncementRepository.save",
            new=AsyncMock(return_value=announcement),
        ),
        patch(
            "app.modules.announcements.service.AnnouncementService._invalidate_after_announcement_write",
            new=AsyncMock(),
        ),
    ):
        updated = await AnnouncementService.update(
            db=db,
            actor=_admin(tenant_id),
            announcement_id=announcement.id,
            payload=AnnouncementUpdate(title="Open Day", is_pinned=False),
        )

    assert updated.title == "Open Day"
    assert updated.is_pinned is False
