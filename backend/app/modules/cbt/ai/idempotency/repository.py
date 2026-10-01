"""Persistence helpers for CBT AI idempotency metadata."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.ai.idempotency.models import AIIdempotencyRecord


class AIIdempotencyRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        record: AIIdempotencyRecord,
    ) -> AIIdempotencyRecord:
        db.add(record)
        await db.flush()
        return record

    @staticmethod
    async def save(
        db: AsyncSession,
        record: AIIdempotencyRecord,
    ) -> AIIdempotencyRecord:
        db.add(record)
        await db.flush()
        return record

    @staticmethod
    async def get_by_scope(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        actor_type: str,
        actor_id: UUID,
        operation: str,
        idempotency_key: str,
        lock: bool = False,
    ) -> AIIdempotencyRecord | None:
        query = select(AIIdempotencyRecord).where(
            AIIdempotencyRecord.tenant_id == tenant_id,
            AIIdempotencyRecord.actor_type == actor_type,
            AIIdempotencyRecord.actor_id == actor_id,
            AIIdempotencyRecord.operation == operation,
            AIIdempotencyRecord.idempotency_key == idempotency_key,
        )
        if lock:
            query = query.with_for_update(of=AIIdempotencyRecord)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        record_id: UUID,
        lock: bool = False,
    ) -> AIIdempotencyRecord | None:
        query = select(AIIdempotencyRecord).where(
            AIIdempotencyRecord.tenant_id == tenant_id,
            AIIdempotencyRecord.id == record_id,
        )
        if lock:
            query = query.with_for_update(of=AIIdempotencyRecord)
        return (await db.execute(query)).scalar_one_or_none()
