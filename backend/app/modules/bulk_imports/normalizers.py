# ============================= #
#   bulk_imports_normalizers.py #
# ============================= #

"""Row normalization helpers for tenant bulk imports."""

from __future__ import annotations

import re
from typing import Any

from app.core.utils.normalization import normalize_class_arm, normalize_class_name
from app.modules.bulk_imports.models import ImportResourceType


SUPPORTED_IMPORT_RESOURCE_TYPES = {
    ImportResourceType.STUDENTS,
}


class BulkImportNormalizer:
    """Normalize parsed import rows into manual-create-compatible field names."""

    FIELD_ALIASES_BY_RESOURCE: dict[ImportResourceType, dict[str, str]] = {
        ImportResourceType.STUDENTS: {
            "first_name": "first_name",
            "firstname": "first_name",
            "first": "first_name",
            "last_name": "last_name",
            "lastname": "last_name",
            "last": "last_name",
            "date_of_birth": "date_of_birth",
            "dob": "date_of_birth",
            "gender": "gender",
            "sex": "gender",
            "class_name": "class_name",
            "class": "class_name",
            "class_arm": "class_arm",
            "arm": "class_arm",
            "state": "state_of_origin",
            "state_of_origin": "state_of_origin",
            "parent_email_1": "parent_email_1",
            "parent_1_email": "parent_email_1",
            "guardian_email_1": "parent_email_1",
            "parent_relationship_1": "parent_relationship_1",
            "parent_1_relationship": "parent_relationship_1",
            "guardian_relationship_1": "parent_relationship_1",
            "parent_email_2": "parent_email_2",
            "parent_2_email": "parent_email_2",
            "guardian_email_2": "parent_email_2",
            "parent_relationship_2": "parent_relationship_2",
            "parent_2_relationship": "parent_relationship_2",
            "guardian_relationship_2": "parent_relationship_2",
        },
    }

    ALLOWED_FIELDS_BY_RESOURCE: dict[ImportResourceType, set[str]] = {
        ImportResourceType.STUDENTS: {
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "class_name",
            "class_arm",
            "state_of_origin",
            "parent_email_1",
            "parent_relationship_1",
            "parent_email_2",
            "parent_relationship_2",
        },
    }

    @staticmethod
    def normalize_key(key: Any) -> str:
        """Normalize a column name for alias matching."""

        if key is None:
            return ""

        normalized_key = str(key).strip().lower()
        normalized_key = re.sub(r"[\s\-]+", "_", normalized_key)
        normalized_key = re.sub(r"[^a-z0-9_]", "", normalized_key)
        return normalized_key

    @staticmethod
    def normalize_email(value: Any) -> str | None:
        """Normalize an email value."""

        if value is None:
            return None

        email = str(value).strip().lower()
        return email or None

    @staticmethod
    def normalize_phone(value: Any) -> str | None:
        """Normalize a phone number without enforcing country-specific formatting."""

        if value is None:
            return None

        phone = str(value).strip()
        phone = re.sub(r"\s+", "", phone)
        return phone or None

    @staticmethod
    def normalize_gender(value: Any) -> str | None:
        """Normalize common gender inputs to model-compatible values."""

        if value is None:
            return None

        gender = str(value).strip().lower()

        if gender in {"m", "male", "boy"}:
            return "male"

        if gender in {"f", "female", "girl"}:
            return "female"

        return gender or None

    @staticmethod
    def normalize_text(value: Any) -> str | None:
        """Normalize a human-readable text field."""

        if value is None:
            return None

        value_text = str(value).strip()
        return " ".join(value_text.split()) or None

    @staticmethod
    def normalize_value(
        *,
        field_name: str,
        value: Any,
    ) -> Any:
        """Normalize a field value based on its canonical field name."""

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

        if field_name in {"email", "parent_email_1", "parent_email_2"}:
            return BulkImportNormalizer.normalize_email(value)

        if field_name in {"parent_relationship_1", "parent_relationship_2"}:
            return BulkImportNormalizer.normalize_key(value)

        if field_name in {"phone_number", "emergency_phone"}:
            return BulkImportNormalizer.normalize_phone(value)

        if field_name == "gender":
            return BulkImportNormalizer.normalize_gender(value)

        if field_name == "class_name":
            return normalize_class_name(value)

        if field_name == "class_arm":
            return normalize_class_arm(value)

        return BulkImportNormalizer.normalize_text(value)

    @staticmethod
    def normalize_row(
        *,
        resource_type: ImportResourceType,
        raw_row: dict[str, Any],
    ) -> tuple[dict[str, Any], list[str]]:
        """Normalize one row and return ignored unsupported fields."""

        field_aliases = BulkImportNormalizer.FIELD_ALIASES_BY_RESOURCE.get(resource_type, {})
        allowed_fields = BulkImportNormalizer.ALLOWED_FIELDS_BY_RESOURCE.get(resource_type, set())

        normalized_row: dict[str, Any] = {}
        ignored_fields: list[str] = []

        for raw_field_name, raw_value in raw_row.items():
            normalized_field_name = BulkImportNormalizer.normalize_key(raw_field_name)
            canonical_field_name = field_aliases.get(normalized_field_name)

            if canonical_field_name is None or canonical_field_name not in allowed_fields:
                ignored_fields.append(str(raw_field_name))
                continue

            normalized_row[canonical_field_name] = BulkImportNormalizer.normalize_value(
                field_name=canonical_field_name,
                value=raw_value,
            )

        return normalized_row, ignored_fields

    @staticmethod
    def normalize_rows(
        *,
        resource_type: ImportResourceType,
        raw_rows: list[dict[str, Any]],
    ) -> list[tuple[dict[str, Any], list[str]]]:
        """Normalize multiple parsed rows."""

        return [
            BulkImportNormalizer.normalize_row(
                resource_type=resource_type,
                raw_row=raw_row,
            )
            for raw_row in raw_rows
        ]
