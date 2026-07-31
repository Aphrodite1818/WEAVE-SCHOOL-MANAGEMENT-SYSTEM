"""Schemas for the tenant-admin bulk-import student slip workspace."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.modules.bulk_imports.schemas import InputBase, OutputBase


class StudentSlipClassSummary(OutputBase):
    class_key: str
    class_id: uuid.UUID | None = None
    class_name: str
    count: int = Field(ge=0)


class StudentSlipSummaryResponse(OutputBase):
    job_id: uuid.UUID
    school_name: str
    school_logo_url: str | None = None
    login_url: str
    total_slips: int = Field(ge=0)
    printable_slips: int = Field(ge=0)
    unavailable_slips: int = Field(ge=0)
    classes: list[StudentSlipClassSummary] = Field(default_factory=list)
    completed_at: datetime | None = None
    credentials_available_until: datetime | None = None


class StudentSlipListItem(OutputBase):
    row_number: int = Field(ge=1)
    student_id: uuid.UUID | None = None
    full_name: str
    admission_number: str
    class_key: str
    class_id: uuid.UUID | None = None
    class_name: str
    setup_code_available: bool
    access_code_expires_at: datetime | None = None
    credentials_available_until: datetime | None = None


class StudentSlipListResponse(OutputBase):
    items: list[StudentSlipListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total_pages: int = Field(ge=0)


class StudentSlipDetailResponse(StudentSlipListItem):
    setup_code: str
    school_name: str
    school_logo_url: str | None = None
    login_url: str
    generated_at: datetime


class StudentSlipPrintRequest(InputBase):
    mode: Literal["selected", "filtered", "all"]
    row_numbers: list[int] = Field(default_factory=list, max_length=5000)
    search: str | None = Field(default=None, max_length=160)
    class_key: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_scope(self) -> "StudentSlipPrintRequest":
        if self.mode == "selected" and not self.row_numbers:
            raise ValueError("row_numbers are required when mode is selected")
        if self.mode != "selected" and self.row_numbers:
            raise ValueError("row_numbers are only allowed when mode is selected")
        if len(set(self.row_numbers)) != len(self.row_numbers):
            raise ValueError("row_numbers must not contain duplicates")
        if any(row_number < 1 for row_number in self.row_numbers):
            raise ValueError("row_numbers must contain positive values")
        return self


class StudentSlipPrintResponse(OutputBase):
    job_id: uuid.UUID
    school_name: str
    school_logo_url: str | None = None
    login_url: str
    items: list[StudentSlipDetailResponse]
    total: int = Field(ge=0)
    unavailable_row_numbers: list[int] = Field(default_factory=list)
