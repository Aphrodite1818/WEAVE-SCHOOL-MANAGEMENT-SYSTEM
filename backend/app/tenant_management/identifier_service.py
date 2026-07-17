"""Generate tenant-scoped student and teacher identifiers."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.modules.students.models import Student
from app.modules.teachers.models import TeacherInvitation, TeacherMembership
from app.tenant_management.models import Tenant
from app.tenant_management.repository import TenantRepository


class TenantIdentifierKind(StrEnum):
    """Supported school-owned identifier types."""

    STUDENT = "student"
    TEACHER = "teacher"


class TenantIdentifierService:
    """Validate tenant onboarding and allocate school-owned identifiers."""

    MAX_GENERATION_ATTEMPTS = 50

    @staticmethod
    async def require_completed_onboarding(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        lock: bool = False,
    ) -> Tenant:
        """Return an onboarded tenant or reject school-owned record creation."""

        tenant = await TenantRepository.get_by_id(
            db,
            tenant_id,
            lock=lock,
        )
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        prefix = (tenant.admission_number_prefix or "").strip().upper()
        if not tenant.onboarding_completed or not prefix:
            raise ForbiddenException(
                "Complete school onboarding before creating students or inviting "
                "teachers. Set a unique admission prefix, address, city, and state."
            )
        if not prefix.isalnum():
            raise ForbiddenException(
                "The admission prefix must contain only letters and numbers. "
                "Update school onboarding before continuing."
            )

        tenant.admission_number_prefix = prefix
        return tenant

    @staticmethod
    def _build_candidate(prefix: str) -> str:
        """Build PREFIX + two-digit year + six-digit random suffix."""

        year = datetime.now(timezone.utc).strftime("%y")
        suffix = secrets.randbelow(900_000) + 100_000
        return f"{prefix}{year}{suffix:06d}"

    @staticmethod
    async def _identifier_exists(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        candidate: str,
    ) -> bool:
        """Keep student admission numbers and teacher staff IDs in one namespace."""

        student_id = (
            await db.execute(
                select(Student.id)
                .where(
                    Student.tenant_id == tenant_id,
                    Student.admission_number == candidate,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if student_id is not None:
            return True

        membership_id = (
            await db.execute(
                select(TeacherMembership.id)
                .where(
                    TeacherMembership.tenant_id == tenant_id,
                    TeacherMembership.staff_id == candidate,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if membership_id is not None:
            return True

        invitation_id = (
            await db.execute(
                select(TeacherInvitation.id)
                .where(
                    TeacherInvitation.tenant_id == tenant_id,
                    TeacherInvitation.staff_id == candidate,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return invitation_id is not None

    @classmethod
    async def generate_identifier(
        cls,
        db: AsyncSession,
        *,
        tenant: Tenant,
        kind: TenantIdentifierKind,
    ) -> str:
        """Allocate an identifier such as WVS26483912 for a student or teacher."""

        prefix = (tenant.admission_number_prefix or "").strip().upper()
        if not prefix or not tenant.onboarding_completed:
            raise ForbiddenException(
                "Complete school onboarding before generating school identifiers."
            )

        for _ in range(cls.MAX_GENERATION_ATTEMPTS):
            candidate = cls._build_candidate(prefix)
            if not await cls._identifier_exists(
                db,
                tenant_id=tenant.id,
                candidate=candidate,
            ):
                return candidate

        raise ConflictException(
            f"Could not allocate a unique {kind.value} identifier. Please try again."
        )
