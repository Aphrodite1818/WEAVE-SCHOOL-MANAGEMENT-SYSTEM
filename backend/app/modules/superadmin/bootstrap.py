"""Startup bootstrap for the built-in superadmin account."""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import get_logger
from app.config.security import hash_password, verify_password
from app.config.settings import settings
from app.modules.superadmin.models import SuperAdmin


logger = get_logger(__name__)


class SuperadminBootstrapService:
    """Ensure the configured bootstrap superadmin exists."""

    @staticmethod
    async def ensure_bootstrap_superadmin(db: AsyncSession) -> None:
        email = (settings.BOOTSTRAP_SUPERADMIN_EMAIL or "").strip().lower()
        password = settings.BOOTSTRAP_SUPERADMIN_PASSWORD or ""
        if not email or not password:
            logger.info("Bootstrap superadmin skipped; email or password is not configured.")
            return

        try:
            superadmin_id = uuid.UUID(settings.BOOTSTRAP_SUPERADMIN_ID)
        except ValueError as exc:
            raise RuntimeError("BOOTSTRAP_SUPERADMIN_ID must be a valid UUID.") from exc

        result = await db.execute(
            select(SuperAdmin).where(
                or_(
                    SuperAdmin.id == superadmin_id,
                    func.lower(SuperAdmin.email) == email,
                )
            )
        )
        matches = list(result.scalars().all())
        if len(matches) > 1:
            raise RuntimeError(
                "Bootstrap superadmin id and email match different rows. Resolve the duplicate before startup."
            )

        superadmin = matches[0] if matches else None
        if superadmin is None:
            superadmin = SuperAdmin(
                id=superadmin_id,
                email=email,
                password_hash=hash_password(password),
                is_active=True,
            )
            db.add(superadmin)
            await db.flush()
            logger.info("Bootstrap superadmin created", extra={"superadmin_id": str(superadmin_id), "email": email})
            return

        changed = False
        if superadmin.email != email:
            superadmin.email = email
            changed = True
        if not superadmin.is_active:
            superadmin.is_active = True
            changed = True
        if not verify_password(password, superadmin.password_hash):
            superadmin.password_hash = hash_password(password)
            changed = True

        if changed:
            db.add(superadmin)
            await db.flush()
            logger.info("Bootstrap superadmin updated", extra={"superadmin_id": str(superadmin.id), "email": email})
