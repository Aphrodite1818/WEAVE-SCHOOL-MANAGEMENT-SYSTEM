"""Read-only business rules for CBT result-ingestion forensic access."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.cbt.results.models import CBTResultIngestionBatch
from app.modules.cbt.results.repository import CBTResultIngestionRepository


class CBTResultIngestionAuditService:
    """Tenant-safe read access to immutable CBT ingestion evidence."""

    @staticmethod
    def _validate_date_range(
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> None:
        if created_from is not None and created_to is not None and created_from > created_to:
            raise BadRequestException("created_from cannot be after created_to.")

    @classmethod
    async def list_batches_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        cls._validate_date_range(created_from, created_to)
        return await CBTResultIngestionRepository.list_batches(
            db,
            tenant_id=tenant_id,
            filters=filters,
            created_from=created_from,
            created_to=created_to,
            skip=skip,
            limit=limit,
        )

    @classmethod
    async def list_batches_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID | None = None,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        cls._validate_date_range(created_from, created_to)
        return await CBTResultIngestionRepository.list_batches(
            db,
            tenant_id=tenant_id,
            filters=filters,
            created_from=created_from,
            created_to=created_to,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def get_batch_for_admin(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        batch_record_id: UUID,
    ) -> CBTResultIngestionBatch:
        batch = await CBTResultIngestionRepository.get_batch_by_id(
            db,
            batch_record_id=batch_record_id,
            tenant_id=tenant_id,
        )
        if batch is None:
            raise NotFoundException("CBT result-ingestion batch not found.")
        return batch

    @staticmethod
    async def get_batch_for_superadmin(
        db: AsyncSession,
        *,
        batch_record_id: UUID,
    ) -> CBTResultIngestionBatch:
        batch = await CBTResultIngestionRepository.get_batch_by_id(
            db,
            batch_record_id=batch_record_id,
            tenant_id=None,
        )
        if batch is None:
            raise NotFoundException("CBT result-ingestion batch not found.")
        return batch

    @classmethod
    async def list_batch_items_for_admin(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        batch_record_id: UUID,
        filters: Mapping[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        await cls.get_batch_for_admin(
            db,
            tenant_id=tenant_id,
            batch_record_id=batch_record_id,
        )
        item_filters = dict(filters or {})
        item_filters["ingestion_batch_id"] = batch_record_id
        return await CBTResultIngestionRepository.list_items(
            db,
            tenant_id=tenant_id,
            filters=item_filters,
            skip=skip,
            limit=limit,
        )

    @classmethod
    async def list_batch_items_for_superadmin(
        cls,
        db: AsyncSession,
        *,
        batch_record_id: UUID,
        filters: Mapping[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
    ):
        batch = await cls.get_batch_for_superadmin(
            db,
            batch_record_id=batch_record_id,
        )
        item_filters = dict(filters or {})
        item_filters["ingestion_batch_id"] = batch_record_id
        return await CBTResultIngestionRepository.list_items(
            db,
            tenant_id=batch.tenant_id,
            filters=item_filters,
            skip=skip,
            limit=limit,
        )
