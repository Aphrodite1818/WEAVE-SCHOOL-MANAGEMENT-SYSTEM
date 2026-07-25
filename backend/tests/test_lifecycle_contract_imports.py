"""Import and schema regressions for the lifecycle hardening modules."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.auth.membership_summary_service import AccountMembershipSummary
from app.modules.parents.lifecycle_contracts import ParentLinkedStudentListResponse
from app.modules.students.admin_contracts import StudentAdminContractService
from app.modules.teachers.capability_service import TeacherSubjectCapabilityListResponse
from app.modules.teachers.offboarding_service import TeacherOffboardingRequest
from app.modules.teachers.patch_service import TeacherPatchService


def test_lifecycle_modules_import_without_circular_dependencies() -> None:
    assert StudentAdminContractService is not None
    assert TeacherPatchService is not None
    assert ParentLinkedStudentListResponse(items=[], total=0).total == 0
    assert TeacherSubjectCapabilityListResponse(items=[], total=0).total == 0


def test_membership_summary_requires_authoritative_school_metadata() -> None:
    summary = AccountMembershipSummary(
        membership_id=uuid4(),
        tenant_id=uuid4(),
        tenant_name="Weave Academy",
        tenant_logo_url=None,
        membership_status="active",
    )
    assert summary.tenant_name == "Weave Academy"
    assert summary.membership_status == "active"


def test_teacher_offboarding_request_rejects_short_reason() -> None:
    with pytest.raises(ValidationError):
        TeacherOffboardingRequest(reason="no")


def test_teacher_offboarding_request_accepts_optional_replacement() -> None:
    replacement_id = uuid4()
    payload = TeacherOffboardingRequest(
        reason="Teacher resigned from the school.",
        replacement_teacher_membership_id=replacement_id,
    )
    assert payload.replacement_teacher_membership_id == replacement_id
