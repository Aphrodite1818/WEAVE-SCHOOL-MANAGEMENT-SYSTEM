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
    ImportResourceType.STUDENTS: "students_v2",
    ImportResourceType.TEACHERS: "teachers_v1",
    ImportResourceType.PARENTS: "parents_v1",
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
    ],
    ImportResourceType.TEACHERS: [
        "email",
        "first_name",
        "last_name",
        "staff_id",
        "qualification",
        "specialization",
    ],
    ImportResourceType.PARENTS: [
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "occupation",
        "address",
        "emergency_phone",
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
            create_template_column(name="first_name", label="First Name", required=True, example="Ade"),
            create_template_column(name="last_name", label="Last Name", required=True, example="Johnson"),
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
                required=False,
                example="JSS1",
                description="Optional. Use the class name visible to admins, for example JSS1 or Primary 4.",
            ),
            create_template_column(
                name="class_arm",
                label="Class Arm",
                required=False,
                example="A",
                description="Optional. Leave blank for classes without arms, or enter an existing arm such as A or Science.",
            ),
            create_template_column(name="state_of_origin", label="State of Origin", required=False, example="Lagos"),
        ],
        notes=[
            "Use the downloaded backend-generated template file. Do not recreate headers manually.",
            "Admission numbers are generated automatically by the backend.",
            "Date of birth is required because students cannot edit it later.",
            "Use class_name and optional class_arm for student class placement. Do not enter internal class UUIDs.",
            "The backend resolves class_name + optional class_arm to the real class record during dry-run.",
            "Student setup/access codes are generated automatically and included once in the result report.",
            "Students can complete remaining profile details through onboarding.",
        ],
    )


def create_teacher_template() -> ImportTemplateDefinition:
    """Create the teacher import template definition."""

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.TEACHERS,
        filename="teachers_import_template.xlsx",
        columns=[
            create_template_column(name="email", label="Email", required=True, example="mary.adebayo@example.com"),
            create_template_column(name="first_name", label="First Name", required=False, example="Mary"),
            create_template_column(name="last_name", label="Last Name", required=False, example="Adebayo"),
            create_template_column(name="staff_id", label="Staff ID", required=False, example="TCH-001"),
            create_template_column(name="qualification", label="Qualification", required=False, example="B.Ed"),
            create_template_column(name="specialization", label="Specialization", required=False, example="Mathematics"),
        ],
        notes=[
            "Use the downloaded backend-generated template file. Do not recreate headers manually.",
            "Teacher email is required and must be unique.",
            "Teacher invite emails are queued through the email outbox worker instead of sent inline.",
            "Only fields accepted by manual teacher creation are allowed.",
        ],
    )


def create_parent_template() -> ImportTemplateDefinition:
    """Create the parent import template definition."""

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.PARENTS,
        filename="parents_import_template.xlsx",
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
            "Use the downloaded backend-generated template file. Do not recreate headers manually.",
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
    file_type: ImportFileType = ImportFileType.XLSX,
) -> ImportTemplateResponse:
    """Convert one template definition to response schema."""

    return ImportTemplateResponse(
        resource_type=template.resource_type,
        file_type=file_type,
        filename=f"{template.resource_type.value}_import_template.{file_type.value}",
        template_version=TEMPLATE_VERSION_BY_RESOURCE.get(template.resource_type),
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
