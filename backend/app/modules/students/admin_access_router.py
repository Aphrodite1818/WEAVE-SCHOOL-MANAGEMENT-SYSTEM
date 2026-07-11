"""Direct tenant-admin routes for student creation and access-code reset."""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.classes.models import ClassRoom
from app.modules.students.models import StudentAccessCodePurpose
from app.modules.students.repository import StudentRepository
from app.modules.students.schemas import (
    StudentAdminAccessCodeResponse,
    StudentCreate,
    StudentResponse,
)
from app.modules.students.service import StudentService
from app.modules.subscriptions.service import SubscriptionFeatureService
from app.modules.subscriptions.subscription_enums import ResourceLimitCode
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter()
CurrentTenantAdmin: TypeAlias = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


async def _validate_student_class_assignment(
    *,
    db: AsyncSession,
    actor: TenantAdmin,
    class_id: UUID | None,
) -> None:
    """Ensure an optional class assignment belongs to the admin's tenant."""

    if class_id is None:
        return

    classroom = await db.get(ClassRoom, class_id)
    if classroom is None or classroom.tenant_id != actor.tenant_id:
        raise BadRequestException(detail="Selected class does not belong to this tenant")


async def _persist_student_creation_admin_fields(
    *,
    db: AsyncSession,
    actor: TenantAdmin,
    payload: StudentCreate,
    student_response: StudentResponse,
) -> StudentResponse:
    """Persist optional admin-only student fields returned after creation."""

    state_of_origin = payload.state_of_origin
    if not state_of_origin:
        return student_response

    student = await StudentRepository.get_student_by_id(
        db=db,
        tenant_id=actor.tenant_id,
        student_id=student_response.id,
    )
    if student is None:
        return student_response

    student.state_of_origin = state_of_origin
    updated_student = await StudentRepository.save(db=db, student=student)
    await db.commit()
    await db.refresh(updated_student)

    return StudentResponse.model_validate(updated_student).model_copy(
        update={
            "setup_code": student_response.setup_code,
            "access_code_expires_at": student_response.access_code_expires_at,
        }
    )


@router.post(
    "/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a student",
)
async def create_student(
    payload: StudentCreate,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentResponse:
    """Create a student and return the one-time initial setup code.

    Passport media is deliberately excluded from this request and is uploaded
    later through the dedicated media endpoint.
    """

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    await _validate_student_class_assignment(
        db=db,
        actor=current_admin,
        class_id=payload.class_id,
    )

    # StudentService still supports the persisted model attribute internally,
    # but the public creation schema intentionally rejects media URLs.
    service_payload = payload.model_copy(update={"passport_photo_url": None})

    student = await StudentService.create_student_profile(
        db=db,
        actor=current_admin,
        payload=service_payload,
    )
    student = await _persist_student_creation_admin_fields(
        db=db,
        actor=current_admin,
        payload=payload,
        student_response=student,
    )
    await SubscriptionFeatureService.invalidate_tenant_subscription_state(
        current_admin.tenant_id
    )
    return student


@router.post(
    "/students/{student_id}/reset-access-code",
    response_model=StudentAdminAccessCodeResponse,
    summary="Generate a new student access code",
)
async def reset_student_access_code(
    student_id: UUID,
    db: DbSession,
    current_admin: CurrentTenantAdmin,
) -> StudentAdminAccessCodeResponse:
    """Invalidate the password and generate a one-time password-reset code."""

    StudentService._ensure_tenant_admin(current_admin)

    student = await StudentRepository.get_student_by_id(
        db=db,
        tenant_id=current_admin.tenant_id,
        student_id=student_id,
    )
    if student is None:
        raise NotFoundException(detail="Student profile not found")

    plain_code, access_code = await StudentService._create_student_access_code(
        db=db,
        tenant_id=current_admin.tenant_id,
        student_id=student.id,
        purpose=StudentAccessCodePurpose.PASSWORD_RESET,
        created_by_admin_id=current_admin.id,
    )

    # A reset initiated by the administrator revokes the old password. The
    # student must log in with admission number + the newly generated code.
    student.password_hash = None
    student.password_reset_required = True
    updated_student = await StudentRepository.save(db=db, student=student)

    await db.commit()
    await db.refresh(updated_student)

    return StudentAdminAccessCodeResponse(
        student_id=updated_student.id,
        admission_number=updated_student.admission_number,
        full_name=StudentService._student_full_name(updated_student),
        purpose=StudentAccessCodePurpose.PASSWORD_RESET,
        access_code=plain_code,
        expires_at=access_code.expires_at,
    )
