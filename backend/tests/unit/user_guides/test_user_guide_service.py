from __future__ import annotations

import uuid

import pytest

from app.modules.user_guides.service import UserGuideService


class TenantAdmin:
    def __init__(self, *, actor_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        self.id = actor_id
        self.tenant_id = tenant_id


class ParentAccount:
    def __init__(self, *, actor_id: uuid.UUID) -> None:
        self.id = actor_id
        self.tenant_id = None


def test_tenant_actor_guide_context_is_tenant_scoped() -> None:
    actor_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    context = UserGuideService.actor_context(
        TenantAdmin(actor_id=actor_id, tenant_id=tenant_id)
    )

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
