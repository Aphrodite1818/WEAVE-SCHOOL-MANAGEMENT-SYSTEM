"""Persistence queries for CBT result ingestion and its audit ledger."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.results.models import (
    CBTResultIngestionBatch,
    CBTResultIngestionItem,
)


class CBTResultIngestionRepository:
    """Persistence queries for CBT result ingestion and its audit ledger."""

    _BATCH_FILTERS = {
        "id": CBTResultIngestionBatch.id,
        "batch_id": CBTResultIngestionBatch.batch_id,
        "ingestion_reference": CBTResultIngestionBatch.ingestion_reference,
        "source_exam_id": CBTResultIngestionBatch.source_exam_id,
        "cbt_server_id": CBTResultIngestionBatch.cbt_server_id,
        "credential_id": CBTResultIngestionBatch.credential_id,
        "academic_session_id": CBTResultIngestionBatch.academic_session_id,
        "academic_term_id": CBTResultIngestionBatch.academic_term_id,
        "academic_level_id": CBTResultIngestionBatch.academic_level_id,
        "curriculum_subject_id": CBTResultIngestionBatch.curriculum_subject_id,
        "assessment_component_id": CBTResultIngestionBatch.assessment_component_id,
        "exam_date": CBTResultIngestionBatch.exam_date,
        "status": CBTResultIngestionBatch.status,
    }

    _ITEM_FILTERS = {
        "id": CBTResultIngestionItem.id,
        "ingestion_batch_id": CBTResultIngestionItem.ingestion_batch_id,
        "submitted_student_id": CBTResultIngestionItem.submitted_student_id,
        "outcome": CBTResultIngestionItem.outcome,
        "error_code": CBTResultIngestionItem.error_code,
        "student_subject_result_id": CBTResultIngestionItem.student_subject_result_id,
        "resolved_teacher_assignment_id": CBTResultIngestionItem.resolved_teacher_assignment_id,
    }

    @staticmethod
    def _apply_filters(
        statement: Select[Any],
        *,
        allowed_filters: Mapping[str, Any],
        filters: Mapping[str, Any] | None,
    ) -> Select[Any]:
        """Apply explicitly whitelisted exact-match filters."""

        if not filters:
            return statement

        for name, value in filters.items():
            if value is None:
                continue
            column = allowed_filters.get(name)
            if column is None:
                raise ValueError(f"Unsupported CBT result-ingestion filter: {name}")
            statement = statement.where(column == value)
        return statement

    @staticmethod
    def _apply_created_at_range(
        statement: Select[Any],
        *,
        column: Any,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> Select[Any]:
        if created_from is not None:
            statement = statement.where(column >= created_from)
        if created_to is not None:
            statement = statement.where(column <= created_to)
        return statement

    @classmethod
    async def list_batches(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID | None,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CBTResultIngestionBatch], int]:
        conditions = []
        if tenant_id is not None:
            conditions.append(CBTResultIngestionBatch.tenant_id == tenant_id)

        query = select(CBTResultIngestionBatch).where(*conditions)
        count_query = select(func.count()).select_from(CBTResultIngestionBatch).where(*conditions)
        query = cls._apply_filters(query, allowed_filters=cls._BATCH_FILTERS, filters=filters)
        count_query = cls._apply_filters(
            count_query,
            allowed_filters=cls._BATCH_FILTERS,
            filters=filters,
        )
        query = cls._apply_created_at_range(
            query,
            column=CBTResultIngestionBatch.created_at,
            created_from=created_from,
            created_to=created_to,
        )
        count_query = cls._apply_created_at_range(
            count_query,
            column=CBTResultIngestionBatch.created_at,
            created_from=created_from,
            created_to=created_to,
        )
        query = (
            query.order_by(
                CBTResultIngestionBatch.created_at.desc(),
                CBTResultIngestionBatch.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        total = await db.scalar(count_query)
        return list(result.scalars().all()), int(total or 0)

    @classmethod
    async def list_items(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID | None,
        filters: Mapping[str, Any] | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[CBTResultIngestionItem], int]:
        conditions = []
        if tenant_id is not None:
            conditions.append(CBTResultIngestionItem.tenant_id == tenant_id)

        query = select(CBTResultIngestionItem).where(*conditions)
        count_query = select(func.count()).select_from(CBTResultIngestionItem).where(*conditions)
        query = cls._apply_filters(query, allowed_filters=cls._ITEM_FILTERS, filters=filters)
        count_query = cls._apply_filters(
            count_query,
            allowed_filters=cls._ITEM_FILTERS,
            filters=filters,
        )
        query = cls._apply_created_at_range(
            query,
            column=CBTResultIngestionItem.created_at,
            created_from=created_from,
            created_to=created_to,
        )
        count_query = cls._apply_created_at_range(
            count_query,
            column=CBTResultIngestionItem.created_at,
            created_from=created_from,
            created_to=created_to,
        )
        query = (
            query.order_by(
                CBTResultIngestionItem.created_at.desc(),
                CBTResultIngestionItem.id.desc(),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        total = await db.scalar(count_query)
        return list(result.scalars().all()), int(total or 0)

    @staticmethod
    async def get_batch_by_id(
        db: AsyncSession,
        *,
        batch_record_id: UUID,
        tenant_id: UUID | None,
    ) -> CBTResultIngestionBatch | None:
        query = select(CBTResultIngestionBatch).where(
            CBTResultIngestionBatch.id == batch_record_id
        )
        if tenant_id is not None:
            query = query.where(CBTResultIngestionBatch.tenant_id == tenant_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_client_batch_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        cbt_server_id: UUID,
        batch_id: UUID,
    ) -> CBTResultIngestionBatch | None:
        result = await db.execute(
            select(CBTResultIngestionBatch).where(
                CBTResultIngestionBatch.tenant_id == tenant_id,
                CBTResultIngestionBatch.cbt_server_id == cbt_server_id,
                CBTResultIngestionBatch.batch_id == batch_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_batch(
        db: AsyncSession,
        batch: CBTResultIngestionBatch,
    ) -> CBTResultIngestionBatch:
        db.add(batch)
        await db.flush()
        return batch

    @staticmethod
    async def add_items(
        db: AsyncSession,
        items: list[CBTResultIngestionItem],
    ) -> list[CBTResultIngestionItem]:
        if not items:
            return []
        db.add_all(items)
        await db.flush()
        return items

    @staticmethod
    async def save_batch(
        db: AsyncSession,
        batch: CBTResultIngestionBatch,
    ) -> CBTResultIngestionBatch:
        db.add(batch)
        await db.flush()
        return batch
