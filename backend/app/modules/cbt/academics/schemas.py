# ==========================#
# cbt/academics/schemas.py
# ==========================#
"""
Contracts for synchronizing academic state from Weave Cloud to a CBT server.

These schemas define the external cloud -> CBT academic synchronization
contract

They Intentionally expose only the academic state required by the local CBT
runtime. Internal Weave persistence details, lifecycle history, authentication
material, payments , report cards , attendance and unreleated tenant data
must not leak through this contract
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

CBTSchemaVersion = Literal[1]


InstitutionTypeValue = Literal[
    "PRIMARY_SCHOOL",
    "SECONDARY_SCHOOL",
]


AcademicCategoryValue = Literal[
    "KINDERGARTEN",
    "PRIMARY",
    "JUNIOR_SECONDARY",
    "SENIOR_SECONDARY",
]


AcademicSessionStatusValue = Literal[
    "draft",
    "open",
    "closing",
    "closed",
]

AcademicTermNameValue = Literal[
    "first_term",
    "second_term",
    "third_term",
]

AcademicTermStatusValue = Literal[
    "draft",
    "open",
    "closing",
    "closed",
]

AssessmentSchemeStatusValue = Literal[
    "draft",
    "active",
    "archived",
]

StudentAcademicStatusValue = Literal[
    "active",
    "withdrawn",
    "suspended",
    "graduated",
    "expelled",
]


class CBTContractModel(BaseModel):
    """Base model for the versioned CBT synchronization contract"""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ==========================#
# Synchronization metadata
# ==========================#


class CBTSyncMetadata(CBTContractModel):
    """Metadata describing the bootstrap snapshot"""

    schema_version: CBTSchemaVersion = 1
    snapshot_id: UUID
    generated_at: datetime
    cursor: str | None


# ==========================#
# Server / school identity
# ==========================#


class CBTServerSnapshot(CBTContractModel):
    id: UUID
    name: str

    institution_type: InstitutionTypeValue | None
    timezone: str


class CBTSchoolSnapshot(CBTContractModel):
    id: UUID
    name: str
    institution_type: InstitutionTypeValue | None
    timezone: str


# ==========================#
# Current academic context
# ==========================#


class CBTSessionSnapshot(CBTContractModel):
    id: UUID
    name: str
    status: AcademicSessionStatusValue
    start_date: date | None
    end_date: date | None


class CBTTermSnapshot(CBTContractModel):
    id: UUID
    academic_session_id: UUID
    name: AcademicTermNameValue
    status: AcademicTermStatusValue
    start_date: date | None
    end_date: date | None


class CBTAcademicContextSnapshot(CBTContractModel):
    """The currently operational academic session/term."""

    session: CBTSessionSnapshot | None

    term: CBTTermSnapshot | None


# ---------------------------------------------------------------------------
# Academic hierarchy
# ---------------------------------------------------------------------------


class CBTLevelSnapshot(CBTContractModel):
    id: UUID

    name: str

    category: AcademicCategoryValue

    position: int = Field(gt=0)


class CBTDepartmentSnapshot(CBTContractModel):
    id: UUID

    name: str


class CBTArmLabelSnapshot(CBTContractModel):
    id: UUID

    label: str

    position: int | None = Field(default=None, gt=0)


class CBTClassSnapshot(CBTContractModel):
    id: UUID

    academic_level_id: UUID

    department_id: UUID | None

    arm_label_id: UUID | None

    display_name: str


class CBTAcademicStructureSnapshot(CBTContractModel):
    levels: list[CBTLevelSnapshot]

    departments: list[CBTDepartmentSnapshot]

    arm_labels: list[CBTArmLabelSnapshot]

    classes: list[CBTClassSnapshot]


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------


class CBTSubjectSnapshot(CBTContractModel):
    id: UUID

    name: str

    code: str | None


class CBTLevelSubjectSnapshot(CBTContractModel):
    id: UUID

    academic_level_id: UUID

    subject_id: UUID


class CBTSubjectOfferingSnapshot(CBTContractModel):
    """One current-term subject offering visible to the CBT runtime.

    `eligible_enrollment_ids` is resolved by Weave.

    The local CBT must NOT reproduce Weave's department/specialization
    eligibility rules.

    For a non-elective offering this represents the academically eligible
    candidate pool.

    For an elective offering it represents the students who may take the
    subject. The local exam roster can then select actual participants for a
    particular CBT exam.
    """

    id: UUID

    level_subject_id: UUID

    academic_term_id: UUID

    department_id: UUID | None

    is_elective: bool

    eligible_enrollment_ids: list[UUID]


class CBTCurriculumSnapshot(CBTContractModel):
    subjects: list[CBTSubjectSnapshot]

    level_subjects: list[CBTLevelSubjectSnapshot]

    subject_offerings: list[CBTSubjectOfferingSnapshot]


# ---------------------------------------------------------------------------
# Assessment configuration
# ---------------------------------------------------------------------------


class CBTAssessmentSchemeSnapshot(CBTContractModel):
    id: UUID

    name: str

    status: AssessmentSchemeStatusValue


class CBTAssessmentComponentSnapshot(CBTContractModel):
    id: UUID

    assessment_scheme_id: UUID

    name: str

    code: str | None

    maximum_score: Decimal = Field(gt=0, le=100)

    position: int = Field(ge=0)


class CBTAssessmentSnapshot(CBTContractModel):
    scheme: CBTAssessmentSchemeSnapshot | None

    components: list[CBTAssessmentComponentSnapshot]


# ---------------------------------------------------------------------------
# Staff / teacher context
# ---------------------------------------------------------------------------


class CBTTeacherSnapshot(CBTContractModel):
    """Minimal teacher identity required by the local CBT runtime."""

    account_id: UUID

    membership_id: UUID

    display_name: str

    email: EmailStr

    staff_id: str | None


class CBTTeacherAssignmentSnapshot(CBTContractModel):
    id: UUID

    teacher_membership_id: UUID

    class_id: UUID

    level_subject_id: UUID

    effective_from: date

    effective_to: date | None


class CBTStaffSnapshot(CBTContractModel):
    teachers: list[CBTTeacherSnapshot]

    teacher_assignments: list[CBTTeacherAssignmentSnapshot]


# ---------------------------------------------------------------------------
# Student / enrollment projection
# ---------------------------------------------------------------------------


class CBTStudentEnrollmentSnapshot(CBTContractModel):
    """Current student identity and academic placement required by CBT.

    Academic level is authoritative.

    Class and department are independent nullable operational/specialization
    state.

    `department_id` represents the department effective for the synchronized
    term. CBT does not receive or interpret department assignment history.
    """

    enrollment_id: UUID

    student_id: UUID

    admission_number: str

    first_name: str | None
    last_name: str | None

    display_name: str

    academic_session_id: UUID

    academic_level_id: UUID

    class_id: UUID | None

    department_id: UUID | None

    student_status: StudentAcademicStatusValue

    started_on: date


class CBTStudentSnapshot(CBTContractModel):
    enrollments: list[CBTStudentEnrollmentSnapshot]


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


class CBTReadinessBlocker(CBTContractModel):
    """Machine-readable blocker plus human-readable explanation.

    The code remains a string intentionally so adding a new readiness blocker
    does not require changing the entire bootstrap schema version.
    """

    code: str

    message: str


class CBTReadinessSnapshot(CBTContractModel):
    can_conduct_exam: bool

    blockers: list[CBTReadinessBlocker]


# ---------------------------------------------------------------------------
# Bootstrap response
# ---------------------------------------------------------------------------


class CBTAcademicBootstrapResponse(CBTContractModel):
    """Complete bootstrap snapshot returned to one authenticated CBT server."""

    sync: CBTSyncMetadata

    server: CBTServerSnapshot

    school: CBTSchoolSnapshot

    academic_context: CBTAcademicContextSnapshot

    structure: CBTAcademicStructureSnapshot

    curriculum: CBTCurriculumSnapshot

    assessment: CBTAssessmentSnapshot

    staff: CBTStaffSnapshot

    students: CBTStudentSnapshot

    readiness: CBTReadinessSnapshot
