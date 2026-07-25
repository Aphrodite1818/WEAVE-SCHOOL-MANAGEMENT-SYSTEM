"""Explicit PATCH semantics for teacher accounts and memberships."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.teachers.models import TeacherMembership
from app.modules.teachers.repository import (
    TeacherAccountRepository,
    TeacherMembershipRepository,
)
from app.modules.teachers.schemas import (
    TeacherAccountProfileUpdateRequest,
    TeacherAccountResponse,
    TeacherMembershipResponse,
    TeacherMembershipUpdateRequest,
)
from app.modules.teachers.service import TeacherAccountService
from app.modules.tenant_admins.models import TenantAdmin


class TeacherPatchService:
    @staticmethod
    async def update_account_profile(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: TeacherAccountProfileUpdateRequest,
    ) -> TeacherAccountResponse:
        account = TeacherAccountService._require_account(
            await TeacherAccountRepository.get_by_id(
                db,
                account_id,
                lock=True,
            )
        )
        TeacherAccountService._require_active_account(account)
        update_data = payload.model_dump(exclude_unset=True)
        for required_name in ("first_name", "last_name"):
            if required_name in update_data and update_data[required_name] is None:
                raise BadRequestException(
                    f"{required_name} cannot be cleared from a completed profile."
                )
        for field, value in update_data.items():
            setattr(account, field, value)
        await TeacherAccountRepository.save(db, account)
        await db.commit()
        await db.refresh(account)
        return TeacherAccountResponse.model_validate(account)

    @staticmethod
    async def update_membership(
        db: AsyncSession,
        *,
        actor: TenantAdmin | TeacherMembership,
        membership_id: UUID,
        payload: TeacherMembershipUpdateRequest,
    ) -> TeacherMembershipResponse:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        update_data = payload.model_dump(exclude_unset=True)
        if isinstance(actor, TeacherMembership):
            if actor.id != membership.id:
                raise ForbiddenException(
                    "Teachers can update only their own membership preferences."
                )
            allowed = {
                "receive_email_notifications",
                "receive_push_notifications",
            }
            if not set(update_data).issubset(allowed):
                raise ForbiddenException(
                    "Employment fields are controlled by the school."
                )

        for boolean_field in (
            "receive_email_notifications",
            "receive_push_notifications",
        ):
            if boolean_field in update_data and update_data[boolean_field] is None:
                raise BadRequestException(
                    f"{boolean_field} must be true or false."
                )

        for field, value in update_data.items():
            setattr(membership, field, value)
        await TeacherMembershipRepository.save(db, membership)
        await db.commit()
        await db.refresh(membership)
        return TeacherMembershipResponse.model_validate(membership)
