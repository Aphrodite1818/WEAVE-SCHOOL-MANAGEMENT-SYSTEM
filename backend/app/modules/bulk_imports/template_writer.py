# ================================== #
#   bulk_imports_template_writer.py  #
# ================================== #

"""Generate downloadable XLSX bulk import templates."""

from __future__ import annotations

import io
from dataclasses import dataclass
from uuid import UUID

from openpyxl import Workbook

from app.modules.bulk_imports.models import ImportFileType, ImportResourceType
from app.modules.bulk_imports.template_security import (
    build_headers_hash,
    build_template_signature_payload,
    sign_template_payload,
)
from app.modules.bulk_imports.templates import (
    DATA_HEADERS_BY_RESOURCE,
    TEMPLATE_METADATA_SHEET_NAME,
    TEMPLATE_VERSION_BY_RESOURCE,
)


@dataclass(frozen=True)
class GeneratedImportTemplate:
    """Generated import template file payload."""

    filename: str
    content_bytes: bytes
    content_type: str


def build_template_metadata(
    *,
    tenant_id: UUID,
    resource_type: ImportResourceType,
) -> dict[str, str]:
    """Build signed metadata for a tenant-specific import template."""

    data_headers = DATA_HEADERS_BY_RESOURCE[resource_type]
    template_version = TEMPLATE_VERSION_BY_RESOURCE[resource_type]
    headers_hash = build_headers_hash(data_headers)
    signature_payload = build_template_signature_payload(
        tenant_id=tenant_id,
        resource_type=resource_type,
        template_version=template_version,
        headers_hash=headers_hash,
    )

    return {
        "_import_resource_type": resource_type.value,
        "_import_template_version": template_version,
        "_import_headers_hash": headers_hash,
        "_import_template_signature": sign_template_payload(signature_payload),
    }


def create_xlsx_template(
    *,
    tenant_id: UUID,
    resource_type: ImportResourceType,
) -> GeneratedImportTemplate:
    """Create an XLSX template with hidden signed metadata."""

    workbook = Workbook()

    data_sheet = workbook.active
    data_sheet.title = f"{resource_type.value}_import"

    data_headers = DATA_HEADERS_BY_RESOURCE[resource_type]
    data_sheet.append(data_headers)

    metadata = build_template_metadata(
        tenant_id=tenant_id,
        resource_type=resource_type,
    )

    metadata_sheet = workbook.create_sheet(TEMPLATE_METADATA_SHEET_NAME)
    metadata_sheet.sheet_state = "veryHidden"
    metadata_sheet.append(["key", "value"])

    for key, value in metadata.items():
        metadata_sheet.append([key, value])

    output = io.BytesIO()
    workbook.save(output)

    return GeneratedImportTemplate(
        filename=f"{resource_type.value}_import_template.xlsx",
        content_bytes=output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def create_import_template(
    *,
    tenant_id: UUID,
    resource_type: ImportResourceType,
    file_type: ImportFileType,
) -> GeneratedImportTemplate:
    """Create a signed XLSX import template file."""

    if file_type != ImportFileType.XLSX:
        raise ValueError(
            "Bulk import templates are XLSX-only. Download the .xlsx template and upload that file."
        )

    return create_xlsx_template(tenant_id=tenant_id, resource_type=resource_type)
