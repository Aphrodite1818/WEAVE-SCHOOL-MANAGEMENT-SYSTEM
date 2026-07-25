from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.announcements.models import (
    AnnouncementRecipientRole,
    AnnouncementTargetType,
)
from app.modules.announcements.schemas import AnnouncementTargetCreate
from app.modules.announcements.service import AnnouncementService
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


def test_rejects_mismatched_target_fields() -> None:
    target = AnnouncementTargetCreate(
        target_type=AnnouncementTargetType.CLASS,
        student_id=uuid4(),
    )

    with pytest.raises(BadRequestException):
        AnnouncementService._validate_target_shape(target)


@pytest.mark.asyncio
async def test_teacher_cannot_broadcast_to_all() -> None:
    teacher = Teacher(
        id=uuid4(),
        tenant_id=uuid4(),
    )

    with pytest.raises(ForbiddenException):
        await AnnouncementService._validate_targets(
            SimpleNamespace(),
            teacher,
            teacher.tenant_id,
            [AnnouncementTargetCreate(target_type=AnnouncementTargetType.ALL)],
        )


@pytest.mark.asyncio
async def test_school_announcement_cannot_target_tenant_admin_role() -> None:
    admin = TenantAdmin(
        id=uuid4(),
        tenant_id=uuid4(),
        email="admin@example.com",
        password_hash="hashed",
    )

    with pytest.raises(ForbiddenException):
        await AnnouncementService._validate_targets(
            SimpleNamespace(),
            admin,
            admin.tenant_id,
            [
                AnnouncementTargetCreate(
                    target_type=AnnouncementTargetType.ROLE,
                    role=AnnouncementRecipientRole.TENANT_ADMIN,
                )
            ],
        )
