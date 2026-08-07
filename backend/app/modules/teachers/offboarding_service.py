"""Teacher offboarding impact inspection and atomic responsibility cleanup."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.models import (
    ClassSubjectTeacher,
    TeacherAssignment,
)
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.teachers.schemas import (
    TeacherMembershipEndRequest,
    TeacherMembershipResponse,
)
from app.modules.teachers.service import TeacherMembershipService
from app.modules.tenant_admins.models import TenantAdmin


class TeacherOffboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=500)
    replacement_teacher_membership_id: UUID | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return str(value or "").strip()


class TeacherOffboardingImpactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    class_teacher_assignments: int = Field(ge=0)
    teacher_assignments: int = Field(ge=0)
    legacy_class_subject_assignments: int = Field(ge=0)


class TeacherOffboardingService:
    @staticmethod
    async def inspect(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
    ) -> TeacherOffboardingImpactResponse:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=tenant_id,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        class_teacher_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ClassRoom)
                    .where(
                        ClassRoom.tenant_id == tenant_id,
                        ClassRoom.teacher_membership_id == membership_id,
                        ClassRoom.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
        assignment_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(TeacherAssignment)
                    .where(
                        TeacherAssignment.tenant_id == tenant_id,
                        TeacherAssignment.teacher_membership_id == membership_id,
                        TeacherAssignment.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
        legacy_assignment_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ClassSubjectTeacher)
                    .where(
                        ClassSubjectTeacher.tenant_id == tenant_id,
                        ClassSubjectTeacher.teacher_membership_id == membership_id,
                        ClassSubjectTeacher.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
        return TeacherOffboardingImpactResponse(
            membership_id=membership_id,
            class_teacher_assignments=class_teacher_count,
            teacher_assignments=assignment_count,
            legacy_class_subject_assignments=legacy_assignment_count,
        )

    @staticmethod
    async def end_membership_and_release_responsibilities(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        membership_id: UUID,
        payload: TeacherOffboardingRequest,
    ) -> TeacherMembershipResponse:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        replacement_id = payload.replacement_teacher_membership_id
        if replacement_id == membership_id:
            raise BadRequestException("A teacher cannot replace their own membership.")

        if replacement_id is not None:
            replacement = await TeacherMembershipRepository.get_by_id(
                db,
                replacement_id,
                tenant_id=actor.tenant_id,
                lock=True,
                load_account=True,
            )
            if replacement is None:
                raise NotFoundException("Replacement teacher membership not found.")
            if replacement.status != TeacherMembershipStatus.ACTIVE:
                raise BadRequestException("Replacement teacher membership must be active.")

        await db.execute(
            update(ClassRoom)
            .where(
                ClassRoom.tenant_id == actor.tenant_id,
                ClassRoom.teacher_membership_id == membership_id,
            )
            .values(teacher_membership_id=replacement_id)
        )

        assignment_filter = (
            TeacherAssignment.tenant_id == actor.tenant_id,
            TeacherAssignment.teacher_membership_id == membership_id,
            TeacherAssignment.is_active.is_(True),
        )
        if replacement_id is None:
            await db.execute(
                update(TeacherAssignment)
                .where(*assignment_filter)
                .values(is_active=False, effective_to=date.today())
            )
        else:
            await db.execute(
                update(TeacherAssignment)
                .where(*assignment_filter)
                .values(teacher_membership_id=replacement_id)
            )

        legacy_filter = (
            ClassSubjectTeacher.tenant_id == actor.tenant_id,
            ClassSubjectTeacher.teacher_membership_id == membership_id,
            ClassSubjectTeacher.is_active.is_(True),
        )
        if replacement_id is None:
            await db.execute(
                update(ClassSubjectTeacher).where(*legacy_filter).values(is_active=False)
            )
        else:
            await db.execute(
                update(ClassSubjectTeacher)
                .where(*legacy_filter)
                .values(teacher_membership_id=replacement_id)
            )

        return await TeacherMembershipService.end_membership(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherMembershipEndRequest(reason=payload.reason),
        )
