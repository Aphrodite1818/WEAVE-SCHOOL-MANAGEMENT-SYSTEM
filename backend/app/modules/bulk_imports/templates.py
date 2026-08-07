# =========================== #
#   bulk_imports_templates.py #
# =========================== #

"""Template definitions for tenant bulk import files."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.bulk_imports.models import ImportFileType, ImportResourceType
from app.modules.bulk_imports.schemas import (
    ImportTemplateColumnResponse,
    ImportTemplateResponse,
)

TEMPLATE_METADATA_SHEET_NAME = "_import_metadata"

CONTROL_COLUMNS: set[str] = {
    "_import_resource_type",
    "_import_template_version",
    "_import_headers_hash",
    "_import_template_signature",
}

TEMPLATE_VERSION_BY_RESOURCE: dict[ImportResourceType, str] = {
    ImportResourceType.STUDENTS: "students_v4",
}

DATA_HEADERS_BY_RESOURCE: dict[ImportResourceType, list[str]] = {
    ImportResourceType.STUDENTS: [
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
    ],
}


@dataclass(frozen=True)
class ImportTemplateColumn:
    """Internal representation of one template column."""

    name: str
    label: str
    required: bool = False
    example: str | None = None
    description: str | None = None
    accepted_values: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportTemplateDefinition:
    """Internal representation of one resource import template."""

    resource_type: ImportResourceType
    filename: str
    columns: list[ImportTemplateColumn]
    notes: list[str] = field(default_factory=list)


def create_template_column(
    *,
    name: str,
    label: str,
    required: bool = False,
    example: str | None = None,
    description: str | None = None,
    accepted_values: list[str] | None = None,
) -> ImportTemplateColumn:
    """Create one template column."""

    return ImportTemplateColumn(
        name=name,
        label=label,
        required=required,
        example=example,
        description=description,
        accepted_values=accepted_values or [],
    )


def create_student_template() -> ImportTemplateDefinition:
    """Create the student import template definition."""

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.STUDENTS,
        filename="students_import_template.xlsx",
        columns=[
            create_template_column(
                name="first_name", label="First Name", required=True, example="Ade"
            ),
            create_template_column(
                name="last_name", label="Last Name", required=True, example="Johnson"
            ),
            create_template_column(
                name="date_of_birth",
                label="Date of Birth",
                required=True,
                example="2012-09-20",
                description="Required. Use YYYY-MM-DD where possible. Students cannot edit this later.",
            ),
            create_template_column(
                name="gender",
                label="Gender",
                required=False,
                example="male",
                accepted_values=["male", "female"],
            ),
            create_template_column(
                name="class_name",
                label="Class Name",
                required=True,
                example="JSS1",
                description="Required. Use the class name visible to admins, for example JSS1 or Primary 4.",
            ),
            create_template_column(
                name="class_arm",
                label="Class Arm",
                required=False,
                example="A",
                description="Optional. Leave blank for classes without arms, or enter an existing arm such as A or Science.",
            ),
            create_template_column(
                name="state_of_origin",
                label="State of Origin",
                required=False,
                example="Lagos",
            ),
            create_template_column(
                name="parent_email_1",
                label="Parent or Guardian Email 1",
                required=False,
                example="parent.one@example.com",
                description="Optional. Provide one or two parent or guardian email addresses.",
            ),
            create_template_column(
                name="parent_relationship_1",
                label="Parent or Guardian Relationship 1",
                required=False,
                example="mother",
                accepted_values=["father", "mother", "guardian", "sponsor", "other"],
            ),
            create_template_column(
                name="parent_email_2",
                label="Parent or Guardian Email 2",
                required=False,
                example="parent.two@example.com",
                description="Optional second parent or guardian. A third parent column is not supported.",
            ),
            create_template_column(
                name="parent_relationship_2",
                label="Parent or Guardian Relationship 2",
                required=False,
                example="father",
                accepted_values=["father", "mother", "guardian", "sponsor", "other"],
            ),
        ],
        notes=[
            "Use the downloaded backend-generated template file. Do not recreate headers manually.",
            "Admission numbers are generated automatically by the backend.",
            "Date of birth is required because students cannot edit it later.",
            "Class name is required. Class arm is optional for classes without an arm.",
            "Use class_name and optional class_arm for student class placement. Do not enter internal class UUIDs.",
            "The backend resolves class_name + class_arm to the real active class during dry-run.",
            "Parent or guardian emails are optional in the current student-creation workflow. If an email is supplied, its matching relationship column is required.",
            "A maximum of two parents or guardians is supported per imported student.",
            "Accepted date formats include YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, MM/DD/YYYY, MM-DD-YYYY, and YYYY/MM/DD.",
            "Student setup/access codes are generated automatically and included once in the result report and access slips.",
        ],
    )


def build_template_definitions() -> dict[ImportResourceType, ImportTemplateDefinition]:
    """Build all supported template definitions."""

    templates = [
        create_student_template(),
    ]

    return {template.resource_type: template for template in templates}


def convert_column_to_response(
    *,
    column: ImportTemplateColumn,
) -> ImportTemplateColumnResponse:
    """Convert one template column to response schema."""

    return ImportTemplateColumnResponse(
        name=column.name,
        label=column.label,
        required=column.required,
        example=column.example,
        description=column.description,
        accepted_values=column.accepted_values,
    )


def convert_template_to_response(
    *,
    template: ImportTemplateDefinition,
    file_type: ImportFileType = ImportFileType.XLSX,
) -> ImportTemplateResponse:
    """Convert one template definition to response schema."""

    return ImportTemplateResponse(
        resource_type=template.resource_type,
        file_type=file_type,
        filename=f"{template.resource_type.value}_import_template.{file_type.value}",
        template_version=TEMPLATE_VERSION_BY_RESOURCE.get(template.resource_type),
        columns=[convert_column_to_response(column=column) for column in template.columns],
        notes=template.notes,
    )


def get_template_definition(
    *,
    resource_type: ImportResourceType,
) -> ImportTemplateDefinition:
    """Return one template definition."""

    templates = build_template_definitions()
    template = templates.get(resource_type)

    if template is None:
        raise ValueError(f"{resource_type.value} bulk import is not supported yet.")

    return template


def get_template_response(
    *,
    resource_type: ImportResourceType,
    file_type: ImportFileType = ImportFileType.XLSX,
) -> ImportTemplateResponse:
    """Return one template response."""

    template = get_template_definition(resource_type=resource_type)

    return convert_template_to_response(
        template=template,
        file_type=file_type,
    )


def list_template_responses(
    *,
    file_type: ImportFileType = ImportFileType.XLSX,
) -> list[ImportTemplateResponse]:
    """Return all supported template responses."""

    return [
        convert_template_to_response(
            template=template,
            file_type=file_type,
        )
        for template in build_template_definitions().values()
    ]
