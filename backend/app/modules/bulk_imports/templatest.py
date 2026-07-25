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


class ImportTemplateNotFoundError(ValueError):
    """Raised when a template does not exist for a resource type."""


def create_template_column(
    *,
    name: str,
    label: str,
    required: bool = False,
    example: str | None = None,
    description: str | None = None,
    accepted_values: list[str] | None = None,
) -> ImportTemplateColumn:
    """Create one import template column."""

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

    columns = [
        create_template_column(
            name="first_name",
            label="First Name",
            required=True,
            example="Ade",
            description="Student first name.",
        ),
        create_template_column(
            name="last_name",
            label="Last Name",
            required=True,
            example="Johnson",
            description="Student last name.",
        ),
        create_template_column(
            name="gender",
            label="Gender",
            required=True,
            example="male",
            accepted_values=["male", "female"],
        ),
        create_template_column(
            name="date_of_birth",
            label="Date of Birth",
            required=True,
            example="2012-09-20",
            description="Use YYYY-MM-DD where possible.",
        ),
        create_template_column(
            name="state_of_origin",
            label="State of Origin",
            required=False,
            example="Lagos",
        ),
        create_template_column(
            name="class_name",
            label="Class Name",
            required=True,
            example="JSS 1",
            description="Must match an existing class name during processing.",
        ),
        create_template_column(
            name="arm",
            label="Arm",
            required=True,
            example="A",
            description="Must match the class arm.",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.STUDENTS,
        filename="students_import_template.csv",
        columns=columns,
        notes=[
            "Do not include admission_number unless your tenant allows manual admission numbers.",
            "Class name and arm must already exist before importing students.",
            "Valid rows will be imported. Invalid rows will be skipped and reported.",
        ],
    )


def create_teacher_template() -> ImportTemplateDefinition:
    """Create the teacher import template definition."""

    columns = [
        create_template_column(
            name="first_name",
            label="First Name",
            required=True,
            example="Mary",
        ),
        create_template_column(
            name="last_name",
            label="Last Name",
            required=True,
            example="Adebayo",
        ),
        create_template_column(
            name="email",
            label="Email",
            required=True,
            example="mary.adebayo@example.com",
        ),
        create_template_column(
            name="phone",
            label="Phone",
            required=False,
            example="+2348012345678",
        ),
        create_template_column(
            name="gender",
            label="Gender",
            required=False,
            example="female",
            accepted_values=["male", "female"],
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.TEACHERS,
        filename="teachers_import_template.csv",
        columns=columns,
        notes=[
            "Teacher email must be unique within the tenant.",
            "Teacher accounts may still require invite/setup handling in the service layer.",
        ],
    )


def create_parent_template() -> ImportTemplateDefinition:
    """Create the parent import template definition."""

    columns = [
        create_template_column(
            name="first_name",
            label="First Name",
            required=True,
            example="Tunde",
        ),
        create_template_column(
            name="last_name",
            label="Last Name",
            required=True,
            example="Johnson",
        ),
        create_template_column(
            name="email",
            label="Email",
            required=True,
            example="parent@example.com",
        ),
        create_template_column(
            name="phone",
            label="Phone",
            required=False,
            example="+2348012345678",
        ),
        create_template_column(
            name="student_admission_number",
            label="Student Admission Number",
            required=False,
            example="LNA20260012",
            description="Used later when linking a parent to an existing student.",
        ),
        create_template_column(
            name="relationship_type",
            label="Relationship Type",
            required=False,
            example="father",
            accepted_values=["father", "mother", "guardian", "sponsor", "other"],
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.PARENTS,
        filename="parents_import_template.csv",
        columns=columns,
        notes=[
            "Parent email should be unique within the tenant.",
            "Student linking can be processed only when student admission number is provided.",
        ],
    )


def create_class_template() -> ImportTemplateDefinition:
    """Create the class import template definition."""

    columns = [
        create_template_column(
            name="name",
            label="Class Name",
            required=True,
            example="JSS 1",
        ),
        create_template_column(
            name="arm",
            label="Arm",
            required=True,
            example="A",
        ),
        create_template_column(
            name="teacher_email",
            label="Class Teacher Email",
            required=False,
            example="teacher@example.com",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.CLASSES,
        filename="classes_import_template.csv",
        columns=columns,
        notes=[
            "Class name and arm should be unique within the tenant.",
            "Teacher email is optional and can be assigned later.",
        ],
    )


def create_subject_template() -> ImportTemplateDefinition:
    """Create the subject import template definition."""

    columns = [
        create_template_column(
            name="name",
            label="Subject Name",
            required=True,
            example="Mathematics",
        ),
        create_template_column(
            name="code",
            label="Subject Code",
            required=False,
            example="MTH",
        ),
        create_template_column(
            name="description",
            label="Description",
            required=False,
            example="Core mathematics subject.",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.SUBJECTS,
        filename="subjects_import_template.csv",
        columns=columns,
        notes=[
            "Subject names should be unique enough for admins to identify them.",
            "Subject assignment to classes can be imported separately.",
        ],
    )


def create_class_subject_template() -> ImportTemplateDefinition:
    """Create the class-subject assignment import template definition."""

    columns = [
        create_template_column(
            name="class_name",
            label="Class Name",
            required=True,
            example="JSS 1",
        ),
        create_template_column(
            name="arm",
            label="Arm",
            required=True,
            example="A",
        ),
        create_template_column(
            name="subject_name",
            label="Subject Name",
            required=True,
            example="Mathematics",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.CLASS_SUBJECTS,
        filename="class_subjects_import_template.csv",
        columns=columns,
        notes=[
            "Class and subject must already exist before creating the assignment.",
        ],
    )


def create_teacher_subject_template() -> ImportTemplateDefinition:
    """Create the teacher-subject assignment import template definition."""

    columns = [
        create_template_column(
            name="teacher_email",
            label="Teacher Email",
            required=True,
            example="teacher@example.com",
        ),
        create_template_column(
            name="subject_name",
            label="Subject Name",
            required=True,
            example="Mathematics",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.TEACHER_SUBJECTS,
        filename="teacher_subjects_import_template.csv",
        columns=columns,
        notes=[
            "Teacher and subject must already exist before creating the assignment.",
        ],
    )


def create_assessment_record_template() -> ImportTemplateDefinition:
    """Create the assessment record import template definition."""

    columns = [
        create_template_column(
            name="admission_number",
            label="Admission Number",
            required=True,
            example="LNA20260012",
        ),
        create_template_column(
            name="subject_name",
            label="Subject Name",
            required=True,
            example="Mathematics",
        ),
        create_template_column(
            name="assessment_name",
            label="Assessment Name",
            required=True,
            example="First Test",
        ),
        create_template_column(
            name="score",
            label="Score",
            required=True,
            example="18",
        ),
        create_template_column(
            name="max_score",
            label="Max Score",
            required=True,
            example="20",
        ),
        create_template_column(
            name="term_name",
            label="Term Name",
            required=False,
            example="First Term",
        ),
        create_template_column(
            name="session_name",
            label="Session Name",
            required=False,
            example="2025/2026",
        ),
    ]

    return ImportTemplateDefinition(
        resource_type=ImportResourceType.ASSESSMENT_RECORDS,
        filename="assessment_records_import_template.csv",
        columns=columns,
        notes=[
            "Student, subject, term, and session must exist before assessment import.",
            "score cannot be greater than max_score.",
        ],
    )


def build_template_definitions() -> dict[ImportResourceType, ImportTemplateDefinition]:
    """Build all available template definitions."""

    templates = [
        create_student_template(),
        create_teacher_template(),
        create_parent_template(),
        create_class_template(),
        create_subject_template(),
        create_class_subject_template(),
        create_teacher_subject_template(),
        create_assessment_record_template(),
    ]

    return {template.resource_type: template for template in templates}


def convert_column_to_response(
    *,
    column: ImportTemplateColumn,
) -> ImportTemplateColumnResponse:
    """Convert an internal template column to a response schema."""

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
    """Convert an internal template definition to a response schema."""

    columns = [
        convert_column_to_response(column=column)
        for column in template.columns
    ]

    return ImportTemplateResponse(
        resource_type=template.resource_type,
        file_type=file_type,
        filename=template.filename,
        columns=columns,
        notes=template.notes,
    )


def get_template_definition(
    *,
    resource_type: ImportResourceType,
) -> ImportTemplateDefinition:
    """Return one template definition by resource type."""

    templates = build_template_definitions()
    template = templates.get(resource_type)

    if template is None:
        raise ImportTemplateNotFoundError(
            f"No import template exists for resource type: {resource_type}"
        )

    return template


def get_template_response(
    *,
    resource_type: ImportResourceType,
    file_type: ImportFileType = ImportFileType.CSV,
) -> ImportTemplateResponse:
    """Return one template response by resource type."""

    template = get_template_definition(resource_type=resource_type)

    return convert_template_to_response(
        template=template,
        file_type=file_type,
    )


def list_template_responses(
    *,
    file_type: ImportFileType = ImportFileType.CSV,
) -> list[ImportTemplateResponse]:
    """Return all available template responses."""

    templates = build_template_definitions()

    return [
        convert_template_to_response(
            template=template,
            file_type=file_type,
        )
        for template in templates.values()
    ]
