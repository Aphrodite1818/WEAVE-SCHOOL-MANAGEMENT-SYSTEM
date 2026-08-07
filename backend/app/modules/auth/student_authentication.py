"""Student admission-number authentication orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_auth_secret, verify_password
from app.core.exceptions import NotFoundException, UnauthorizedException
from app.modules.auth.models import AuthSessionActorType
from app.modules.auth.schemas import LoginSessionUser
from app.modules.auth.service import AuthenticatedActor
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.students.models import AcademicStatus, StudentAccountStatus
from app.modules.students.repository import (
    StudentAccessCodeRepository,
    StudentRepository,
)
from app.tenant_management.models import TenantStatus, TenantVerificationStatus
from app.tenant_management.repository import TenantRepository


async def authenticate_student_actor(
    db: AsyncSession,
    *,
    admission_number: str,
    credential: str,
) -> AuthenticatedActor:
    normalized = admission_number.strip().upper()
    try:
        resolution = await AuthIdentityService.resolve_identifier(
            db,
            identifier=normalized,
            identifier_type=IdentifierType.ADMISSION_NUMBER,
        )
    except NotFoundException as exc:
        raise UnauthorizedException("Invalid admission number or credential.") from exc

    if resolution.actor_type != ActorType.STUDENT or resolution.tenant_id is None:
        raise UnauthorizedException("Invalid admission number or credential.")
    tenant = await TenantRepository.get_by_id(db, resolution.tenant_id)
    if (
        tenant is None
        or tenant.is_deleted
        or tenant.verification_status != TenantVerificationStatus.ACTIVE
        or tenant.status not in {TenantStatus.ACTIVE, TenantStatus.TRIAL}
    ):
        raise UnauthorizedException("Account is not active.")

    student = await StudentRepository.get_by_id(
        db,
        resolution.tenant_id,
        resolution.actor_id,
    )
    if student is None:
        raise UnauthorizedException("Invalid admission number or credential.")

    if student.status == AcademicStatus.EXPELLED:
        raise UnauthorizedException(
            "This account has been expelled and can no longer be accessed."
        )
    if student.status == AcademicStatus.SUSPENDED:
        raise UnauthorizedException("This account is currently suspended.")
    if student.status == AcademicStatus.WITHDRAWN:
        raise UnauthorizedException("This account has been withdrawn.")
    if student.status == AcademicStatus.GRADUATED:
        raise UnauthorizedException(
            "This account has graduated and is now read-only or inactive."
        )

    if (
        not student.is_active
        or not student.is_verified
        or student.account_status != StudentAccountStatus.ACTIVE
        or student.is_archived
    ):
        raise UnauthorizedException("Account is not active.")

    password_matches = bool(
        student.password_hash and verify_password(credential, student.password_hash)
    )
    access_code = None
    if not password_matches:
        access_code = await StudentAccessCodeRepository.get_active_code_by_digest(
            db,
            student.tenant_id,
            student.id,
            hash_auth_secret(credential),
        )
    if not password_matches and access_code is None:
        raise UnauthorizedException("Invalid admission number or credential.")

    if access_code is not None:
        student.password_reset_required = True
    student.last_login_at = datetime.now(timezone.utc)
    db.add(student)
    await db.flush()

    profile_status = getattr(
        student.profile_status, "value", str(student.profile_status)
    )
    return AuthenticatedActor(
        actor_type=AuthSessionActorType.STUDENT.value,
        account_type=AuthSessionActorType.STUDENT.value,
        actor_id=student.id,
        email=student.admission_number,
        role="student",
        tenant_id=student.tenant_id,
        password_reset_required=student.password_reset_required,
        user=LoginSessionUser(
            id=str(student.id),
            tenant_id=str(student.tenant_id),
            school_name=tenant.school_name,
            email=student.admission_number,
            admission_number=student.admission_number,
            first_name=student.first_name,
            last_name=student.last_name,
            actor_type=AuthSessionActorType.STUDENT.value,
            account_type=AuthSessionActorType.STUDENT.value,
            role="student",
            password_reset_required=student.password_reset_required,
            profile_status=profile_status,
            passport_photo_url=student.passport_photo_url,
            tenant_logo_url=tenant.logo_url,
        ),
    )
