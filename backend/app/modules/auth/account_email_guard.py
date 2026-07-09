#================================#
#  auth/account_email_guard.py   #
#================================#


""" Cross-account email conflict guards


This module protects platform level accounts from colliding with tenant level accounts.
Auth identity protects tenant actors from each other, but superadmins live outside Authidentity, so every tenant email 
create/update flow must explicitly check the superadmins table 
"""



from __future__ import annotations

import stat
from typing import Callable
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.modules.superadmin.repository import SuperAdminRepository


class AccountEmailGuard:
    """Reusable email guards for account creation/update flows"""


    @staticmethod
    def _normalize_email(email : str) -> str:
        """Normalize email consistently before lookup or storage"""
        return email.strip().lower()
    



    @staticmethod
    async def ensure_not_superadmin_email(
        db : AsyncSession,
        email: str,
        *,
        exclude_superadmin_id : uuid.UUID | None = None ,
        message : str = "This email is already in use"
    ) -> str:
        """
        Blocks tenant accounts fron using an existing superadmin email

        Returns the normalized email so callers can use on consistent value

        exclude_super_admin_id exists for future superadmin profile-update flows.
        do not need it for tenant admin , teacher , parent or tenant creation
        """

        normalized_email = AccountEmailGuard._normalize_email(email)

        existing_superadmin = await SuperAdminRepository.get_by_email(
            db = db ,
            email = normalized_email
        )

        if existing_superadmin is not None:
            if(
                exclude_superadmin_id is None
                or existing_superadmin.id != exclude_superadmin_id
            ):
                raise ConflictException(message)
            
        return normalized_email