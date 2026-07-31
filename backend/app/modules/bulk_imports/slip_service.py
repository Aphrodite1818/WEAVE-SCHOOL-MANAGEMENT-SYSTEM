"""Tenant-scoped student access slip queries for completed bulk imports."""

from __future__ import annotations

import math
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.bulk_imports.models import ImportJob, ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.repository import ImportJobRepository
from app.modules.bulk_imports.sensitive_results import (
    SETUP_CODE_AVAILABLE_UNTIL_FIELD,
    redact_result_row,
    reveal_result_row,
)
from app.modules.bulk_imports.slip_schemas import (
    StudentSlipClassSummary,
    StudentSlipDetailResponse,
    StudentSlipListItem,
    StudentSlipListResponse,
    StudentSlipPrintRequest,
    StudentSlipPrintResponse,
    StudentSlipSummaryResponse,
)
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.models import Tenant
from app.tenant_management.repository import TenantRepository


_ALLOWED_JOB_STATUSES = {
    ImportJobStatus.COMPLETED,
    ImportJobStatus.PARTIALLY_COMPLETED,
}


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value in {None, ""}:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _normalize_search(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def _full_name(row: dict[str, Any]) -> str:
    name = " ".join(
        part
        for part in (
            str(row.get("first_name") or "").strip(),
            str(row.get("last_name") or "").strip(),
        )
        if part
    )
    return name or "Student"


def _class_name(row: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in (
            str(row.get("class_name") or "").strip(),
            str(row.get("class_arm") or "").strip(),
        )
        if part
    ) or "Unassigned"


class StudentSlipService:
    """Serve searchable and printable slips from encrypted import results."""

    @staticmethod
    async def _load_context(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: uuid.UUID,
    ) -> tuple[ImportJob, Tenant, list[dict[str, Any]]]:
        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")
        if import_job.resource_type != ImportResourceType.STUDENTS:
            raise BadRequestException(detail="Student slips are only available for student imports.")
        if import_job.status not in _ALLOWED_JOB_STATUSES:
            raise ConflictException(detail="Student slips are available only after import processing finishes.")

        metadata = dict(import_job.metadata_json or {})
        if metadata.get("dry_run"):
            raise ConflictException(detail="Complete the real import before viewing student slips.")

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=actor.tenant_id)
        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        rows = [
            row
            for row in list(metadata.get("result_rows") or [])
            if isinstance(row, dict) and str(row.get("status") or "").lower() == "created"
        ]
        rows.sort(key=lambda row: int(row.get("row_number") or 0))
        return import_job, tenant, rows

    @staticmethod
    def _matches(
        row: dict[str, Any],
        *,
        search: str | None,
        class_id: uuid.UUID | None,
    ) -> bool:
        if class_id is not None and _parse_uuid(row.get("class_id")) != class_id:
            return False
        query = _normalize_search(search)
        if not query:
            return True
        haystack = _normalize_search(
            " ".join(
                (
                    _full_name(row),
                    str(row.get("admission_number") or ""),
                    _class_name(row),
                )
            )
        )
        return query in haystack

    @staticmethod
    def _list_item(row: dict[str, Any]) -> StudentSlipListItem:
        redacted = redact_result_row(row)
        return StudentSlipListItem(
            row_number=int(row.get("row_number") or 0),
            student_id=_parse_uuid(row.get("student_id")),
            full_name=_full_name(row),
            admission_number=str(row.get("admission_number") or "--"),
            class_id=_parse_uuid(row.get("class_id")),
            class_name=_class_name(row),
            setup_code_available=bool(redacted.get("setup_code_available")),
            access_code_expires_at=_parse_datetime(row.get("access_code_expires_at")),
            credentials_available_until=_parse_datetime(
                row.get(SETUP_CODE_AVAILABLE_UNTIL_FIELD)
            ),
        )

    @staticmethod
    def _detail(
        row: dict[str, Any],
        *,
        import_job: ImportJob,
        tenant: Tenant,
    ) -> StudentSlipDetailResponse | None:
        revealed = reveal_result_row(row)
        setup_code = str(revealed.get("setup_code") or "").strip()
        if not setup_code:
            return None
        item = StudentSlipService._list_item(row)
        return StudentSlipDetailResponse(
            **item.model_dump(),
            setup_code=setup_code,
            school_name=tenant.school_name,
            school_logo_url=tenant.logo_url,
            login_url=f"{str(settings.FRONTEND_APP_URL).rstrip('/')}/login",
            generated_at=import_job.completed_at or import_job.updated_at,
        )

    @staticmethod
    async def summary(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: uuid.UUID,
    ) -> StudentSlipSummaryResponse:
        import_job, tenant, rows = await StudentSlipService._load_context(
            db,
            actor=actor,
            job_id=job_id,
        )
        class_counts: dict[tuple[uuid.UUID | None, str], int] = {}
        printable = 0
        available_until_values: list[datetime] = []
        for row in rows:
            item = StudentSlipService._list_item(row)
            class_key = (item.class_id, item.class_name)
            class_counts[class_key] = class_counts.get(class_key, 0) + 1
            if item.setup_code_available:
                printable += 1
            if item.credentials_available_until is not None:
                available_until_values.append(item.credentials_available_until)

        classes = [
            StudentSlipClassSummary(
                class_id=class_id,
                class_name=class_name,
                count=count,
            )
            for (class_id, class_name), count in sorted(
                class_counts.items(),
                key=lambda item: item[0][1].casefold(),
            )
        ]
        return StudentSlipSummaryResponse(
            job_id=import_job.id,
            school_name=tenant.school_name,
            school_logo_url=tenant.logo_url,
            login_url=f"{str(settings.FRONTEND_APP_URL).rstrip('/')}/login",
            total_slips=len(rows),
            printable_slips=printable,
            unavailable_slips=len(rows) - printable,
            classes=classes,
            completed_at=import_job.completed_at,
            credentials_available_until=(
                max(available_until_values) if available_until_values else None
            ),
        )

    @staticmethod
    async def list_slips(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: uuid.UUID,
        search: str | None,
        class_id: uuid.UUID | None,
        page: int,
        page_size: int,
    ) -> StudentSlipListResponse:
        _, _, rows = await StudentSlipService._load_context(
            db,
            actor=actor,
            job_id=job_id,
        )
        filtered = [
            row
            for row in rows
            if StudentSlipService._matches(row, search=search, class_id=class_id)
        ]
        start = (page - 1) * page_size
        page_rows = filtered[start : start + page_size]
        return StudentSlipListResponse(
            items=[StudentSlipService._list_item(row) for row in page_rows],
            total=len(filtered),
            page=page,
            page_size=page_size,
            total_pages=math.ceil(len(filtered) / page_size) if filtered else 0,
        )

    @staticmethod
    async def get_slip(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: uuid.UUID,
        row_number: int,
    ) -> StudentSlipDetailResponse:
        import_job, tenant, rows = await StudentSlipService._load_context(
            db,
            actor=actor,
            job_id=job_id,
        )
        row = next(
            (item for item in rows if int(item.get("row_number") or 0) == row_number),
            None,
        )
        if row is None:
            raise NotFoundException(detail="Student slip not found in this import job.")
        detail = StudentSlipService._detail(
            row,
            import_job=import_job,
            tenant=tenant,
        )
        if detail is None:
            raise ConflictException(
                detail="This temporary setup code is no longer available. Generate a new student access code before printing another slip."
            )
        return detail

    @staticmethod
    async def print_data(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: uuid.UUID,
        payload: StudentSlipPrintRequest,
    ) -> StudentSlipPrintResponse:
        import_job, tenant, rows = await StudentSlipService._load_context(
            db,
            actor=actor,
            job_id=job_id,
        )

        if payload.mode == "selected":
            selected = set(payload.row_numbers)
            scoped_rows = [
                row
                for row in rows
                if int(row.get("row_number") or 0) in selected
            ]
            found = {int(row.get("row_number") or 0) for row in scoped_rows}
            missing = sorted(selected - found)
            if missing:
                raise NotFoundException(
                    detail="One or more selected slips do not belong to this import job."
                )
        elif payload.mode == "filtered":
            scoped_rows = [
                row
                for row in rows
                if StudentSlipService._matches(
                    row,
                    search=payload.search,
                    class_id=payload.class_id,
                )
            ]
        else:
            scoped_rows = rows

        details: list[StudentSlipDetailResponse] = []
        unavailable: list[int] = []
        for row in scoped_rows:
            detail = StudentSlipService._detail(
                row,
                import_job=import_job,
                tenant=tenant,
            )
            if detail is None:
                unavailable.append(int(row.get("row_number") or 0))
                continue
            details.append(detail)

        if not details:
            raise ConflictException(
                detail="None of the selected student setup codes are still available for printing."
            )

        return StudentSlipPrintResponse(
            job_id=import_job.id,
            school_name=tenant.school_name,
            school_logo_url=tenant.logo_url,
            login_url=f"{str(settings.FRONTEND_APP_URL).rstrip('/')}/login",
            items=details,
            total=len(details),
            unavailable_row_numbers=unavailable,
        )
