from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.modules.students.models import (
    ParentLinkVerifiedByType,
    ParentRelationship,
    StudentParentLink,
    StudentParentLinkStatus,
)
from app.modules.students.schemas import StudentParentLinkUpdateRequest
from app.modules.students.service import StudentParentLinkService
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


def _actor(tenant_id: uuid.UUID) -> TenantAdmin:
    return TenantAdmin(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="admin@example.test",
        password_hash="hashed-password",
        account_status=TenantAdminStatus.ACTIVE,
        is_verified=True,
        is_active=True,
    )


def _link(tenant_id: uuid.UUID) -> StudentParentLink:
    now = datetime.now(timezone.utc)
    return StudentParentLink(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        student_id=uuid.uuid4(),
        parent_membership_id=uuid.uuid4(),
        relationship_type=ParentRelationship.MOTHER,
        status=StudentParentLinkStatus.ACTIVE,
        is_primary_contact=True,
        receives_academic_updates=True,
        receives_fee_updates=True,
        verified_at=now,
        verified_by_type=ParentLinkVerifiedByType.TENANT_ADMIN,
        verified_by_id=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def test_update_parent_link_rejects_explicit_null_values() -> None:
    with pytest.raises(ValidationError):
        StudentParentLinkUpdateRequest(
            relationship_type=None,
            is_primary_contact=None,
            receives_academic_updates=None,
            receives_fee_updates=None,
        )


@pytest.mark.asyncio
async def test_update_parent_link_applies_explicit_values_only() -> None:
    tenant_id = uuid.uuid4()
    link = _link(tenant_id)
    db = AsyncMock()

    with (
        patch(
            "app.modules.students.service.StudentParentLinkRepository.get_by_id",
            new=AsyncMock(return_value=link),
        ),
        patch(
            "app.modules.students.service.StudentParentLinkRepository.save",
            new=AsyncMock(return_value=link),
        ),
    ):
        response = await StudentParentLinkService.update(
            db=db,
            actor=_actor(tenant_id),
            link_id=link.id,
            payload=StudentParentLinkUpdateRequest(
                relationship_type=ParentRelationship.FATHER,
                receives_fee_updates=False,
            ),
        )

    assert link.relationship_type == ParentRelationship.FATHER
    assert link.receives_fee_updates is False
    assert link.is_primary_contact is True
    assert link.receives_academic_updates is True
    assert response.relationship_type == ParentRelationship.FATHER
