from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import NotFoundException
from app.modules.bulk_imports.models import ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.slip_schemas import StudentSlipPrintRequest
from app.modules.bulk_imports.slip_service import StudentSlipService


def _future_iso(hours: int = 4) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _row(
    row_number: int,
    *,
    first_name: str,
    last_name: str,
    admission_number: str,
    class_name: str,
    class_arm: str,
    setup_code: str = "12345678",
) -> dict:
    return {
        "row_number": row_number,
        "status": "created",
        "first_name": first_name,
        "last_name": last_name,
        "admission_number": admission_number,
        "class_name": class_name,
        "class_arm": class_arm,
        "setup_code": setup_code,
        "access_code_expires_at": _future_iso(),
    }


def _context(rows: list[dict]):
    now = datetime.now(timezone.utc)
    job = SimpleNamespace(
        id=uuid.uuid4(),
        resource_type=ImportResourceType.STUDENTS,
        status=ImportJobStatus.COMPLETED,
        metadata_json={"dry_run": False, "result_rows": rows},
        completed_at=now,
        updated_at=now,
    )
    tenant = SimpleNamespace(
        school_name="Bright Future Academy",
        logo_url=None,
    )
    actor = SimpleNamespace(tenant_id=uuid.uuid4())
    return job, tenant, actor


@pytest.mark.asyncio
async def test_summary_groups_classes_and_reports_printable_credentials() -> None:
    rows = [
        _row(
            2,
            first_name="Ada",
            last_name="Okafor",
            admission_number="BFA/001",
            class_name="JSS 1",
            class_arm="Blue",
        ),
        _row(
            3,
            first_name="Tobi",
            last_name="Adeleke",
            admission_number="BFA/002",
            class_name="JSS 1",
            class_arm="Blue",
        ),
        _row(
            4,
            first_name="Mary",
            last_name="James",
            admission_number="BFA/003",
            class_name="JSS 2",
            class_arm="",
        ),
    ]
    job, tenant, actor = _context(rows)

    with (
        patch(
            "app.modules.bulk_imports.slip_service.ImportJobRepository.get_job_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch(
            "app.modules.bulk_imports.slip_service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
    ):
        result = await StudentSlipService.summary(
            SimpleNamespace(),
            actor=actor,
            job_id=job.id,
        )

    assert result.total_slips == 3
    assert result.printable_slips == 3
    assert [(item.class_name, item.count) for item in result.classes] == [
        ("JSS 1 Blue", 2),
        ("JSS 2", 1),
    ]
    assert result.classes[0].class_key == "name:jss 1 blue"


@pytest.mark.asyncio
async def test_list_slips_filters_by_class_and_student_search() -> None:
    rows = [
        _row(
            2,
            first_name="Ada",
            last_name="Okafor",
            admission_number="BFA/001",
            class_name="JSS 1",
            class_arm="Blue",
        ),
        _row(
            3,
            first_name="Tobi",
            last_name="Adeleke",
            admission_number="BFA/002",
            class_name="JSS 2",
            class_arm="Red",
        ),
    ]
    job, tenant, actor = _context(rows)

    with (
        patch(
            "app.modules.bulk_imports.slip_service.ImportJobRepository.get_job_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch(
            "app.modules.bulk_imports.slip_service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
    ):
        result = await StudentSlipService.list_slips(
            SimpleNamespace(),
            actor=actor,
            job_id=job.id,
            search="ada",
            class_key="name:jss 1 blue",
            page=1,
            page_size=50,
        )

    assert result.total == 1
    assert result.items[0].full_name == "Ada Okafor"
    assert result.items[0].setup_code_available is True


@pytest.mark.asyncio
async def test_print_data_rejects_rows_outside_the_import_job() -> None:
    rows = [
        _row(
            2,
            first_name="Ada",
            last_name="Okafor",
            admission_number="BFA/001",
            class_name="JSS 1",
            class_arm="Blue",
        )
    ]
    job, tenant, actor = _context(rows)

    with (
        patch(
            "app.modules.bulk_imports.slip_service.ImportJobRepository.get_job_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch(
            "app.modules.bulk_imports.slip_service.TenantRepository.get_by_id",
            new=AsyncMock(return_value=tenant),
        ),
        pytest.raises(NotFoundException),
    ):
        await StudentSlipService.print_data(
            SimpleNamespace(),
            actor=actor,
            job_id=job.id,
            payload=StudentSlipPrintRequest(
                mode="selected",
                row_numbers=[2, 999],
            ),
        )
