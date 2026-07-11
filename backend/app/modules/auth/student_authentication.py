"""Student-specific login orchestration.

Students authenticate with their generated admission number and either their
current password or an active one-time access code. Access-code authentication
always forces password setup before dashboard access.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_auth_secret, verify_password
from app.core.exceptions import NotFoundException, UnauthorizedException
from app.modules.auth.schemas import LoginSessionUser
from app.modules.auth.service import (
    AuthenticatedActor,
    _enum_value,
    _tenant_allows_login,
    _update_last_login_if_due,
)
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.students.models import StudentAccountStatus
from app.modules.students.repository import StudentAccessCodeRepository, StudentRepository
from app.tenant_management.repository import TenantRepository


async def authenticate_student_actor(
    db: AsyncSession,
    *,
    admission_number: str,
    credential: str,
) -> AuthenticatedActor:
    """Authenticate a student using a password or active access code."""

    normalized_admission_number = admission_number.strip().upper()

    try:
        resolution = await AuthIdentityService.resolve_identifier(
            db=db,
            identifier=normalized_admission_number,
            identifier_type=IdentifierType.ADMISSION_NUMBER,
        )
    except NotFoundException as exc:
        raise UnauthorizedException("Invalid admission number or credential") from exc

    if resolution.actor_type != ActorType.STUDENT:
        raise UnauthorizedException("Invalid admission number or credential")

    tenant = await TenantRepository.get_by_id(db, resolution.tenant_id)
    if not _tenant_allows_login(tenant):
        raise UnauthorizedException("Account is not active")

    student = await StudentRepository.get_by_id(db, resolution.actor_id)
    if student is None or student.tenant_id != resolution.tenant_id:
        raise UnauthorizedException("Account not found")

    if (
        not student.is_active
        or not student.is_verified
        or student.account_status != StudentAccountStatus.ACTIVE
    ):
        raise UnauthorizedException("Account is not active")

    password_matches = bool(
        student.password_hash
        and verify_password(credential, student.password_hash)
    )

    access_code = None
    if not password_matches:
        access_code = await StudentAccessCodeRepository.get_active_code_by_digest(
            db=db,
            tenant_id=student.tenant_id,
            student_id=student.id,
            code_digest=hash_auth_secret(credential),
        )

    if not password_matches and access_code is None:
        raise UnauthorizedException("Invalid admission number or credential")

    # Every access-code login is a password-setup/reset session. The code is
    # consumed only after the student successfully saves the new password.
    if access_code is not None and not student.password_reset_required:
        student.password_reset_required = True
        await db.flush()

    await _update_last_login_if_due(db, student)

    return AuthenticatedActor(
        actor_type=ActorType.STUDENT.value,
        account_type=ActorType.STUDENT.value,
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
            actor_type=ActorType.STUDENT.value,
            account_type=ActorType.STUDENT.value,
            role="student",
            password_reset_required=student.password_reset_required,
            profile_status=_enum_value(student.profile_status),
            passport_photo_url=student.passport_photo_url,
            tenant_logo_url=tenant.logo_url,
        ),
    )
