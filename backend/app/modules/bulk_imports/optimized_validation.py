"""Batch-oriented validation helpers for student import dry runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.normalization import normalized_class_arm_key, normalized_class_name_key
from app.modules.auth.account_email_guard import INVITATION_EMAIL_CONFLICT_MESSAGE
from app.modules.auth_identity.models import ActorType, AuthIdentity, IdentifierType
from app.modules.bulk_imports.service import (
    _format_class_reference,
    _is_blank,
    append_validation_error,
)
from app.modules.bulk_imports.validators import ImportRowValidationResult
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelStatus,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.parents.models import ParentAccount
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.superadmin.models import SuperAdmin


async def resolve_student_class_references_batch(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    validation_results: list[ImportRowValidationResult],
) -> None:
    """Resolve all import hierarchy references with a bounded set of queries."""

    current_term = await StudentAcademicRepository.get_current_term(db, tenant_id)

    level_keys = {
        normalized_class_name_key(str(result.normalized_row.get("level")))
        for result in validation_results
        if not _is_blank(result.normalized_row.get("level"))
    }
    levels = (
        list(
            (
                await db.execute(
                    select(AcademicLevel).where(
                        AcademicLevel.tenant_id == tenant_id,
                        AcademicLevel.normalized_name.in_(level_keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        if level_keys
        else []
    )
    levels_by_key = {level.normalized_name: level for level in levels}

    arm_keys = {
        normalized_class_arm_key(result.normalized_row.get("arm"))
        for result in validation_results
        if not _is_blank(result.normalized_row.get("arm"))
    }
    arms = (
        list(
            (
                await db.execute(
                    select(ArmLabel).where(
                        ArmLabel.tenant_id == tenant_id,
                        ArmLabel.normalized_label.in_(arm_keys),
                    )
                )
            )
            .scalars()
            .all()
        )
        if arm_keys
        else []
    )
    arms_by_key = {arm.normalized_label: arm for arm in arms}

    level_ids = {level.id for level in levels}
    arm_ids = {arm.id for arm in arms}
    classrooms = (
        list(
            (
                await db.execute(
                    select(ClassRoom).where(
                        ClassRoom.tenant_id == tenant_id,
                        ClassRoom.academic_level_id.in_(level_ids),
                        ClassRoom.arm_label_id.in_(arm_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        if level_ids and arm_ids
        else []
    )
    classrooms_by_key = {
        (room.academic_level_id, room.arm_label_id): room for room in classrooms
    }

    assignments_by_class: dict[UUID, ClassTermDepartmentAssignment] = {}
    if current_term is not None and classrooms:
        assignments = list(
            (
                await db.execute(
                    select(ClassTermDepartmentAssignment).where(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.academic_term_id == current_term.id,
                        ClassTermDepartmentAssignment.class_id.in_(
                            {room.id for room in classrooms}
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        assignments_by_class = {
            assignment.class_id: assignment for assignment in assignments
        }
    else:
        assignments = []

    assigned_department_ids = {assignment.department_id for assignment in assignments}
    supplied_department_names = {
        str(result.normalized_row.get("department")).strip().casefold()
        for result in validation_results
        if not _is_blank(result.normalized_row.get("department"))
    }
    department_filters = [Department.tenant_id == tenant_id]
    if level_ids:
        department_filters.append(Department.academic_level_id.in_(level_ids))
    if assigned_department_ids or supplied_department_names:
        department_filters.append(
            (Department.id.in_(assigned_department_ids))
            | (Department.normalized_name.in_(supplied_department_names))
        )
        departments = list(
            (await db.execute(select(Department).where(*department_filters)))
            .scalars()
            .all()
        )
    else:
        departments = []
    departments_by_id = {department.id: department for department in departments}
    departments_by_level_name = {
        (department.academic_level_id, department.normalized_name): department
        for department in departments
    }

    for validation_result in validation_results:
        normalized_row = validation_result.normalized_row
        level_name = normalized_row.get("level")
        arm_name = normalized_row.get("arm")
        department_name = normalized_row.get("department")

        if _is_blank(level_name) or _is_blank(arm_name):
            continue

        level = levels_by_key.get(normalized_class_name_key(str(level_name)))
        if level is None:
            append_validation_error(
                validation_result=validation_result,
                field_name="level",
                error_code="level_not_found",
                error_message=f"Academic level {level_name} does not exist.",
            )
            continue
        if level.status != AcademicLevelStatus.ACTIVE:
            append_validation_error(
                validation_result=validation_result,
                field_name="level",
                error_code="level_inactive",
                error_message=f"Academic level {level.name} is inactive or archived.",
            )
            continue

        normalized_row["academic_level_id"] = str(level.id)
        normalized_row["level"] = level.name

        arm_label = arms_by_key.get(normalized_class_arm_key(arm_name))
        if arm_label is None:
            append_validation_error(
                validation_result=validation_result,
                field_name="arm",
                error_code="arm_label_not_found",
                error_message=(
                    f"Arm label {arm_name} does not exist. "
                    "Create the arm label before importing students."
                ),
            )
            continue
        if not arm_label.is_active or arm_label.archived_at is not None:
            append_validation_error(
                validation_result=validation_result,
                field_name="arm",
                error_code="arm_label_inactive",
                error_message=f"Arm label {arm_label.label} is inactive or archived.",
            )
            continue

        normalized_row["arm"] = arm_label.label
        classroom = classrooms_by_key.get((level.id, arm_label.id))
        class_reference = _format_class_reference(level.name, arm_label.label)
        if classroom is None:
            append_validation_error(
                validation_result=validation_result,
                field_name="arm",
                error_code="class_not_found",
                error_message=(
                    f"Class {class_reference} does not exist. "
                    "Create the class first before importing students."
                ),
            )
            continue
        if not classroom.is_active or classroom.archived_at is not None:
            append_validation_error(
                validation_result=validation_result,
                field_name="arm",
                error_code="class_inactive",
                error_message=(
                    f"Class {class_reference} is inactive or archived. "
                    "Use an active class before importing students."
                ),
            )
            continue

        normalized_row["class_id"] = str(classroom.id)
        if current_term is None:
            if not _is_blank(department_name):
                append_validation_error(
                    validation_result=validation_result,
                    field_name="department",
                    error_code="department_term_unavailable",
                    error_message=(
                        "Department placement cannot be validated because there is no "
                        "current academic term."
                    ),
                )
            else:
                normalized_row["department"] = None
            continue

        assignment = assignments_by_class.get(classroom.id)
        if assignment is None:
            if not _is_blank(department_name):
                append_validation_error(
                    validation_result=validation_result,
                    field_name="department",
                    error_code="department_not_applicable",
                    error_message=(
                        f"Class {class_reference} is General for the current term. "
                        "Leave department blank."
                    ),
                )
            else:
                normalized_row["department"] = None
            continue

        assigned_department = departments_by_id.get(assignment.department_id)
        if (
            assigned_department is None
            or not assigned_department.is_active
            or assigned_department.archived_at is not None
        ):
            append_validation_error(
                validation_result=validation_result,
                field_name="department",
                error_code="department_assignment_invalid",
                error_message=(
                    f"Class {class_reference} has an invalid current-term department assignment. "
                    "Fix the academic setup before importing students."
                ),
            )
            continue

        if _is_blank(department_name):
            append_validation_error(
                validation_result=validation_result,
                field_name="department",
                error_code="department_required",
                error_message=(
                    f"Department is required for class {class_reference} in the current term. "
                    f"Enter {assigned_department.name}."
                ),
            )
            continue

        supplied_key = str(department_name).strip().casefold()
        supplied_department = departments_by_level_name.get((level.id, supplied_key))
        if supplied_department is None:
            append_validation_error(
                validation_result=validation_result,
                field_name="department",
                error_code="department_not_found",
                error_message=(
                    f"Department {department_name} does not exist for academic level {level.name}."
                ),
            )
            continue
        if not supplied_department.is_active or supplied_department.archived_at is not None:
            append_validation_error(
                validation_result=validation_result,
                field_name="department",
                error_code="department_inactive",
                error_message=(
                    f"Department {supplied_department.name} is inactive or archived."
                ),
            )
            continue
        if supplied_department.id != assigned_department.id:
            append_validation_error(
                validation_result=validation_result,
                field_name="department",
                error_code="department_mismatch",
                error_message=(
                    f"Class {class_reference} is assigned to {assigned_department.name} "
                    f"for the current term, not {supplied_department.name}."
                ),
            )
            continue

        normalized_row["department"] = assigned_department.name


async def preflight_student_parent_invitations_batch(
    db: AsyncSession,
    *,
    validation_results: list[ImportRowValidationResult],
) -> dict[str, int]:
    """Validate all unique parent emails with three bounded lookup queries."""

    summary = {
        "parent_emails_supplied": 0,
        "existing_parent_accounts": 0,
        "new_parent_invitations_expected": 0,
        "parent_links_expected_after_acceptance": 0,
    }
    email_slots: list[tuple[ImportRowValidationResult, str, str]] = []
    unique_emails: set[str] = set()
    for result in validation_results:
        if result.errors:
            continue
        for index in (1, 2):
            field = f"parent_email_{index}"
            value = result.normalized_row.get(field)
            if _is_blank(value):
                continue
            summary["parent_emails_supplied"] += 1
            email = str(value).strip().lower()
            email_slots.append((result, field, email))
            unique_emails.add(email)

    if not unique_emails:
        return summary

    superadmin_emails = set(
        (
            await db.execute(
                select(func.lower(SuperAdmin.email)).where(
                    func.lower(SuperAdmin.email).in_(unique_emails)
                )
            )
        )
        .scalars()
        .all()
    )
    identities = list(
        (
            await db.execute(
                select(AuthIdentity).where(
                    AuthIdentity.identifier_type == IdentifierType.EMAIL,
                    AuthIdentity.identifier.in_(unique_emails),
                )
            )
        )
        .scalars()
        .all()
    )
    identities_by_email = {identity.identifier: identity for identity in identities}
    parents = list(
        (
            await db.execute(
                select(ParentAccount).where(ParentAccount.email.in_(unique_emails))
            )
        )
        .scalars()
        .all()
    )
    parents_by_email = {parent.email: parent for parent in parents}

    summary["existing_parent_accounts"] = len(parents_by_email)
    for result, field, email in email_slots:
        identity = identities_by_email.get(email)
        incompatible = email in superadmin_emails or (
            identity is not None and identity.actor_type != ActorType.PARENT_ACCOUNT
        )
        if incompatible:
            append_validation_error(
                validation_result=result,
                field_name=field,
                error_code="parent_email_role_conflict",
                error_message=INVITATION_EMAIL_CONFLICT_MESSAGE,
            )
            continue

        result.normalized_row[field] = email
        summary["new_parent_invitations_expected"] += 1
        summary["parent_links_expected_after_acceptance"] += 1

    return summary