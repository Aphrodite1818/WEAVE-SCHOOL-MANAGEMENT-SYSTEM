from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReportCardBulkScope(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    class_id: uuid.UUID
    academic_session_id: uuid.UUID
    academic_term_id: uuid.UUID


class ReportCardBulkPublishRequest(ReportCardBulkScope):
    confirmation: Literal["BULK_PUBLISH_REPORT_CARDS"]


class ReportCardBulkArchiveRequest(ReportCardBulkScope):
    confirmation: Literal["BULK_ARCHIVE_REPORT_CARDS"]
    reason: str = Field(min_length=3, max_length=1000)


class ReportCardBulkReopenRequest(ReportCardBulkScope):
    confirmation: Literal["BULK_REOPEN_REPORT_CARDS"]
    reason: str = Field(min_length=3, max_length=1000)


class BulkActionSkippedItem(BaseModel):
    id: uuid.UUID
    reason: str


class BulkActionResponse(BaseModel):
    matched: int
    processed: int
    skipped: list[BulkActionSkippedItem]
