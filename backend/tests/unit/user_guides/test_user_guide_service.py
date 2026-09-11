from __future__ import annotations

import uuid

import pytest
from unittest.mock import AsyncMock, patch

from app.modules.user_guides.service import (
    TEACHER_CLASS_DUTIES_GUIDE_KEY,
    TEACHER_CLASS_DUTIES_QUEUED_STEP,
    UserGuideService,
)


class TenantAdmin:
    def __init__(self, *, actor_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        self.id = actor_id
        self.tenant_id = tenant_id


class ParentAccount:
    def __init__(self, *, actor_id: uuid.UUID) -> None:
        self.id = actor_id
        self.tenant_id = None


class TeacherMembership:
    def __init__(self, *, account_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        self.id = uuid.uuid4()
        self.teacher_account_id = account_id
        self.tenant_id = tenant_id


def test_tenant_actor_guide_context_is_tenant_scoped() -> None:
    actor_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    context = UserGuideService.actor_context(TenantAdmin(actor_id=actor_id, tenant_id=tenant_id))

    assert context.actor_type == "tenant_admin"
    assert context.actor_id == actor_id
    assert context.tenant_id == tenant_id
    assert context.scope_key == str(tenant_id)


def test_global_actor_guide_context_is_not_shared_between_actors() -> None:
    actor_id = uuid.uuid4()

    context = UserGuideService.actor_context(ParentAccount(actor_id=actor_id))

    assert context.actor_type == "parent_account"
    assert context.actor_id == actor_id
    assert context.tenant_id is None
    assert context.scope_key == "global"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("tenant_admin_academic_setup", "tenant_admin_academic_setup"),
        (" Teacher_Workspace_Intro ", "teacher_workspace_intro"),
    ],
)
def test_guide_keys_are_normalized(value: str, expected: str) -> None:
    assert UserGuideService.validate_guide_key(value) == expected


@pytest.mark.parametrize("value", ["a", "bad key", "../guide", "guide/child"])
def test_invalid_guide_keys_are_rejected(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid guide key"):
        UserGuideService.validate_guide_key(value)


@pytest.mark.asyncio
async def test_class_duty_guide_is_queued_only_when_no_state_exists() -> None:
    teacher = TeacherMembership(account_id=uuid.uuid4(), tenant_id=uuid.uuid4())
    db = AsyncMock()

    with (
        patch(
            "app.modules.user_guides.service.UserGuideRepository.get_state",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.user_guides.service.UserGuideRepository.save",
            new=AsyncMock(),
        ) as save,
    ):
        queued = await UserGuideService.queue_if_absent(
            db,
            actor=teacher,
            guide_key=TEACHER_CLASS_DUTIES_GUIDE_KEY,
            current_step=TEACHER_CLASS_DUTIES_QUEUED_STEP,
        )

    assert queued is True
    state = save.await_args.args[1]
    assert state.actor_id == teacher.teacher_account_id
    assert state.scope_key == "global"
    assert state.status == "in_progress"
    assert state.current_step == TEACHER_CLASS_DUTIES_QUEUED_STEP
