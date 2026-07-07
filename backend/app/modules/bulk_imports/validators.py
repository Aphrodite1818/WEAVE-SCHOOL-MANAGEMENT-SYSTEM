# ============================= #
#   bulk_imports_validators.py  #
# ============================= #

"""Validation helpers for tenant bulk import rows."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.modules.bulk_imports.models import ImportResourceType


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class ImportValidationErrorItem:
    """One validation error found in an import row."""

    row_number: int
    field_name: str | None
    error_code: str
    error_message: str


@dataclass
class ImportRowValidationResult:
    """Validation result for one import row."""

    row_number: int
    raw_row: dict[str, Any]
    normalized_row: dict[str, Any]
    ignored_fields: list[str] = field(default_factory=list)
    errors: list[ImportValidationErrorItem] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True when this row has no validation errors."""

        return not self.errors


def _is_blank(value: Any) -> bool:
    """Return True if a field value is blank."""

    return value is None or str(value).strip() == ""


def _parse_date(value: Any) -> date | None:
    """Parse common date formats."""

    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    value_text = str(value).strip()

    if not value_text:
        return None

    accepted_formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
    )

    for date_format in accepted_formats:
        try:
            return datetime.strptime(value_text, date_format).date()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(value_text).date()
    except ValueError:
        return None


def _parse_uuid(value: Any) -> uuid.UUID | None:
    """Parse a UUID value."""

    if value is None:
        return None

    if isinstance(value, uuid.UUID):
        return value

    try:
        return uuid.UUID(str(value).strip())
    except (TypeError, ValueError):
        return None


def _add_error(
    *,
    errors: list[ImportValidationErrorItem],
    row_number: int,
    field_name: str | None,
    error_code: str,
    error_message: str,
) -> None:
    """Append one validation error."""

    errors.append(
        ImportValidationErrorItem(
            row_number=row_number,
            field_name=field_name,
            error_code=error_code,
            error_message=error_message,
        )
    )


class BulkImportValidator:
    """Validate normalized import rows against manual-create-compatible rules."""

    REQUIRED_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.STUDENTS: ("first_name", "last_name"),
        ImportResourceType.TEACHERS: ("email",),
        ImportResourceType.PARENTS: ("email",),
    }

    DUPLICATE_CHECK_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.TEACHERS: ("email", "staff_id"),
        ImportResourceType.PARENTS: ("email",),
    }

    @staticmethod
    def parse_date(value: Any) -> date | None:
        """Expose date parsing for service payload conversion."""

        return _parse_date(value)

    @staticmethod
    def parse_uuid(value: Any) -> uuid.UUID | None:
        """Expose UUID parsing for service payload conversion."""

        return _parse_uuid(value)

    @staticmethod
    def _validate_required_fields(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate required fields for a resource type."""

        required_fields = BulkImportValidator.REQUIRED_FIELDS_BY_RESOURCE.get(resource_type, ())

        for field_name in required_fields:
            if _is_blank(normalized_row.get(field_name)):
                _add_error(
                    errors=errors,
                    row_number=row_number,
                    field_name=field_name,
                    error_code="required",
                    error_message=f"{field_name} is required.",
                )

    @staticmethod
    def _validate_email(
        *,
        row_number: int,
        field_name: str,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate one email field."""

        value = normalized_row.get(field_name)

        if _is_blank(value):
            return

        if not EMAIL_PATTERN.match(str(value)):
            _add_error(
                errors=errors,
                row_number=row_number,
                field_name=field_name,
                error_code="invalid_email",
                error_message=f"{field_name} must be a valid email address.",
            )

    @staticmethod
    def _validate_student_fields(
        *,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate student-specific optional fields."""

        gender = normalized_row.get("gender")
        if not _is_blank(gender) and gender not in {"male", "female"}:
            _add_error(
                errors=errors,
                row_number=row_number,
                field_name="gender",
                error_code="invalid_gender",
                error_message="gender must be male or female.",
            )

        date_of_birth = normalized_row.get("date_of_birth")
        if not _is_blank(date_of_birth) and _parse_date(date_of_birth) is None:
            _add_error(
                errors=errors,
                row_number=row_number,
                field_name="date_of_birth",
                error_code="invalid_date",
                error_message="date_of_birth must be a valid date.",
            )

        class_id = normalized_row.get("class_id")
        if not _is_blank(class_id) and _parse_uuid(class_id) is None:
            _add_error(
                errors=errors,
                row_number=row_number,
                field_name="class_id",
                error_code="invalid_uuid",
                error_message="class_id must be a valid UUID.",
            )

    @staticmethod
    def _validate_teacher_fields(
        *,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate teacher-specific fields."""

        BulkImportValidator._validate_email(
            row_number=row_number,
            field_name="email",
            normalized_row=normalized_row,
            errors=errors,
        )

    @staticmethod
    def _validate_parent_fields(
        *,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate parent-specific fields."""

        BulkImportValidator._validate_email(
            row_number=row_number,
            field_name="email",
            normalized_row=normalized_row,
            errors=errors,
        )

    @staticmethod
    def _validate_duplicates_within_file(
        *,
        resource_type: ImportResourceType,
        validation_results: list[ImportRowValidationResult],
    ) -> None:
        """Validate duplicate identifiers within the uploaded file."""

        duplicate_fields = BulkImportValidator.DUPLICATE_CHECK_FIELDS_BY_RESOURCE.get(
            resource_type,
            (),
        )

        for field_name in duplicate_fields:
            seen_values: dict[str, int] = {}

            for validation_result in validation_results:
                value = validation_result.normalized_row.get(field_name)

                if _is_blank(value):
                    continue

                normalized_value = str(value).strip().lower()

                if normalized_value in seen_values:
                    _add_error(
                        errors=validation_result.errors,
                        row_number=validation_result.row_number,
                        field_name=field_name,
                        error_code="duplicate_in_file",
                        error_message=(
                            f"{field_name} duplicates row "
                            f"{seen_values[normalized_value]} in this file."
                        ),
                    )
                    continue

                seen_values[normalized_value] = validation_result.row_number

    @staticmethod
    def validate_row(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        raw_row: dict[str, Any],
        normalized_row: dict[str, Any],
        ignored_fields: list[str],
    ) -> ImportRowValidationResult:
        """Validate one normalized import row."""

        validation_result = ImportRowValidationResult(
            row_number=row_number,
            raw_row=raw_row,
            normalized_row=normalized_row,
            ignored_fields=ignored_fields,
        )

        BulkImportValidator._validate_required_fields(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        if resource_type == ImportResourceType.STUDENTS:
            BulkImportValidator._validate_student_fields(
                row_number=row_number,
                normalized_row=normalized_row,
                errors=validation_result.errors,
            )
        elif resource_type == ImportResourceType.TEACHERS:
            BulkImportValidator._validate_teacher_fields(
                row_number=row_number,
                normalized_row=normalized_row,
                errors=validation_result.errors,
            )
        elif resource_type == ImportResourceType.PARENTS:
            BulkImportValidator._validate_parent_fields(
                row_number=row_number,
                normalized_row=normalized_row,
                errors=validation_result.errors,
            )
        else:
            _add_error(
                errors=validation_result.errors,
                row_number=row_number,
                field_name=None,
                error_code="unsupported_resource_type",
                error_message=f"{resource_type.value} bulk import is not supported yet.",
            )

        return validation_result

    @staticmethod
    def validate_rows(
        *,
        resource_type: ImportResourceType,
        row_items: list[tuple[int, dict[str, Any], dict[str, Any], list[str]]],
    ) -> list[ImportRowValidationResult]:
        """Validate multiple normalized rows and check duplicates within the file."""

        validation_results = [
            BulkImportValidator.validate_row(
                resource_type=resource_type,
                row_number=row_number,
                raw_row=raw_row,
                normalized_row=normalized_row,
                ignored_fields=ignored_fields,
            )
            for row_number, raw_row, normalized_row, ignored_fields in row_items
        ]

        BulkImportValidator._validate_duplicates_within_file(
            resource_type=resource_type,
            validation_results=validation_results,
        )

        return validation_results
