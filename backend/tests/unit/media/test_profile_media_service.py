from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.modules.media.models import MediaOwnerType, MediaPurpose
from app.modules.media.service import MediaService
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_class", "owner_type", "purpose"),
    [
        (TenantAdmin, MediaOwnerType.TENANT_ADMIN, MediaPurpose.TENANT_ADMIN_PASSPORT),
        (Teacher, MediaOwnerType.TEACHER, MediaPurpose.TEACHER_PASSPORT),
        (Student, MediaOwnerType.STUDENT, MediaPurpose.STUDENT_PASSPORT),
    ],
)
async def test_upload_profile_passport_targets_authenticated_actor(
    monkeypatch: pytest.MonkeyPatch,
    actor_class: type,
    owner_type: MediaOwnerType,
    purpose: MediaPurpose,
) -> None:
    actor = actor_class(id=uuid4(), tenant_id=uuid4())
    upload = AsyncMock(return_value=SimpleNamespace(message="ok"))
    monkeypatch.setattr(MediaService, "_create_and_attach_media", upload)
    file = SimpleNamespace(filename="passport.jpg")

    result = await MediaService.upload_profile_passport(
        db=SimpleNamespace(),
        actor=actor,
        file=file,
    )

    assert result.message == "ok"
    upload.assert_awaited_once_with(
        db=ANY,
        actor=actor,
        owner_type=owner_type,
        owner_id=actor.id,
        purpose=purpose,
        file=file,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("actor_class", "owner_type", "purpose"),
    [
        (TenantAdmin, MediaOwnerType.TENANT_ADMIN, MediaPurpose.TENANT_ADMIN_PASSPORT),
        (Teacher, MediaOwnerType.TEACHER, MediaPurpose.TEACHER_PASSPORT),
        (Student, MediaOwnerType.STUDENT, MediaPurpose.STUDENT_PASSPORT),
    ],
)
async def test_delete_profile_passport_targets_authenticated_actor(
    monkeypatch: pytest.MonkeyPatch,
    actor_class: type,
    owner_type: MediaOwnerType,
    purpose: MediaPurpose,
) -> None:
    actor = actor_class(id=uuid4(), tenant_id=uuid4())
    delete = AsyncMock(return_value=SimpleNamespace(deleted=True))
    monkeypatch.setattr(MediaService, "_delete_current_media", delete)

    result = await MediaService.delete_current_profile_passport(
        db=SimpleNamespace(),
        actor=actor,
    )

    assert result.deleted is True
    delete.assert_awaited_once_with(
        db=ANY,
        actor=actor,
        owner_type=owner_type,
        owner_id=actor.id,
        purpose=purpose,
        delete_object=False,
    )
