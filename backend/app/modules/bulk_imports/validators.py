#==============================#
# bulk_imports_validators.py   #
#==============================#



"""Validation helpers for tenant bulk import rows"""


from __future__ import annotations 

import re
from dataclasses import dataclass , field
from datetime import datetime 

from app.modules.bulk_imports.models import ImportResourceType
from typing import Any

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")



@dataclass(frozen = True)
class ImportValidationErrorItem:
    """One validation error found in an import row"""

    row_number : int 
    field_name : str | None
    error_code : str 
    error_message : str





@dataclass
class ImportRowValidationResult:
    """Validation result for one import row"""

    row_number : int
    normalized_row : dict[str , Any]
    errors : list[ImportValidationErrorItem] = field(default_factory = list)


    @property
    def is_valid(self) -> bool:
        """Return True when this row has no validation errors"""

        return not self.errors
    


class BulkImportValidator:
    """Validate normalized import rows before service-level creation."""

    REQUIRED_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.STUDENTS: (
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "class_name",
            "arm",
        ),
        ImportResourceType.TEACHERS: (
            "first_name",
            "last_name",
            "email",
        ),
        ImportResourceType.PARENTS: (
            "first_name",
            "last_name",
            "email",
        ),
        ImportResourceType.CLASSES: (
            "name",
            "level",
            "arm",
        ),
        ImportResourceType.SUBJECTS: (
            "name",
        ),
        ImportResourceType.CLASS_SUBJECTS: (
            "class_name",
            "arm",
            "subject_name",
        ),
        ImportResourceType.TEACHER_SUBJECTS: (
            "teacher_email",
            "subject_name",
        ),
        ImportResourceType.ASSESSMENT_RECORDS: (
            "admission_number",
            "subject_name",
            "assessment_name",
            "score",
            "max_score",
        ),
    }

    EMAIL_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.TEACHERS: ("email",),
        ImportResourceType.PARENTS: ("email",),
        ImportResourceType.TEACHER_SUBJECTS: ("teacher_email",),
    }

    DATE_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.STUDENTS: ("date_of_birth",),
    }

    NUMERIC_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.ASSESSMENT_RECORDS: ("score", "max_score"),
    }

    DUPLICATE_CHECK_FIELDS_BY_RESOURCE: dict[ImportResourceType, tuple[str, ...]] = {
        ImportResourceType.STUDENTS: ("admission_number",),
        ImportResourceType.TEACHERS: ("email",),
        ImportResourceType.PARENTS: ("email",),
        ImportResourceType.SUBJECTS: ("code",),
    }

    @staticmethod
    def _is_blank(value: Any) -> bool:
        """Return True if a field value is blank."""

        return value is None or str(value).strip() == ""

    @staticmethod
    def is_number(value: Any) -> bool:
        """Return True if a value can be converted to a number."""

        if value is None:
            return False

        try:
            float(value)
        except (TypeError, ValueError):
            return False

        return True

    @staticmethod
    def parse_date(value: Any) -> datetime | None:
        """Parse common date formats.

        Returns None when the value cannot be parsed.
        """

        if value is None:
            return None

        if isinstance(value, datetime):
            return value

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
                return datetime.strptime(value_text, date_format)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(value_text)
        except ValueError:
            return None

    @staticmethod
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

    @staticmethod
    def _validate_required_fields(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate required fields for a resource type."""

        required_fields = BulkImportValidator.REQUIRED_FIELDS_BY_RESOURCE.get(
            resource_type,
            (),
        )

        for field_name in required_fields:
            if BulkImportValidator._is_blank(normalized_row.get(field_name)):
                BulkImportValidator._add_error(
                    errors=errors,
                    row_number=row_number,
                    field_name=field_name,
                    error_code="required",
                    error_message=f"{field_name} is required.",
                )

    @staticmethod
    def _validate_email_fields(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate email fields."""

        email_fields = BulkImportValidator.EMAIL_FIELDS_BY_RESOURCE.get(
            resource_type,
            (),
        )

        for field_name in email_fields:
            value = normalized_row.get(field_name)

            if BulkImportValidator._is_blank(value):
                continue

            if not EMAIL_PATTERN.match(str(value)):
                BulkImportValidator._add_error(
                    errors=errors,
                    row_number=row_number,
                    field_name=field_name,
                    error_code="invalid_email",
                    error_message=f"{field_name} must be a valid email address.",
                )

    @staticmethod
    def _validate_gender_field(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate gender value where present."""

        if resource_type not in {
            ImportResourceType.STUDENTS,
            ImportResourceType.TEACHERS,
        }:
            return

        gender = normalized_row.get("gender")

        if BulkImportValidator._is_blank(gender):
            return

        if gender not in {"male", "female"}:
            BulkImportValidator._add_error(
                errors=errors,
                row_number=row_number,
                field_name="gender",
                error_code="invalid_gender",
                error_message="gender must be male or female.",
            )

    @staticmethod
    def _validate_date_fields(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate date-like fields."""

        date_fields = BulkImportValidator.DATE_FIELDS_BY_RESOURCE.get(
            resource_type,
            (),
        )

        for field_name in date_fields:
            value = normalized_row.get(field_name)

            if BulkImportValidator._is_blank(value):
                continue

            if BulkImportValidator.parse_date(value) is None:
                BulkImportValidator._add_error(
                    errors=errors,
                    row_number=row_number,
                    field_name=field_name,
                    error_code="invalid_date",
                    error_message=f"{field_name} must be a valid date.",
                )

    @staticmethod
    def _validate_numeric_fields(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate numeric fields."""

        numeric_fields = BulkImportValidator.NUMERIC_FIELDS_BY_RESOURCE.get(
            resource_type,
            (),
        )

        for field_name in numeric_fields:
            value = normalized_row.get(field_name)

            if BulkImportValidator._is_blank(value):
                continue

            if not BulkImportValidator.is_number(value):
                BulkImportValidator._add_error(
                    errors=errors,
                    row_number=row_number,
                    field_name=field_name,
                    error_code="invalid_number",
                    error_message=f"{field_name} must be a valid number.",
                )

    @staticmethod
    def _validate_assessment_scores(
        *,
        resource_type: ImportResourceType,
        row_number: int,
        normalized_row: dict[str, Any],
        errors: list[ImportValidationErrorItem],
    ) -> None:
        """Validate assessment score boundaries."""

        if resource_type != ImportResourceType.ASSESSMENT_RECORDS:
            return

        score = normalized_row.get("score")
        max_score = normalized_row.get("max_score")

        if not BulkImportValidator.is_number(score):
            return

        if not BulkImportValidator.is_number(max_score):
            return

        score_value = float(score)
        max_score_value = float(max_score)

        if max_score_value <= 0:
            BulkImportValidator._add_error(
                errors=errors,
                row_number=row_number,
                field_name="max_score",
                error_code="invalid_max_score",
                error_message="max_score must be greater than zero.",
            )
            return

        if score_value < 0:
            BulkImportValidator._add_error(
                errors=errors,
                row_number=row_number,
                field_name="score",
                error_code="invalid_score",
                error_message="score cannot be less than zero.",
            )

        if score_value > max_score_value:
            BulkImportValidator._add_error(
                errors=errors,
                row_number=row_number,
                field_name="score",
                error_code="score_exceeds_max_score",
                error_message="score cannot be greater than max_score.",
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

                if BulkImportValidator._is_blank(value):
                    continue

                normalized_value = str(value).strip().lower()

                if normalized_value in seen_values:
                    BulkImportValidator._add_error(
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
        normalized_row: dict[str, Any],
    ) -> ImportRowValidationResult:
        """Validate one normalized import row."""

        validation_result = ImportRowValidationResult(
            row_number=row_number,
            normalized_row=normalized_row,
        )

        BulkImportValidator._validate_required_fields(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        BulkImportValidator._validate_email_fields(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        BulkImportValidator._validate_gender_field(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        BulkImportValidator._validate_date_fields(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        BulkImportValidator._validate_numeric_fields(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        BulkImportValidator._validate_assessment_scores(
            resource_type=resource_type,
            row_number=row_number,
            normalized_row=normalized_row,
            errors=validation_result.errors,
        )

        return validation_result

    @staticmethod
    def validate_rows(
        *,
        resource_type: ImportResourceType,
        row_items: list[tuple[int, dict[str, Any]]],
    ) -> list[ImportRowValidationResult]:
        """Validate multiple normalized rows and check duplicates within the file."""

        validation_results = [
            BulkImportValidator.validate_row(
                resource_type=resource_type,
                row_number=row_number,
                normalized_row=normalized_row,
            )
            for row_number, normalized_row in row_items
        ]

        BulkImportValidator._validate_duplicates_within_file(
            resource_type=resource_type,
            validation_results=validation_results,
        )

        return validation_results

