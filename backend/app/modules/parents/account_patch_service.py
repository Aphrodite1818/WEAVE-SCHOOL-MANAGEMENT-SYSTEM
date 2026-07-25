"""Explicit PATCH semantics for global parent profiles."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.modules.parents.repository import ParentAccountRepository
from app.modules.parents.schemas import (
    ParentAccountProfileUpdateRequest,
    ParentAccountResponse,
)
from app.modules.parents.service import ParentAccountService


class ParentAccountPatchService:
    @staticmethod
    async def update_profile(
        db: AsyncSession,
        *,
        account_id: UUID,
        payload: ParentAccountProfileUpdateRequest,
    ) -> ParentAccountResponse:
        account = ParentAccountService._require_account(
            await ParentAccountRepository.get_by_id(
                db,
                account_id,
                lock=True,
            )
        )
        ParentAccountService._require_active_account(account)
        update_data = payload.model_dump(exclude_unset=True)
        for required_name in ("first_name", "last_name"):
            if required_name in update_data and update_data[required_name] is None:
                raise BadRequestException(
                    f"{required_name} cannot be cleared from a completed profile."
                )
        for field, value in update_data.items():
            setattr(account, field, value)
        await ParentAccountRepository.save(db, account)
        await db.commit()
        await db.refresh(account)
        return ParentAccountResponse.model_validate(account)
