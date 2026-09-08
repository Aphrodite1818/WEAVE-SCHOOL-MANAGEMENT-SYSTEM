from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.cbt.results.audit_service import (
    CBTResultIngestionAuditService,
    _exam_display_label,
)


def test_exam_display_label_uses_human_academic_context() -> None:
    assert _exam_display_label(
        subject_name="Mathematics",
        component_name="Examination",
        level_name="SS2",
        term_name="first_term",
        exam_date=date(2026, 9, 8),
    ) == "Mathematics · Examination · SS2 · First Term · 08 Sep 2026"


@pytest.mark.asyncio
async def test_admin_batch_list_is_tenant_scoped() -> None:
    tenant_id = uuid4()
    db = AsyncMock()

    with patch(
        "app.modules.cbt.results.audit_service.CBTResultIngestionRepository.list_batches",
        new=AsyncMock(return_value=([], 0)),
    ) as list_batches:
        await CBTResultIngestionAuditService.list_batches_for_admin(
            db,
            tenant_id=tenant_id,
            filters={"source_exam_id": uuid4()},
        )

    assert list_batches.await_args.kwargs["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_admin_filter_options_are_tenant_scoped() -> None:
    tenant_id = uuid4()
    db = AsyncMock()

    with patch.object(
        CBTResultIngestionAuditService,
        "_filter_options",
        new=AsyncMock(return_value=object()),
    ) as filter_options:
        await CBTResultIngestionAuditService.get_filter_options_for_admin(
            db,
            tenant_id=tenant_id,
        )

    assert filter_options.await_args.kwargs["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_superadmin_filter_options_require_explicit_tenant_scope() -> None:
    tenant_id = uuid4()
    db = AsyncMock()

    with patch.object(
        CBTResultIngestionAuditService,
        "_filter_options",
        new=AsyncMock(return_value=object()),
    ) as filter_options:
        await CBTResultIngestionAuditService.get_filter_options_for_superadmin(
            db,
            tenant_id=tenant_id,
        )

    assert filter_options.await_args.kwargs["tenant_id"] == tenant_id


@pytest.mark.asyncio
async def test_admin_item_list_forces_requested_batch_scope() -> None:
    tenant_id = uuid4()
    batch_record_id = uuid4()
    db = AsyncMock()

    with (
        patch.object(
            CBTResultIngestionAuditService,
            "get_batch_for_admin",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "app.modules.cbt.results.audit_service.CBTResultIngestionRepository.list_items",
            new=AsyncMock(return_value=([], 0)),
        ) as list_items,
    ):
        await CBTResultIngestionAuditService.list_batch_items_for_admin(
            db,
            tenant_id=tenant_id,
            batch_record_id=batch_record_id,
            filters={"ingestion_batch_id": uuid4()},
        )

    assert list_items.await_args.kwargs["tenant_id"] == tenant_id
    assert list_items.await_args.kwargs["filters"]["ingestion_batch_id"] == batch_record_id


def test_audit_service_rejects_reversed_date_range() -> None:
    with pytest.raises(BadRequestException):
        CBTResultIngestionAuditService._validate_date_range(
            datetime(2026, 9, 9, tzinfo=timezone.utc),
            datetime(2026, 9, 8, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_admin_cannot_fetch_missing_or_cross_tenant_batch() -> None:
    db = AsyncMock()

    with patch(
        "app.modules.cbt.results.audit_service.CBTResultIngestionRepository.get_batch_by_id",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(NotFoundException):
            await CBTResultIngestionAuditService.get_batch_for_admin(
                db,
                tenant_id=uuid4(),
                batch_record_id=uuid4(),
            )
