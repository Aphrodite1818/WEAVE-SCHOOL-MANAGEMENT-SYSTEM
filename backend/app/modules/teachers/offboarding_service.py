"""Teacher offboarding impact inspection and atomic responsibility cleanup."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.classes.models import ClassRoom
from app.modules.student_academics.models import TeacherAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.service import StudentAcademicService
from app.modules.student_academics.write_guard import ensure_academic_write_window
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
        today = date.today()
        assignment_count = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(TeacherAssignment)
                    .where(
                        TeacherAssignment.tenant_id == tenant_id,
                        TeacherAssignment.teacher_membership_id == membership_id,
                        or_(
                            TeacherAssignment.effective_to.is_(None),
                            TeacherAssignment.effective_to >= today,
                        ),
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
    async def _create_replacement_assignment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        source: TeacherAssignment,
        replacement_teacher_membership_id: UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> TeacherAssignment:
        try:
            return await StudentAcademicRepository.create_teacher_assignment(
                db,
                TeacherAssignment(
                    tenant_id=tenant_id,
                    class_id=source.class_id,
                    curriculum_subject_id=source.curriculum_subject_id,
                    teacher_membership_id=replacement_teacher_membership_id,
                    effective_from=effective_from,
                    effective_to=effective_to,
                ),
            )
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Replacement teacher assignment overlaps existing assignment history."
            ) from exc

    @staticmethod
    async def end_membership_and_release_responsibilities(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        membership_id: UUID,
        payload: TeacherOffboardingRequest,
    ) -> TeacherMembershipResponse:
        """End a membership while preserving date-effective teaching history.

        Current subject assignments remain historical through the offboarding date.
        Future scheduled assignments have never taken effect, so they are cancelled
        or transferred to the replacement teacher instead of being rewritten as
        ended history.
        """

        await ensure_academic_write_window(db, tenant_id=actor.tenant_id)

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
            await StudentAcademicService._validate_teacher_capability(
                db,
                tenant_id=actor.tenant_id,
                teacher_membership_id=replacement_id,
            )

        today = date.today()
        live_assignments = list(
            (
                await db.execute(
                    select(TeacherAssignment)
                    .where(
                        TeacherAssignment.tenant_id == actor.tenant_id,
                        TeacherAssignment.teacher_membership_id == membership_id,
                        or_(
                            TeacherAssignment.effective_to.is_(None),
                            TeacherAssignment.effective_to >= today,
                        ),
                    )
                    .order_by(TeacherAssignment.effective_from.asc())
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )

        # Class-teacher ownership is a current pointer rather than temporal subject
        # assignment history, so it may be moved directly after validation.
        await db.execute(
            update(ClassRoom)
            .where(
                ClassRoom.tenant_id == actor.tenant_id,
                ClassRoom.teacher_membership_id == membership_id,
            )
            .values(teacher_membership_id=replacement_id)
        )

        for assignment in live_assignments:
            previous_state = assignment.state.value
            original_effective_to = assignment.effective_to

            if assignment.effective_from > today:
                # A scheduled assignment has never been effective. Remove the stale
                # future responsibility before creating an equivalent replacement so
                # the exclusion constraint cannot see overlapping ranges.
                await StudentAcademicRepository.delete_teacher_assignment(db, assignment)

                if replacement_id is None:
                    await StudentAcademicService._record_teacher_assignment_audit(
                        db,
                        tenant_id=actor.tenant_id,
                        assignment_id=None,
                        class_id=assignment.class_id,
                        curriculum_subject_id=assignment.curriculum_subject_id,
                        action="scheduled_assignment_cancelled_for_offboarding",
                        previous_teacher_membership_id=membership_id,
                        new_teacher_membership_id=None,
                        previous_state=previous_state,
                        new_state="deleted",
                        previous_effective_from=assignment.effective_from,
                        previous_effective_to=original_effective_to,
                        acting_admin_id=actor.id,
                        reason=payload.reason,
                    )
                    continue

                replacement_assignment = (
                    await TeacherOffboardingService._create_replacement_assignment(
                        db,
                        tenant_id=actor.tenant_id,
                        source=assignment,
                        replacement_teacher_membership_id=replacement_id,
                        effective_from=assignment.effective_from,
                        effective_to=original_effective_to,
                    )
                )
                await StudentAcademicService._record_teacher_assignment_audit(
                    db,
                    tenant_id=actor.tenant_id,
                    assignment_id=replacement_assignment.id,
                    class_id=replacement_assignment.class_id,
                    curriculum_subject_id=replacement_assignment.curriculum_subject_id,
                    action="scheduled_teacher_reassigned_for_offboarding",
                    previous_teacher_membership_id=membership_id,
                    new_teacher_membership_id=replacement_id,
                    previous_state=previous_state,
                    new_state=replacement_assignment.state.value,
                    previous_effective_from=assignment.effective_from,
                    previous_effective_to=original_effective_to,
                    new_effective_from=replacement_assignment.effective_from,
                    new_effective_to=replacement_assignment.effective_to,
                    acting_admin_id=actor.id,
                    reason=payload.reason,
                )
                continue

            # The outgoing teacher is historically responsible through today. An
            # assignment already ending today needs no range rewrite or successor.
            if original_effective_to is not None and original_effective_to <= today:
                continue

            assignment.effective_to = today
            await StudentAcademicRepository.save_teacher_assignment(db, assignment)

            if replacement_id is None:
                await StudentAcademicService._record_teacher_assignment_audit(
                    db,
                    tenant_id=actor.tenant_id,
                    assignment_id=assignment.id,
                    class_id=assignment.class_id,
                    curriculum_subject_id=assignment.curriculum_subject_id,
                    action="assignment_end_set_for_offboarding",
                    previous_teacher_membership_id=membership_id,
                    new_teacher_membership_id=None,
                    previous_state=previous_state,
                    new_state=assignment.state.value,
                    previous_effective_from=assignment.effective_from,
                    previous_effective_to=original_effective_to,
                    new_effective_from=assignment.effective_from,
                    new_effective_to=assignment.effective_to,
                    acting_admin_id=actor.id,
                    reason=payload.reason,
                )
                continue

            replacement_assignment = (
                await TeacherOffboardingService._create_replacement_assignment(
                    db,
                    tenant_id=actor.tenant_id,
                    source=assignment,
                    replacement_teacher_membership_id=replacement_id,
                    effective_from=today + timedelta(days=1),
                    effective_to=original_effective_to,
                )
            )
            await StudentAcademicService._record_teacher_assignment_audit(
                db,
                tenant_id=actor.tenant_id,
                assignment_id=replacement_assignment.id,
                class_id=assignment.class_id,
                curriculum_subject_id=assignment.curriculum_subject_id,
                action="teacher_reassigned_for_offboarding",
                previous_teacher_membership_id=membership_id,
                new_teacher_membership_id=replacement_id,
                previous_state=previous_state,
                new_state=replacement_assignment.state.value,
                previous_effective_from=assignment.effective_from,
                previous_effective_to=assignment.effective_to,
                new_effective_from=replacement_assignment.effective_from,
                new_effective_to=replacement_assignment.effective_to,
                acting_admin_id=actor.id,
                reason=payload.reason,
            )

        # end_membership owns the final commit. The model-event collector records
        # old-assignment tombstones and replacement creates in that same outer
        # transaction, then dependency-sorts them before allocating sync cursors.
        return await TeacherMembershipService.end_membership(
            db,
            actor=actor,
            membership_id=membership_id,
            payload=TeacherMembershipEndRequest(reason=payload.reason),
        )
