from __future__ import annotations

import uuid

import pytest

from app.core.dependencies.route_guards import (
    get_current_parent,
    get_current_parent_account,
)
from app.core.exceptions import ForbiddenException
from app.modules.parents.models import (
    Parent,
    ParentAccount,
    ParentAccountStatus,
    ParentMembershipStatus,
)


def build_parent_account(*, active: bool = True) -> ParentAccount:
    return ParentAccount(
        email="parent@example.com",
        password_hash="not-used-by-guard-tests",
        first_name="Bola",
        last_name="Parent",
        account_status=(
            ParentAccountStatus.ACTIVE
            if active
            else ParentAccountStatus.INACTIVE
        ),
        is_verified=active,
        is_active=active,
    )


def build_parent_membership(account: ParentAccount) -> Parent:
    return Parent(
        tenant_id=uuid.uuid4(),
        parent_account=account,
        status=ParentMembershipStatus.ACTIVE,
    )


@pytest.mark.asyncio
async def test_parent_membership_resolves_its_global_parent_account() -> None:
    account = build_parent_account()
    membership = build_parent_membership(account)

    resolved = await get_current_parent_account(membership)

    assert resolved is account


@pytest.mark.asyncio
async def test_global_parent_account_is_returned_directly() -> None:
    account = build_parent_account()

    resolved = await get_current_parent_account(account)

    assert resolved is account


@pytest.mark.asyncio
async def test_inactive_parent_account_is_rejected_from_membership_context() -> None:
    membership = build_parent_membership(build_parent_account(active=False))

    with pytest.raises(ForbiddenException, match="Inactive account"):
        await get_current_parent_account(membership)


@pytest.mark.asyncio
async def test_global_parent_account_cannot_access_membership_only_guard() -> None:
    account = build_parent_account()

    with pytest.raises(
        ForbiddenException,
        match="Parent membership credentials are required",
    ):
        await get_current_parent(account, None)  # type: ignore[arg-type]
