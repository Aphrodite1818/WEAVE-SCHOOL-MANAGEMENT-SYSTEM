"""Read-only tenant-admin service for monitoring one pairing challenge."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.cbt.pairing.status_schemas import PairingStatusResponse
from app.modules.cbt.repository import CBTPairingCodeRepository
from app.modules.cbt.security import hash_pairing_code
from app.modules.tenant_admins.models import TenantAdmin


class CBTPairingStatusService:
    """Resolve the status of the exact pairing code displayed to an admin."""

    @staticmethod
    async def get_status(
        db: AsyncSession,
        *,
        admin: TenantAdmin,
        pairing_code: str,
    ) -> PairingStatusResponse:
        tenant_id = admin.tenant_id
        if tenant_id is None:
            raise NotFoundException(detail="Pairing code not found.")

        try:
            code_hash = hash_pairing_code(pairing_code)
        except ValueError as exc:
            raise NotFoundException(detail="Pairing code not found.") from exc

        record = await CBTPairingCodeRepository.get_by_hash(db, code_hash)
        if record is None or record.tenant_id != tenant_id:
            raise NotFoundException(detail="Pairing code not found.")

        if record.used_at is not None:
            status = "paired"
        elif record.invalidated_at is not None:
            status = "invalidated"
        elif record.expires_at <= datetime.now(timezone.utc):
            status = "expired"
        else:
            status = "pending"

        return PairingStatusResponse(
            status=status,
            expires_at=record.expires_at,
            server_id=record.used_by_server_id if status == "paired" else None,
        )
