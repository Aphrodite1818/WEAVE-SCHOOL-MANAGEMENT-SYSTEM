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
        filename="students_import_template.csv",
        columns=[
            create_template_column(name="first_name", label="First Name", required=True, example="Ade"),
            create_template_column(name="last_name", label="Last Name", required=True, example="Johnson"),
            create_template_column(
                name="date_of_birth",
                label="Date of Birth",
                required=False,
                example="2012-09-20",
                description="Optional. Use YYYY-MM-DD where possible.",
            ),
            create_template_column(
                name="gender",
                label="Gender",
                required=False,
                example="male",
                accepted_values=["male", "female"],
            ),
            create_template_column(
                name="class_id",
                label="Class ID",
                required=False,
                example="6d1fc27b-1cf4-43d2-a8f1-2f312226ca8f",
                description="Optional. Must be an existing class UUID if supplied.",
            ),
            create_template_column(name="arm", label="Arm", required=False, example="A"),
            create_template_column(name="state_of_origin", label="State of Origin", required=False, example="Lagos"),
        ],
        notes=[
            "Admission numbers are generated automatically by the backend.",
            "Student setup/access codes are generated automatically and included once in the result report.",
            "Only fields accepted by manual student creation are allowed.",
            "Students can complete remaining profile details through onboarding.",
        ],
    )


def create_teacher_template() -> ImportTemplateDefinition:
    """Create the teacher import template definition."""

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.TEACHERS,
        filename="teachers_import_template.csv",
        columns=[
            create_template_column(name="email", label="Email", required=True, example="mary.adebayo@example.com"),
            create_template_column(name="first_name", label="First Name", required=False, example="Mary"),
            create_template_column(name="last_name", label="Last Name", required=False, example="Adebayo"),
            create_template_column(name="staff_id", label="Staff ID", required=False, example="TCH-001"),
            create_template_column(name="qualification", label="Qualification", required=False, example="B.Ed"),
            create_template_column(name="specialization", label="Specialization", required=False, example="Mathematics"),
        ],
        notes=[
            "Teacher email is required and must be unique.",
            "Teacher invite emails are queued through the email outbox worker instead of sent inline.",
            "Only fields accepted by manual teacher creation are allowed.",
        ],
    )


def create_parent_template() -> ImportTemplateDefinition:
    """Create the parent import template definition."""

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.PARENTS,
        filename="parents_import_template.csv",
        columns=[
            create_template_column(name="email", label="Email", required=True, example="parent@example.com"),
            create_template_column(name="first_name", label="First Name", required=False, example="Tunde"),
            create_template_column(name="last_name", label="Last Name", required=False, example="Johnson"),
            create_template_column(name="phone_number", label="Phone Number", required=False, example="+2348012345678"),
            create_template_column(name="occupation", label="Occupation", required=False, example="Engineer"),
            create_template_column(name="address", label="Address", required=False, example="12 Allen Avenue"),
            create_template_column(name="emergency_phone", label="Emergency Phone", required=False, example="+2348098765432"),
        ],
        notes=[
            "Parent email is required and must be unique.",
            "Parent invite emails are queued through the email outbox worker instead of sent inline.",
            "Parent-student linking is intentionally not handled by this first bulk import version.",
            "Only fields accepted by manual parent creation are allowed.",
        ],
    )


def build_template_definitions() -> dict[ImportResourceType, ImportTemplateDefinition]:
    """Build all supported template definitions."""

    templates = [
        create_student_template(),
        create_teacher_template(),
        create_parent_template(),
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
    file_type: ImportFileType = ImportFileType.CSV,
) -> ImportTemplateResponse:
    """Convert one template definition to response schema."""

    return ImportTemplateResponse(
        resource_type=template.resource_type,
        file_type=file_type,
        filename=template.filename,
        columns=[
            convert_column_to_response(column=column)
            for column in template.columns
        ],
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
    file_type: ImportFileType = ImportFileType.CSV,
) -> ImportTemplateResponse:
    """Return one template response."""

    template = get_template_definition(resource_type=resource_type)

    return convert_template_to_response(
        template=template,
        file_type=file_type,
    )


def list_template_responses(
    *,
    file_type: ImportFileType = ImportFileType.CSV,
) -> list[ImportTemplateResponse]:
    """Return all supported template responses."""

    return [
        convert_template_to_response(
            template=template,
            file_type=file_type,
        )
        for template in build_template_definitions().values()
    ]
