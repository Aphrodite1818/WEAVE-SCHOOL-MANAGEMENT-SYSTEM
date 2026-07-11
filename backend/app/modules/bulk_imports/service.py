# =========================== #
#   bulk_imports_service.py   #
# =========================== #

"""Main service layer for tenant bulk imports."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.auth.service import UserInviteService
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.bulk_imports.chunking import chunk_import_items
from app.modules.bulk_imports.models import ImportFileType, ImportJobStatus, ImportResourceType
from app.modules.bulk_imports.normalizers import BulkImportNormalizer, SUPPORTED_IMPORT_RESOURCE_TYPES
from app.modules.bulk_imports.notification_service import BulkImportNotificationService
from app.modules.bulk_imports.parsers import BulkImportParser, ParsedImportFile
from app.modules.bulk_imports.repository import (
    ImportJobRepository,
    ImportRowErrorRepository,
    ImportStagedRowRepository,
)
from app.modules.bulk_imports.schemas import (
    ImportJobCreate,
    ImportJobDetailResponse,
    ImportJobListResponse,
    ImportJobSummaryResponse,
    ImportJobUpdate,
    ImportRowErrorCreate,
    ImportRowErrorListResponse,
)
from app.modules.bulk_imports.template_security import (
    build_headers_hash,
    verify_template_signature,
)
from app.modules.bulk_imports.template_writer import GeneratedImportTemplate, create_import_template
from app.modules.bulk_imports.templates import (
    CONTROL_COLUMNS,
    DATA_HEADERS_BY_RESOURCE,
    TEMPLATE_VERSION_BY_RESOURCE,
    get_template_response,
    list_template_responses,
)
from app.modules.bulk_imports.validators import (
    BulkImportValidator,
    ImportRowValidationResult,
    ImportValidationErrorItem,
)
from app.modules.classes.repository import ClassRoomRepository
from app.modules.email_outbox.service import EmailOutboxService
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.parents.repository import ParentRepository
from app.modules.parents.schemas import ParentCreate
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccessCode,
    StudentAccessCodePurpose,
    StudentAccountStatus,
    StudentProfileStatus,
)
from app.modules.students.repository import StudentRepository
from app.modules.students.schemas import StudentCreate
from app.modules.students.service import StudentService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import FeatureCode, ResourceLimitCode
from app.modules.teachers.models import Teacher, TeacherAccountStatus, TeacherStatus
from app.modules.teachers.repository import TeacherRepository
from app.modules.teachers.schemas import TeacherCreate
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


IMPORT_PROCESSING_CHUNK_SIZE = 100


def utc_now() -> datetime:
    """Return timezone-aware UTC now."""

    return datetime.now(timezone.utc)


def build_full_name(*, first_name: str | None, last_name: str | None, fallback: str) -> str:
    """Build a display name for invite emails."""

    name = " ".join(part for part in [first_name, last_name] if part).strip()
    return name or fallback


def compact_validation_error(exc: ValidationError) -> str:
    """Return a compact pydantic validation error message."""

    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(item) for item in first_error.get("loc", []))
    message = str(first_error.get("msg", "Invalid row data."))
    return f"{location}: {message}" if location else message


def build_failed_result_row(
    *,
    row_number: int,
    normalized_row: dict[str, Any],
    error_message: str,
) -> dict[str, Any]:
    """Build a failed row result."""

    return {
        "row_number": row_number,
        "status": "failed",
        **normalized_row,
        "error_message": error_message,
    }


def build_validation_error_items(
    *,
    import_job_id: UUID,
    validation_result: ImportRowValidationResult,
) -> list[ImportRowErrorCreate]:
    """Build row error schemas from validation errors."""

    return [
        ImportRowErrorCreate(
            import_job_id=import_job_id,
            row_number=error.row_number,
            field_name=error.field_name,
            error_code=error.error_code,
            error_message=error.error_message,
            raw_row=validation_result.raw_row,
            normalized_row=validation_result.normalized_row,
        )
        for error in validation_result.errors
    ]


def strip_control_columns(raw_row: dict[str, Any]) -> dict[str, Any]:
    """Remove signed-template control columns before row normalization."""

    return {
        key: value
        for key, value in raw_row.items()
        if BulkImportNormalizer.normalize_key(key) not in CONTROL_COLUMNS
    }


def _is_blank(value: Any) -> bool:
    """Return True when a value is blank."""

    return value is None or str(value).strip() == ""


def append_validation_error(
    *,
    validation_result: ImportRowValidationResult,
    field_name: str | None,
    error_code: str,
    error_message: str,
) -> None:
    """Append one service-level validation error to a row result."""

    validation_result.errors.append(
        ImportValidationErrorItem(
            row_number=validation_result.row_number,
            field_name=field_name,
            error_code=error_code,
            error_message=error_message,
        )
    )


class BulkImportService:
    """Coordinate parsing, validation, creation, results, and notifications."""

    @staticmethod
    def ensure_supported_resource_type(resource_type: ImportResourceType) -> None:
        """Reject resource types outside this implementation phase."""

        if resource_type not in SUPPORTED_IMPORT_RESOURCE_TYPES:
            raise BadRequestException(
                detail=f"{resource_type.value} bulk import is not supported yet."
            )

    @staticmethod
    def resource_limit_code(resource_type: ImportResourceType) -> ResourceLimitCode:
        """Map import resource type to subscription resource limit code."""

        return {
            ImportResourceType.STUDENTS: ResourceLimitCode.STUDENTS,
            ImportResourceType.TEACHERS: ResourceLimitCode.TEACHERS,
            ImportResourceType.PARENTS: ResourceLimitCode.PARENTS,
        }[resource_type]

    @staticmethod
    def resolve_final_status(*, successful_rows: int, failed_rows: int) -> ImportJobStatus:
        """Resolve final import job status from row counters."""

        if failed_rows == 0:
            return ImportJobStatus.COMPLETED
        if successful_rows > 0:
            return ImportJobStatus.PARTIALLY_COMPLETED
        return ImportJobStatus.FAILED

    @staticmethod
    def validate_exact_headers(
        *,
        actual_headers: list[str],
        expected_headers: list[str],
    ) -> None:
        """Ensure uploaded data headers exactly match the current template contract."""

        normalized_actual = [BulkImportNormalizer.normalize_key(header) for header in actual_headers]
        normalized_expected = [BulkImportNormalizer.normalize_key(header) for header in expected_headers]

        if normalized_actual != normalized_expected:
            raise BadRequestException(
                detail=(
                    "Import file headers do not match the selected template. "
                    f"Expected: {', '.join(expected_headers)}. "
                    f"Received: {', '.join(actual_headers)}."
                )
            )

    @staticmethod
    def validate_import_template_contract(
        *,
        tenant_id: UUID,
        endpoint_resource_type: ImportResourceType,
        parsed_file: ParsedImportFile,
    ) -> None:
        """Validate signed template metadata before processing rows."""

        metadata = parsed_file.metadata or {}
        resource_type_value = metadata.get("_import_resource_type")
        template_version = metadata.get("_import_template_version")
        headers_hash = metadata.get("_import_headers_hash")
        signature = metadata.get("_import_template_signature")

        if not all([resource_type_value, template_version, headers_hash, signature]):
            raise BadRequestException(
                detail="Import file must be generated from a valid backend template."
            )

        resource_type_value = str(resource_type_value).strip()
        template_version = str(template_version).strip()
        headers_hash = str(headers_hash).strip()
        signature = str(signature).strip()

        if resource_type_value != endpoint_resource_type.value:
            raise BadRequestException(
                detail=(
                    f"This file is for {resource_type_value}, but it was uploaded "
                    f"to {endpoint_resource_type.value} import."
                )
            )

        expected_version = TEMPLATE_VERSION_BY_RESOURCE[endpoint_resource_type]
        if template_version != expected_version:
            raise BadRequestException(
                detail="This import template version is no longer supported. Download a new template."
            )

        expected_headers = DATA_HEADERS_BY_RESOURCE[endpoint_resource_type]
        BulkImportService.validate_exact_headers(
            actual_headers=parsed_file.headers,
            expected_headers=expected_headers,
        )

        actual_headers_hash = build_headers_hash(parsed_file.headers)
        expected_headers_hash = build_headers_hash(expected_headers)

        if actual_headers_hash != headers_hash:
            raise BadRequestException(
                detail="Import file headers were changed. Download a new template and try again."
            )

        if headers_hash != expected_headers_hash:
            raise BadRequestException(
                detail="Import template headers do not match the current backend template."
            )

        if not verify_template_signature(
            tenant_id=tenant_id,
            resource_type=endpoint_resource_type,
            template_version=template_version,
            headers_hash=headers_hash,
            signature=signature,
        ):
            raise BadRequestException(
                detail="Invalid import template signature. Download a new template."
            )

    @staticmethod
    def build_validation_result_rows(
        *,
        validation_results: list[ImportRowValidationResult],
    ) -> list[dict[str, Any]]:
        """Build dry-run result rows."""

        result_rows: list[dict[str, Any]] = []

        for validation_result in validation_results:
            if validation_result.is_valid:
                result_rows.append(
                    {
                        "row_number": validation_result.row_number,
                        "status": "valid",
                        **validation_result.normalized_row,
                        "error_message": "",
                    }
                )
                continue

            result_rows.append(
                build_failed_result_row(
                    row_number=validation_result.row_number,
                    normalized_row=validation_result.normalized_row,
                    error_message="; ".join(
                        error.error_message for error in validation_result.errors
                    ),
                )
            )

        return result_rows

    @staticmethod
    def build_row_items(
        *,
        resource_type: ImportResourceType,
        parsed_file: ParsedImportFile,
    ) -> list[tuple[int, dict[str, Any], dict[str, Any], list[str]]]:
        """Strip control columns, normalize parsed rows, and build validator input."""

        row_items: list[tuple[int, dict[str, Any], dict[str, Any], list[str]]] = []

        for parsed_row in parsed_file.rows:
            raw_data = strip_control_columns(parsed_row.raw_data)
            normalized_row, ignored_fields = BulkImportNormalizer.normalize_row(
                resource_type=resource_type,
                raw_row=raw_data,
            )
            row_items.append((parsed_row.row_number, raw_data, normalized_row, ignored_fields))

        return row_items

    @staticmethod
    async def resolve_student_class_references(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        validation_results: list[ImportRowValidationResult],
    ) -> None:
        """Resolve class_name/class_arm values to the real class UUID for student imports."""

        for validation_result in validation_results:
            normalized_row = validation_result.normalized_row
            class_name = normalized_row.get("class_name")
            class_arm = normalized_row.get("class_arm")

            if _is_blank(class_name) and _is_blank(class_arm):
                normalized_row["class_id"] = None
                normalized_row["arm"] = None
                continue

            if _is_blank(class_name):
                append_validation_error(
                    validation_result=validation_result,
                    field_name="class_name",
                    error_code="required_with_class_arm",
                    error_message="class_name is required when class_arm is supplied.",
                )
                continue

            if _is_blank(class_arm):
                append_validation_error(
                    validation_result=validation_result,
                    field_name="class_arm",
                    error_code="required_with_class_name",
                    error_message="class_arm is required when class_name is supplied.",
                )
                continue

            classroom = await ClassRoomRepository.get_classroom_by_normalized_name_and_arm(
                db=db,
                tenant_id=tenant_id,
                class_name=str(class_name),
                class_arm=str(class_arm),
            )

            if classroom is None:
                append_validation_error(
                    validation_result=validation_result,
                    field_name="class_name",
                    error_code="class_not_found",
                    error_message=(
                        f"Class {class_name} {class_arm} does not exist. "
                        "Create the class first before importing students."
                    ),
                )
                continue

            normalized_row["class_id"] = str(classroom.id)
            normalized_row["class_name"] = classroom.name
            normalized_row["class_arm"] = classroom.arm
            normalized_row["arm"] = classroom.arm

    @staticmethod
    async def create_student_from_row(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        normalized_row: dict[str, Any],
    ) -> dict[str, Any]:
        """Create one student using manual creation semantics without committing."""

        student_data = StudentCreate(
            admission_number=None,
            first_name=normalized_row.get("first_name"),
            last_name=normalized_row.get("last_name"),
            date_of_birth=BulkImportValidator.parse_date(normalized_row.get("date_of_birth")),
            gender=normalized_row.get("gender"),
            class_id=BulkImportValidator.parse_uuid(normalized_row.get("class_id")),
            arm=normalized_row.get("arm") or normalized_row.get("class_arm"),
            state_of_origin=normalized_row.get("state_of_origin"),
            status=AcademicStatus.ACTIVE,
        )

        admission_number = await StudentService.generate_admission_number(
            db=db,
            tenant_id=actor.tenant_id,
        )

        if await StudentRepository.admission_number_exists(
            db=db,
            tenant_id=actor.tenant_id,
            admission_number=admission_number,
        ):
            raise ConflictException(detail="Admission number already exists")

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=admission_number,
            identifier_type=IdentifierType.ADMISSION_NUMBER,
        )

        student = Student(
            tenant_id=actor.tenant_id,
            admission_number=admission_number,
            password_hash=None,
            first_name=student_data.first_name,
            last_name=student_data.last_name,
            date_of_birth=student_data.date_of_birth,
            gender=student_data.gender,
            passport_photo_url=None,
            admission_date=StudentService._get_default_admission_date(),
            graduation_date=None,
            class_id=student_data.class_id,
            arm=student_data.arm,
            status=student_data.status,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=True,
            last_login_at=None,
            profile_status=StudentProfileStatus.INCOMPLETE,
            state_of_origin=student_data.state_of_origin,
        )
        student.profile_status = StudentService._resolve_profile_status(student)

        created_student = await StudentRepository.create_student(db=db, student=student)

        await AuthIdentityService.create_for_actor(
            db=db,
            tenant_id=actor.tenant_id,
            payload=AuthIdentityCreate(
                identifier=admission_number,
                identifier_type=IdentifierType.ADMISSION_NUMBER,
                actor_type=ActorType.STUDENT,
                actor_id=created_student.id,
                is_active=True,
            ),
        )

        setup_code, access_code = await StudentService._create_student_access_code(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=created_student.id,
            purpose=StudentAccessCodePurpose.INITIAL_SETUP,
            created_by_admin_id=actor.id,
        )

        return {
            "student": created_student,
            "setup_code": setup_code,
            "access_code": access_code,
        }

    @staticmethod
    async def create_teacher_from_row(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        normalized_row: dict[str, Any],
        school_name: str,
    ) -> dict[str, Any]:
        """Create one teacher and queue invite email without committing."""

        teacher_data = TeacherCreate(**normalized_row)
        normalized_email = str(teacher_data.email).strip().lower()

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )

        existing_teacher = await TeacherRepository.get_by_email(db=db, email=normalized_email)
        if existing_teacher is not None:
            raise ConflictException(detail="A teacher with this email already exists")

        if teacher_data.staff_id is not None:
            staff_id_exists = await TeacherRepository.staff_id_exists(
                db=db,
                tenant_id=actor.tenant_id,
                staff_id=teacher_data.staff_id,
            )
            if staff_id_exists:
                raise ConflictException(detail="A teacher with this staff ID already exists")

        temporary_password = secrets.token_urlsafe(32)
        teacher = Teacher(
            tenant_id=actor.tenant_id,
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            first_name=teacher_data.first_name,
            last_name=teacher_data.last_name,
            staff_id=teacher_data.staff_id,
            qualification=teacher_data.qualification,
            specialization=teacher_data.specialization,
            account_status=TeacherAccountStatus.PENDING,
            status=TeacherStatus.ACTIVE,
            is_verified=False,
            is_active=True,
        )

        created_teacher = await TeacherRepository.create_teacher(db=db, teacher=teacher)

        await AuthIdentityService.create_for_actor(
            db=db,
            tenant_id=actor.tenant_id,
            payload=AuthIdentityCreate(
                identifier=normalized_email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.TEACHER,
                actor_id=created_teacher.id,
                is_active=True,
            ),
        )

        invite_link = await UserInviteService.create_invite_record(
            db=db,
            email=normalized_email,
            tenant_id=actor.tenant_id,
        )

        await EmailOutboxService.queue_user_invite_email(
            db=db,
            tenant_id=actor.tenant_id,
            email=normalized_email,
            user_name=build_full_name(
                first_name=created_teacher.first_name,
                last_name=created_teacher.last_name,
                fallback=normalized_email,
            ),
            school_name=school_name,
            invite_link=invite_link,
            metadata_json={
                "source": "bulk_import",
                "actor_type": "teacher",
                "actor_id": str(created_teacher.id),
            },
        )

        return {"teacher": created_teacher, "invite_status": "queued"}

    @staticmethod
    async def create_parent_from_row(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        normalized_row: dict[str, Any],
        school_name: str,
    ) -> dict[str, Any]:
        """Create one parent and queue invite email without committing."""

        parent_data = ParentCreate(**normalized_row)
        normalized_email = str(parent_data.email).strip().lower()

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=normalized_email,
            identifier_type=IdentifierType.EMAIL,
        )

        if await ParentRepository.email_exists(db=db, email=normalized_email):
            raise ConflictException(detail="A parent with this email already exists")

        temporary_password = secrets.token_urlsafe(32)
        parent = Parent(
            tenant_id=actor.tenant_id,
            email=normalized_email,
            password_hash=hash_password(temporary_password),
            first_name=parent_data.first_name,
            last_name=parent_data.last_name,
            phone_number=parent_data.phone_number,
            occupation=parent_data.occupation,
            address=parent_data.address,
            emergency_phone=parent_data.emergency_phone,
            account_status=ParentAccountStatus.PENDING,
            is_verified=False,
            is_active=True,
            last_login_at=None,
        )

        created_parent = await ParentRepository.create_parent(db=db, parent=parent)

        await AuthIdentityService.create_for_actor(
            db=db,
            tenant_id=actor.tenant_id,
            payload=AuthIdentityCreate(
                identifier=normalized_email,
                identifier_type=IdentifierType.EMAIL,
                actor_type=ActorType.PARENT,
                actor_id=created_parent.id,
                is_active=True,
            ),
        )

        invite_link = await UserInviteService.create_invite_record(
            db=db,
            email=normalized_email,
            tenant_id=actor.tenant_id,
        )

        await EmailOutboxService.queue_user_invite_email(
            db=db,
            tenant_id=actor.tenant_id,
            email=normalized_email,
            user_name=build_full_name(
                first_name=created_parent.first_name,
                last_name=created_parent.last_name,
                fallback=normalized_email,
            ),
            school_name=school_name,
            invite_link=invite_link,
            metadata_json={
                "source": "bulk_import",
                "actor_type": "parent",
                "actor_id": str(created_parent.id),
            },
        )

        return {"parent": created_parent, "invite_status": "queued"}

    @staticmethod
    async def process_valid_row(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        validation_result: ImportRowValidationResult,
        school_name: str,
    ) -> dict[str, Any]:
        """Process one validated row."""

        if resource_type == ImportResourceType.STUDENTS:
            created = await BulkImportService.create_student_from_row(
                db=db,
                actor=actor,
                normalized_row=validation_result.normalized_row,
            )
            student: Student = created["student"]
            access_code: StudentAccessCode = created["access_code"]
            return {
                "row_number": validation_result.row_number,
                "status": "created",
                "first_name": student.first_name,
                "last_name": student.last_name,
                "admission_number": student.admission_number,
                "class_name": validation_result.normalized_row.get("class_name"),
                "class_arm": validation_result.normalized_row.get("class_arm"),
                "setup_code": created["setup_code"],
                "access_code_expires_at": access_code.expires_at.isoformat(),
                "error_message": "",
            }

        if resource_type == ImportResourceType.TEACHERS:
            created = await BulkImportService.create_teacher_from_row(
                db=db,
                actor=actor,
                normalized_row=validation_result.normalized_row,
                school_name=school_name,
            )
            teacher: Teacher = created["teacher"]
            return {
                "row_number": validation_result.row_number,
                "status": "created",
                "invite_status": created["invite_status"],
                "email": teacher.email,
                "first_name": teacher.first_name,
                "last_name": teacher.last_name,
                "staff_id": teacher.staff_id,
                "error_message": "",
            }

        if resource_type == ImportResourceType.PARENTS:
            created = await BulkImportService.create_parent_from_row(
                db=db,
                actor=actor,
                normalized_row=validation_result.normalized_row,
                school_name=school_name,
            )
            parent: Parent = created["parent"]
            return {
                "row_number": validation_result.row_number,
                "status": "created",
                "invite_status": created["invite_status"],
                "email": parent.email,
                "first_name": parent.first_name,
                "last_name": parent.last_name,
                "error_message": "",
            }

        raise BadRequestException(detail=f"{resource_type.value} bulk import is not supported yet.")

    @staticmethod
    async def process_valid_rows(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        validation_results: list[ImportRowValidationResult],
        import_job_id: UUID,
        school_name: str,
    ) -> tuple[int, int, list[ImportRowErrorCreate], list[dict[str, Any]]]:
        """Process valid rows in chunks."""

        successful_rows = 0
        failed_rows = 0
        row_error_items: list[ImportRowErrorCreate] = []
        result_rows: list[dict[str, Any]] = []

        for chunk in chunk_import_items(items=validation_results, chunk_size=IMPORT_PROCESSING_CHUNK_SIZE):
            for validation_result in chunk.items:
                try:
                    async with db.begin_nested():
                        result_row = await BulkImportService.process_valid_row(
                            db=db,
                            actor=actor,
                            resource_type=resource_type,
                            validation_result=validation_result,
                            school_name=school_name,
                        )
                    successful_rows += 1
                    result_rows.append(result_row)

                except (BadRequestException, ConflictException, NotFoundException, ValidationError) as exc:
                    failed_rows += 1
                    error_message = (
                        compact_validation_error(exc)
                        if isinstance(exc, ValidationError)
                        else str(exc.detail if hasattr(exc, "detail") else exc)
                    )
                    row_error_items.append(
                        ImportRowErrorCreate(
                            import_job_id=import_job_id,
                            row_number=validation_result.row_number,
                            field_name=None,
                            error_code="processing_error",
                            error_message=error_message,
                            raw_row=validation_result.raw_row,
                            normalized_row=validation_result.normalized_row,
                        )
                    )
                    result_rows.append(
                        build_failed_result_row(
                            row_number=validation_result.row_number,
                            normalized_row=validation_result.normalized_row,
                            error_message=error_message,
                        )
                    )

                except IntegrityError:
                    failed_rows += 1
                    error_message = "Row failed because of a duplicate or invalid database value."
                    row_error_items.append(
                        ImportRowErrorCreate(
                            import_job_id=import_job_id,
                            row_number=validation_result.row_number,
                            field_name=None,
                            error_code="integrity_error",
                            error_message=error_message,
                            raw_row=validation_result.raw_row,
                            normalized_row=validation_result.normalized_row,
                        )
                    )
                    result_rows.append(
                        build_failed_result_row(
                            row_number=validation_result.row_number,
                            normalized_row=validation_result.normalized_row,
                            error_message=error_message,
                        )
                    )

        return successful_rows, failed_rows, row_error_items, result_rows

    @staticmethod
    def generate_template_file(
        *,
        tenant_id: UUID,
        resource_type: ImportResourceType,
        file_type: ImportFileType = ImportFileType.XLSX,
    ) -> GeneratedImportTemplate:
        """Generate a signed backend-owned import template file."""

        BulkImportService.ensure_supported_resource_type(resource_type)
        try:
            return create_import_template(
                tenant_id=tenant_id,
                resource_type=resource_type,
                file_type=file_type,
            )
        except ValueError as exc:
            raise BadRequestException(detail=str(exc)) from exc

    @staticmethod
    async def create_dry_run_from_upload(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        upload_file: UploadFile,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        """Parse, validate, and stage an import file without creating records."""

        BulkImportService.ensure_supported_resource_type(resource_type)

        await SubscriptionFeatureService.ensure_feature_enabled(
            db=db,
            tenant_id=actor.tenant_id,
            feature=FeatureCode.BULK_IMPORT,
        )

        parsed_file = await BulkImportParser.parse_upload(upload_file)
        if not parsed_file.rows:
            raise BadRequestException(detail="Import file does not contain any data rows.")

        BulkImportService.validate_import_template_contract(
            tenant_id=actor.tenant_id,
            endpoint_resource_type=resource_type,
            parsed_file=parsed_file,
        )

        import_job = await ImportJobRepository.create_job(
            db=db,
            tenant_id=actor.tenant_id,
            job_data=ImportJobCreate(
                resource_type=resource_type,
                file_type=parsed_file.file_type,
                original_filename=upload_file.filename or f"{resource_type.value}_import.{parsed_file.file_type.value}",
                file_size_bytes=parsed_file.file_size_bytes,
                created_by_admin_id=actor.id,
                metadata_json={
                    "dry_run": True,
                    "confirmation_required": True,
                    "notify_on_completion": notify_on_completion,
                    "template_version": parsed_file.metadata.get("_import_template_version"),
                    "template_headers_hash": parsed_file.metadata.get("_import_headers_hash"),
                    "result_rows": [],
                },
            ),
        )

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=ImportJobStatus.PROCESSING,
                started_at=utc_now(),
                total_rows=len(parsed_file.rows),
            ),
        )

        row_items = BulkImportService.build_row_items(
            resource_type=resource_type,
            parsed_file=parsed_file,
        )
        validation_results = BulkImportValidator.validate_rows(
            resource_type=resource_type,
            row_items=row_items,
        )

        if resource_type == ImportResourceType.STUDENTS:
            await BulkImportService.resolve_student_class_references(
                db=db,
                tenant_id=actor.tenant_id,
                validation_results=validation_results,
            )

        invalid_results = [result for result in validation_results if not result.is_valid]
        valid_results = [result for result in validation_results if result.is_valid]

        validation_error_items: list[ImportRowErrorCreate] = []
        for validation_result in invalid_results:
            validation_error_items.extend(
                build_validation_error_items(
                    import_job_id=import_job.id,
                    validation_result=validation_result,
                )
            )

        if validation_error_items:
            await ImportRowErrorRepository.create_many(
                db=db,
                tenant_id=actor.tenant_id,
                row_error_items=validation_error_items,
            )

        if valid_results:
            await ImportStagedRowRepository.create_many(
                db=db,
                tenant_id=actor.tenant_id,
                import_job_id=import_job.id,
                validation_results=valid_results,
            )

        successful_rows = len(valid_results)
        failed_rows = len(invalid_results)
        result_rows = BulkImportService.build_validation_result_rows(
            validation_results=validation_results,
        )
        final_status = BulkImportService.resolve_final_status(
            successful_rows=successful_rows,
            failed_rows=failed_rows,
        )

        metadata_json = dict(import_job.metadata_json or {})
        metadata_json["result_rows"] = sorted(
            result_rows,
            key=lambda row: int(row.get("row_number") or 0),
        )
        metadata_json["valid_rows"] = len(valid_results)
        metadata_json["invalid_rows"] = len(invalid_results)
        metadata_json["staged_valid_rows"] = len(valid_results)
        metadata_json["dry_run_completed_at"] = utc_now().isoformat()

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=final_status,
                total_rows=len(parsed_file.rows),
                processed_rows=len(parsed_file.rows),
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                skipped_rows=0,
                completed_at=utc_now(),
                metadata_json=metadata_json,
            ),
        )

        await db.commit()

        refreshed_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=import_job.id,
            include_children=True,
        )
        if refreshed_job is None:
            raise NotFoundException(detail="Import job not found after dry run.")

        return ImportJobDetailResponse.model_validate(refreshed_job)

    @staticmethod
    async def create_import_from_upload(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        resource_type: ImportResourceType,
        upload_file: UploadFile,
        dry_run: bool = False,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        """Backward-compatible upload entry point.

        Real imports now require a dry-run job and the confirm endpoint.
        """

        if not dry_run:
            raise BadRequestException(
                detail="Direct bulk imports are disabled. Run dry_run=true first, then confirm the import job."
            )

        return await BulkImportService.create_dry_run_from_upload(
            db=db,
            actor=actor,
            resource_type=resource_type,
            upload_file=upload_file,
            notify_on_completion=notify_on_completion,
        )

    @staticmethod
    async def confirm_import_from_dry_run(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: UUID,
        notify_on_completion: bool = True,
    ) -> ImportJobDetailResponse:
        """Confirm a staged dry-run import and create records from staged rows."""

        await SubscriptionFeatureService.ensure_feature_enabled(
            db=db,
            tenant_id=actor.tenant_id,
            feature=FeatureCode.BULK_IMPORT,
        )

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
            lock=True,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")

        metadata_json = dict(import_job.metadata_json or {})
        if not metadata_json.get("dry_run"):
            raise BadRequestException(detail="Only dry-run import jobs can be confirmed.")

        if metadata_json.get("confirmed_at"):
            raise BadRequestException(detail="This import job has already been confirmed.")

        staged_rows = await ImportStagedRowRepository.list_by_job(
            db=db,
            tenant_id=actor.tenant_id,
            import_job_id=import_job.id,
        )
        if not staged_rows:
            raise BadRequestException(detail="This dry-run job has no valid staged rows to confirm.")

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=actor.tenant_id)
        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        await SubscriptionFeatureService.ensure_resource_limit_available(
            db=db,
            tenant_id=actor.tenant_id,
            resource=BulkImportService.resource_limit_code(import_job.resource_type),
            increment=len(staged_rows),
        )

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=ImportJobStatus.PROCESSING,
                started_at=utc_now(),
                completed_at=None,
                successful_rows=0,
                failed_rows=0,
                processed_rows=0,
            ),
        )

        validation_results = [
            ImportRowValidationResult(
                row_number=staged_row.row_number,
                raw_row=staged_row.raw_row,
                normalized_row=staged_row.normalized_row,
            )
            for staged_row in staged_rows
        ]

        created_count, processing_failed_count, processing_errors, processing_result_rows = (
            await BulkImportService.process_valid_rows(
                db=db,
                actor=actor,
                resource_type=import_job.resource_type,
                validation_results=validation_results,
                import_job_id=import_job.id,
                school_name=tenant.school_name,
            )
        )

        if processing_errors:
            await ImportRowErrorRepository.create_many(
                db=db,
                tenant_id=actor.tenant_id,
                row_error_items=processing_errors,
            )

        existing_result_rows = list(metadata_json.get("result_rows") or [])
        invalid_result_rows = [
            row for row in existing_result_rows
            if row.get("status") == "failed"
        ]

        invalid_rows = int(metadata_json.get("invalid_rows") or 0)
        successful_rows = created_count
        failed_rows = invalid_rows + processing_failed_count
        result_rows = [*invalid_result_rows, *processing_result_rows]
        final_status = BulkImportService.resolve_final_status(
            successful_rows=successful_rows,
            failed_rows=failed_rows,
        )

        metadata_json["dry_run"] = False
        metadata_json["confirmed_from_dry_run"] = True
        metadata_json["confirmation_required"] = False
        metadata_json["confirmed_at"] = utc_now().isoformat()
        metadata_json["valid_rows"] = len(staged_rows)
        metadata_json["invalid_rows"] = invalid_rows
        metadata_json["result_rows"] = sorted(
            result_rows,
            key=lambda row: int(row.get("row_number") or 0),
        )

        import_job = await ImportJobRepository.update_job(
            db=db,
            import_job=import_job,
            job_update=ImportJobUpdate(
                status=final_status,
                total_rows=import_job.total_rows,
                processed_rows=import_job.total_rows,
                successful_rows=successful_rows,
                failed_rows=failed_rows,
                skipped_rows=0,
                completed_at=utc_now(),
                metadata_json=metadata_json,
            ),
        )

        if notify_on_completion:
            if final_status == ImportJobStatus.FAILED:
                await BulkImportNotificationService.create_failure_notification(
                    db=db,
                    tenant_id=actor.tenant_id,
                    recipient_admin_id=actor.id,
                    import_job=import_job,
                )
            else:
                await BulkImportNotificationService.create_completion_notification(
                    db=db,
                    tenant_id=actor.tenant_id,
                    recipient_admin_id=actor.id,
                    import_job=import_job,
                )

        if successful_rows > 0:
            await SubscriptionFeatureService.invalidate_tenant_subscription_state(actor.tenant_id)

        await db.commit()
        await AuthIdentityService.invalidate_after_commit(db)

        if successful_rows > 0 and import_job.resource_type in {ImportResourceType.TEACHERS, ImportResourceType.PARENTS}:
            try:
                from app.core.queue.arq import enqueue_email_outbox_batch

                await enqueue_email_outbox_batch(batch_size=50)
            except Exception:
                pass

        refreshed_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=import_job.id,
            include_children=True,
        )
        if refreshed_job is None:
            raise NotFoundException(detail="Import job not found after confirmation.")

        return ImportJobDetailResponse.model_validate(refreshed_job)

    @staticmethod
    async def list_jobs(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        skip: int = 0,
        limit: int = 50,
        resource_type: ImportResourceType | None = None,
        status: ImportJobStatus | None = None,
    ) -> ImportJobListResponse:
        """List tenant import jobs."""

        jobs, total = await ImportJobRepository.list_jobs(
            db=db,
            tenant_id=actor.tenant_id,
            skip=skip,
            limit=limit,
            resource_type=resource_type,
            status=status,
        )

        return ImportJobListResponse(
            items=[ImportJobSummaryResponse.model_validate(job) for job in jobs],
            total=total,
        )

    @staticmethod
    async def get_job(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: UUID,
    ) -> ImportJobDetailResponse:
        """Return one import job."""

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
            include_children=True,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")

        return ImportJobDetailResponse.model_validate(import_job)

    @staticmethod
    async def list_job_errors(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> ImportRowErrorListResponse:
        """Return row errors for one import job."""

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")

        row_errors, total = await ImportRowErrorRepository.list_errors_by_job(
            db=db,
            tenant_id=actor.tenant_id,
            import_job_id=job_id,
            skip=skip,
            limit=limit,
        )

        return ImportRowErrorListResponse(items=row_errors, total=total)

    @staticmethod
    async def get_result_rows(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        job_id: UUID,
    ) -> tuple[ImportResourceType, list[dict[str, Any]]]:
        """Return persisted result rows for a completed import job."""

        import_job = await ImportJobRepository.get_job_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            job_id=job_id,
        )
        if import_job is None:
            raise NotFoundException(detail="Import job not found")

        metadata_json = import_job.metadata_json or {}
        result_rows = metadata_json.get("result_rows") or []

        return import_job.resource_type, list(result_rows)

    @staticmethod
    def list_templates(*, file_type: ImportFileType = ImportFileType.XLSX):
        """Return all supported import templates."""

        return list_template_responses(file_type=file_type)

    @staticmethod
    def get_template(*, resource_type: ImportResourceType, file_type: ImportFileType = ImportFileType.XLSX):
        """Return one supported import template."""

        BulkImportService.ensure_supported_resource_type(resource_type)
        return get_template_response(resource_type=resource_type, file_type=file_type)
