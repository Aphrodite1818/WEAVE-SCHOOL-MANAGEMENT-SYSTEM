"""Direct tenant-admin routes for student creation and access-code reset."""

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import get_current_tenant_admin
from app.core.exceptions import NotFoundException
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


async def _persist_student_creation_admin_fields(
    *,
    db: AsyncSession,
    actor: TenantAdmin,
    payload: StudentCreate,
    student_response: StudentResponse,
) -> StudentResponse:
    """Persist optional admin-only student fields that are returned after create."""

    state_of_origin = getattr(payload, "state_of_origin", None)
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
    """Create a student and return the one-time setup code."""

    await SubscriptionFeatureService.ensure_resource_limit_available(
        db=db,
        tenant_id=current_admin.tenant_id,
        resource=ResourceLimitCode.STUDENTS,
    )
    student = await StudentService.create_student_profile(
        db=db,
        actor=current_admin,
        payload=payload,
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
    """Generate a fresh access code and disable the previous student password."""

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
