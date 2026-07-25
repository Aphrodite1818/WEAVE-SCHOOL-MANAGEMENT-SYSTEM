"""Teacher offboarding impact inspection and atomic responsibility cleanup."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.models import (
    ClassSubjectTeacher,
    TeacherAssignment,
)
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.teachers.schemas import (
    TeacherMembershipEndRequest,
    TeacherMembershipResponse,
)
from app.modules.teachers.service import TeacherMembershipService
from app.modules.tenant_admins.models import TenantAdmin


class TeacherOffboardingImpactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    class_teacher_assignments: int = Field(ge=0)
    teacher_assignments: int = Field(ge=0)
    legacy_class_subject_assignments: int = Field(ge=0)

    @property
    def total_active_responsibilities(self) -> int:
        return (
            self.class_teacher_assignments
            + self.teacher_assignments
            + self.legacy_class_subject_assignments
        )


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
        payload: TeacherMembershipEndRequest,
    ) -> TeacherMembershipResponse:
        # Lock the membership before touching dependent responsibility rows so
        # concurrent assignment or reactivation actions serialize correctly.
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=actor.tenant_id,
            lock=True,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")

        await db.execute(
            update(ClassRoom)
            .where(
                ClassRoom.tenant_id == actor.tenant_id,
                ClassRoom.teacher_membership_id == membership_id,
            )
            .values(teacher_membership_id=None)
        )
        await db.execute(
            update(TeacherAssignment)
            .where(
                TeacherAssignment.tenant_id == actor.tenant_id,
                TeacherAssignment.teacher_membership_id == membership_id,
                TeacherAssignment.is_active.is_(True),
            )
            .values(is_active=False, effective_to=date.today())
        )
        await db.execute(
            update(ClassSubjectTeacher)
            .where(
                ClassSubjectTeacher.tenant_id == actor.tenant_id,
                ClassSubjectTeacher.teacher_membership_id == membership_id,
                ClassSubjectTeacher.is_active.is_(True),
            )
            .values(is_active=False)
        )

        # The existing service owns status validation, session revocation,
        # subscription invalidation, and the transaction commit.
        return await TeacherMembershipService.end_membership(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=payload,
        )
