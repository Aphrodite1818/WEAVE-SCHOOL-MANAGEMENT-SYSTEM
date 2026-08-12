"""Teacher offboarding impact inspection and atomic responsibility cleanup."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.service import StudentAcademicService
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
        return TeacherOffboardingImpactResponse(
            membership_id=membership_id,
            class_teacher_assignments=class_teacher_count,
            teacher_assignments=assignment_count,
        )

    @staticmethod
    async def end_membership_and_release_responsibilities(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        membership_id: UUID,
        payload: TeacherOffboardingRequest,
    ) -> TeacherMembershipResponse:
        """End a membership without rewriting teacher-assignment history.

        Subject responsibility is temporal history. Offboarding therefore ends
        each active assignment and, when a replacement is supplied, creates a
        new assignment beginning the following day. This preserves the teacher
        that actually owned historical results and prevents inclusive-date
        overlaps between the old and replacement assignments.
        """

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

        active_assignments = list(
            (
                await db.execute(
                    select(TeacherAssignment)
                    .where(
                        TeacherAssignment.tenant_id == actor.tenant_id,
                        TeacherAssignment.teacher_membership_id == membership_id,
                        TeacherAssignment.is_active.is_(True),
                        TeacherAssignment.effective_to.is_(None),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

        today = date.today()
        replacement_effective_from = today + timedelta(days=1)

        # Validate every subject capability before mutating anything so a single
        # ineligible subject cannot leave a partially offboarded teacher.
        if replacement_id is not None:
            for assignment in active_assignments:
                level_subject = await StudentAcademicRepository.get_level_subject_by_id(
                    db,
                    actor.tenant_id,
                    assignment.level_subject_id,
                    lock=True,
                )
                if level_subject is None:
                    raise NotFoundException("Level subject for teacher assignment not found.")
                await StudentAcademicService._validate_teacher_capability(
                    db,
                    tenant_id=actor.tenant_id,
                    teacher_membership_id=replacement_id,
                    subject_id=level_subject.subject_id,
                )

        # Class-teacher ownership is a current pointer rather than subject
        # assignment history, so it may be moved directly after validation.
        await db.execute(
            update(ClassRoom)
            .where(
                ClassRoom.tenant_id == actor.tenant_id,
                ClassRoom.teacher_membership_id == membership_id,
            )
            .values(teacher_membership_id=replacement_id)
        )

        for assignment in active_assignments:
            if today < assignment.effective_from:
                raise BadRequestException(
                    "Teacher offboarding date cannot be before an assignment start date."
                )

            assignment.is_active = False
            assignment.effective_to = today
            await StudentAcademicRepository.save_teacher_assignment(db, assignment)

            if replacement_id is None:
                await StudentAcademicService._record_teacher_assignment_audit(
                    db,
                    tenant_id=actor.tenant_id,
                    assignment_id=assignment.id,
                    class_id=assignment.class_id,
                    level_subject_id=assignment.level_subject_id,
                    action="assignment_ended_for_offboarding",
                    previous_teacher_membership_id=membership_id,
                    new_teacher_membership_id=None,
                    previous_state="active",
                    new_state="ended",
                    previous_effective_from=assignment.effective_from,
                    previous_effective_to=None,
                    new_effective_from=assignment.effective_from,
                    new_effective_to=today,
                    acting_admin_id=actor.id,
                    reason=payload.reason,
                )
                continue

            replacement_assignment = await StudentAcademicRepository.create_teacher_assignment(
                db,
                TeacherAssignment(
                    tenant_id=actor.tenant_id,
                    class_id=assignment.class_id,
                    level_subject_id=assignment.level_subject_id,
                    teacher_membership_id=replacement_id,
                    is_active=True,
                    effective_from=replacement_effective_from,
                    effective_to=None,
                ),
            )
            await StudentAcademicService._record_teacher_assignment_audit(
                db,
                tenant_id=actor.tenant_id,
                assignment_id=replacement_assignment.id,
                class_id=assignment.class_id,
                level_subject_id=assignment.level_subject_id,
                action="teacher_reassigned_for_offboarding",
                previous_teacher_membership_id=membership_id,
                new_teacher_membership_id=replacement_id,
                previous_state="active",
                new_state="active",
                previous_effective_from=assignment.effective_from,
                previous_effective_to=today,
                new_effective_from=replacement_effective_from,
                new_effective_to=None,
                acting_admin_id=actor.id,
                reason=payload.reason,
            )

        # end_membership owns the final commit, so the responsibility updates and
        # membership lifecycle transition remain one database transaction.
        return await TeacherMembershipService.end_membership(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherMembershipEndRequest(reason=payload.reason),
        )
