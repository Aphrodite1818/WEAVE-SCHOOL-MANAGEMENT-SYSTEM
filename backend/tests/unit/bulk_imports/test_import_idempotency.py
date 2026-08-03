from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import BadRequestException
from app.modules.bulk_imports.models import ImportJob, ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.repository import ImportJobRepository
from app.modules.bulk_imports.service import BulkImportService, build_import_source_fingerprint


def test_import_source_fingerprint_is_stable_when_rows_are_reordered() -> None:
    first = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[
            (2, {"first_name": "Ada", "last_name": "Okafor", "class_id": "class-1"}),
            (3, {"first_name": "Tunde", "last_name": "Bello", "class_id": "class-2"}),
        ],
    )
    second = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[
            (2, {"first_name": "Tunde", "last_name": "Bello", "class_id": "class-2"}),
            (3, {"first_name": "Ada", "last_name": "Okafor", "class_id": "class-1"}),
        ],
    )
    assert first == second
    assert len(first) == 64


def test_import_source_fingerprint_preserves_duplicate_row_multiplicity() -> None:
    one_row = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Okafor"})],
    )
    duplicated_row = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[
            (2, {"first_name": "Ada", "last_name": "Okafor"}),
            (3, {"first_name": "Ada", "last_name": "Okafor"}),
        ],
    )
    assert one_row != duplicated_row


def test_import_source_fingerprint_changes_when_student_data_changes() -> None:
    original = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Okafor"})],
    )
    changed = build_import_source_fingerprint(
        resource_type=ImportResourceType.STUDENTS,
        template_version="student-v1",
        rows=[(2, {"first_name": "Ada", "last_name": "Bello"})],
    )
    assert original != changed


def test_confirmed_fingerprint_has_unique_tenant_resource_index() -> None:
    index = next(
        item
        for item in ImportJob.__table__.indexes
        if item.name == "uq_import_jobs_tenant_confirmed_fingerprint"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == [
        "tenant_id",
        "resource_type",
        "confirmed_fingerprint",
    ]


@pytest.mark.asyncio
async def test_confirmed_import_history_cannot_be_deleted(monkeypatch) -> None:
    import_job = SimpleNamespace(
        status=ImportJobStatus.COMPLETED,
        confirmed_fingerprint="a" * 64,
    )
    delete_job = AsyncMock()
    monkeypatch.setattr(
        ImportJobRepository,
        "get_job_by_id",
        AsyncMock(return_value=import_job),
    )
    monkeypatch.setattr(ImportJobRepository, "delete_job", delete_job)

    db = SimpleNamespace(commit=AsyncMock())
    actor = SimpleNamespace(tenant_id=uuid4())

    with pytest.raises(BadRequestException) as exc_info:
        await BulkImportService.delete_job_history(
            db=db,
            actor=actor,
            job_id=uuid4(),
        )

    assert "cannot be deleted" in str(exc_info.value.detail)
    delete_job.assert_not_awaited()
    db.commit.assert_not_awaited()
