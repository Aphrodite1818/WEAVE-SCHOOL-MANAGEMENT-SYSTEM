"""Canonical immutable student placement workflow.

Initial class placement is deliberately distinct from reassignment. Academic
results, attendance and CBT evidence remain attached to the enrollment segment
that originally produced them; placement only changes which segment is current.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelDepartment,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.classes.repository import ClassRoomRepository
from app.modules.report_cards.comment_models import StudentTermTeacherComment, TeacherCommentStatus
from app.modules.report_cards.comment_service import ReportCommentService
from app.modules.report_cards.models import ReportCard
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository
from app.modules.student_academics.models import AcademicSession, AcademicSessionStatus, StudentSubjectResult
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.enrollment_schemas import (
    PlacementImpactPreviewRequest,
    PlacementImpactPreviewResponse,
    PlacementImpactSubject,
    StudentAcademicLevelReassignmentRequest,
    StudentClassPlacementRequest,
    StudentClassPlacementResponse,
    StudentClassReassignmentRequest,
)
from app.modules.students.models import (
    AcademicStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
)
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import StudentDetailResponse, StudentEnrollmentDetailResponse
from app.modules.students.service import StudentService
from app.modules.subjects.repository import SubjectRepository
from app.modules.tenant_admins.models import TenantAdmin


class StudentPlacementService:
    """Own placement history, initial class placement, and reassignment."""

    @staticmethod
    async def list_history(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentEnrollmentDetailResponse]:
        student = await StudentRepository.get_by_id(
            db, tenant_id, student_id, include_archived=True
        )
        if student is None:
            raise NotFoundException("Student not found.")
        rows = (
            await db.execute(
                select(StudentEnrollment, ClassRoom, AcademicLevel, AcademicSession, ArmLabel)
                .join(AcademicLevel, AcademicLevel.id == StudentEnrollment.academic_level_id)
                .join(AcademicSession, AcademicSession.id == StudentEnrollment.academic_session_id)
                .outerjoin(
                    ClassRoom,
                    and_(
                        ClassRoom.id == StudentEnrollment.class_id,
                        ClassRoom.tenant_id == tenant_id,
                    ),
                )
                .outerjoin(
                    ArmLabel,
                    and_(
                        ArmLabel.id == ClassRoom.arm_label_id,
                        ArmLabel.tenant_id == tenant_id,
                    ),
                )
                .where(
                    StudentEnrollment.tenant_id == tenant_id,
                    StudentEnrollment.student_id == student_id,
                    AcademicLevel.tenant_id == tenant_id,
                    AcademicSession.tenant_id == tenant_id,
                )
                .order_by(
                    StudentEnrollment.started_on.asc(),
                    StudentEnrollment.created_at.asc(),
                )
            )
        ).all()
        output: list[StudentEnrollmentDetailResponse] = []
        for enrollment, classroom, level, session, arm_label in rows:
            base = StudentEnrollmentDetailResponse.model_validate(enrollment).model_dump(
                exclude={
                    "class_name",
                    "class_arm",
                    "academic_level_name",
                    "academic_session_name",
                }
            )
            output.append(
                StudentEnrollmentDetailResponse(
                    **base,
                    class_name=level.name if classroom else None,
                    class_arm=arm_label.label if arm_label else None,
                    academic_level_name=level.name,
                    academic_session_name=session.name,
                )
            )
        return output

    @staticmethod
    async def _require_open_session(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        academic_session_id: UUID,
    ) -> AcademicSession:
        session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, academic_session_id, lock=True
        )
        if session is None or not session.is_current or session.status != AcademicSessionStatus.OPEN:
            raise NotFoundException("Academic session not found or not open.")
        return session

    @staticmethod
    async def _require_target_class(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        class_id: UUID,
    ) -> ClassRoom:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise NotFoundException("Target class not found.")
        return classroom

    @staticmethod
    async def _create_segment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_level_id: UUID,
        class_id: UUID,
        academic_session_id: UUID,
        started_on: date,
        outcome: StudentEnrollmentOutcome,
        reason: str,
        acting_admin_id: UUID,
    ) -> StudentEnrollment:
        enrollment = StudentEnrollment(
            tenant_id=tenant_id,
            student_id=student_id,
            academic_level_id=academic_level_id,
            class_id=class_id,
            academic_session_id=academic_session_id,
            started_on=started_on,
            entry_outcome=outcome,
            entry_reason=reason,
            created_by_admin_id=acting_admin_id,
        )
        try:
            return await StudentEnrollmentRepository.add(db, enrollment)
        except IntegrityError as exc:
            raise ConflictException(
                "Student enrollment overlaps existing placement history."
            ) from exc

    @staticmethod
    async def _close_segment(
        db: AsyncSession,
        *,
        enrollment: StudentEnrollment,
        ended_on: date,
        outcome: StudentEnrollmentOutcome,
        reason: str,
        acting_admin_id: UUID,
    ) -> None:
        if ended_on < enrollment.started_on:
            raise ConflictException("Placement effective date must follow the current segment start.")
        enrollment.ended_on = ended_on
        enrollment.exit_outcome = outcome
        enrollment.exit_reason = reason
        enrollment.ended_by_admin_id = acting_admin_id
        await StudentEnrollmentRepository.save(db, enrollment)

    @staticmethod
    async def _invalidate_derived_context(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_session_id: UUID,
    ) -> None:
        await ReportCommentService.invalidate_for_placement_change(
            db,
            tenant_id=tenant_id,
            student_id=student_id,
            academic_session_id=academic_session_id,
        )
        cards = list(
            (
                await db.execute(
                    select(ReportCard).where(
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.student_id == student_id,
                        ReportCard.academic_session_id == academic_session_id,
                        ReportCard.superseded_at.is_(None),
                    )
                )
            ).scalars()
        )
        for card in cards:
            card.is_outdated = True
            db.add(card)

    @staticmethod
    async def place_class(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        payload: StudentClassPlacementRequest,
    ) -> StudentClassPlacementResponse:
        """Bulk-place only unassigned enrollments; academic evidence never blocks this."""

        tenant_id = actor.tenant_id
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        session = await StudentPlacementService._require_open_session(
            db, tenant_id=tenant_id, academic_session_id=payload.academic_session_id
        )
        target_class = await StudentPlacementService._require_target_class(
            db, tenant_id=tenant_id, class_id=payload.target_class_id
        )
        if target_class.academic_level_id != payload.academic_level_id:
            raise BadRequestException("Target class must belong to the selected academic level.")

        placed_ids: list[UUID] = []
        effective_date = date.today()
        for student_id in payload.student_ids:
            student = await StudentRepository.get_by_id(db, tenant_id, student_id, lock=True)
            if student is None:
                raise NotFoundException(f"Student {student_id} not found.")
            if student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}:
                raise BadRequestException("Only active or suspended students can be placed.")
            current = await StudentEnrollmentRepository.get_current(
                db, tenant_id, student.id, lock=True
            )
            if current is None or current.academic_session_id != session.id:
                raise ConflictException(
                    "Student has no current enrollment for the selected academic session."
                )
            if current.academic_level_id != payload.academic_level_id:
                raise BadRequestException(
                    "Class placement cannot change the student's academic level."
                )
            if current.class_id is not None:
                raise ConflictException(
                    "Student is already classed; use Reassign Class instead."
                )

            # A fresh/today-or-future enrollment has no meaningful unassigned time
            # to preserve. Mutate only class_id and retain ENROLLED/PROMOTED/etc.
            if current.started_on >= effective_date:
                current.class_id = target_class.id
                await StudentEnrollmentRepository.save(db, current)
            else:
                # Preserve the real unassigned interval as its own immutable segment.
                reason = "Initial class placement"
                await StudentPlacementService._close_segment(
                    db,
                    enrollment=current,
                    ended_on=effective_date - timedelta(days=1),
                    outcome=StudentEnrollmentOutcome.CLASS_PLACED,
                    reason=reason,
                    acting_admin_id=actor.id,
                )
                await StudentPlacementService._create_segment(
                    db,
                    tenant_id=tenant_id,
                    student_id=student.id,
                    academic_level_id=current.academic_level_id,
                    class_id=target_class.id,
                    academic_session_id=current.academic_session_id,
                    started_on=effective_date,
                    outcome=StudentEnrollmentOutcome.CLASS_PLACED,
                    reason=reason,
                    acting_admin_id=actor.id,
                )
            placed_ids.append(student.id)

        await db.commit()
        return StudentClassPlacementResponse(
            placed_student_ids=placed_ids,
            target_class_id=target_class.id,
            placed_count=len(placed_ids),
        )

    @staticmethod
    async def reassign_class(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentClassReassignmentRequest,
    ) -> StudentDetailResponse:
        tenant_id = actor.tenant_id
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        student = await StudentRepository.get_by_id(db, tenant_id, student_id, lock=True)
        if student is None:
            raise NotFoundException("Student not found.")
        if student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}:
            raise BadRequestException("Only active or suspended students can be reassigned.")
        session = await StudentPlacementService._require_open_session(
            db, tenant_id=tenant_id, academic_session_id=payload.academic_session_id
        )
        target_class = await StudentPlacementService._require_target_class(
            db, tenant_id=tenant_id, class_id=payload.target_class_id
        )
        current = await StudentEnrollmentRepository.get_current(
            db, tenant_id, student.id, lock=True
        )
        if current is None or current.academic_session_id != session.id:
            raise ConflictException("Student has no current enrollment for this session.")
        if current.class_id is None:
            raise ConflictException("Unassigned students must use Class Placement.")
        if target_class.academic_level_id != current.academic_level_id:
            raise BadRequestException("Reassign Class cannot change academic level.")
        if target_class.id == current.class_id:
            raise ConflictException("Student is already in the target class.")
        if payload.effective_date <= current.started_on:
            raise BadRequestException(
                "Reassignment effective date must be after the current placement start."
            )

        await StudentPlacementService._close_segment(
            db,
            enrollment=current,
            ended_on=payload.effective_date - timedelta(days=1),
            outcome=StudentEnrollmentOutcome.RECLASSIFIED,
            reason=payload.reason,
            acting_admin_id=actor.id,
        )
        await StudentPlacementService._create_segment(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            academic_level_id=current.academic_level_id,
            class_id=target_class.id,
            academic_session_id=current.academic_session_id,
            started_on=payload.effective_date,
            outcome=StudentEnrollmentOutcome.RECLASSIFIED,
            reason=payload.reason,
            acting_admin_id=actor.id,
        )
        await StudentPlacementService._invalidate_derived_context(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            academic_session_id=current.academic_session_id,
        )
        await db.commit()
        return await StudentService.get_student_profile(db, actor, student.id)

    @staticmethod
    async def reassign_academic_level(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentAcademicLevelReassignmentRequest,
    ) -> StudentDetailResponse:
        tenant_id = actor.tenant_id
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        student = await StudentRepository.get_by_id(db, tenant_id, student_id, lock=True)
        if student is None:
            raise NotFoundException("Student not found.")
        if student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}:
            raise BadRequestException("Only active or suspended students can be reassigned.")
        session = await StudentPlacementService._require_open_session(
            db, tenant_id=tenant_id, academic_session_id=payload.academic_session_id
        )
        target_class = await StudentPlacementService._require_target_class(
            db, tenant_id=tenant_id, class_id=payload.target_class_id
        )
        if target_class.academic_level_id != payload.target_academic_level_id:
            raise BadRequestException("Target class does not belong to the target academic level.")
        current = await StudentEnrollmentRepository.get_current(
            db, tenant_id, student.id, lock=True
        )
        if current is None or current.academic_session_id != session.id:
            raise ConflictException("Student has no current enrollment for this session.")
        if current.academic_level_id == payload.target_academic_level_id:
            raise BadRequestException("Use Reassign Class for a same-level move.")
        if payload.effective_date <= current.started_on:
            raise BadRequestException(
                "Reassignment effective date must be after the current placement start."
            )

        await StudentPlacementService._close_segment(
            db,
            enrollment=current,
            ended_on=payload.effective_date - timedelta(days=1),
            outcome=StudentEnrollmentOutcome.LEVEL_REASSIGNED,
            reason=payload.reason,
            acting_admin_id=actor.id,
        )
        await StudentPlacementService._create_segment(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            academic_level_id=payload.target_academic_level_id,
            class_id=target_class.id,
            academic_session_id=current.academic_session_id,
            started_on=payload.effective_date,
            outcome=StudentEnrollmentOutcome.LEVEL_REASSIGNED,
            reason=payload.reason,
            acting_admin_id=actor.id,
        )
        await StudentPlacementService._invalidate_derived_context(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            academic_session_id=current.academic_session_id,
        )
        await db.commit()
        return await StudentService.get_student_profile(db, actor, student.id)

    @staticmethod
    async def _department_name(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        class_id: UUID | None,
        academic_term_id: UUID,
    ) -> str | None:
        if class_id is None:
            return None
        return (
            await db.execute(
                select(Department.name)
                .select_from(ClassTermDepartmentAssignment)
                .join(
                    AcademicLevelDepartment,
                    and_(
                        AcademicLevelDepartment.id
                        == ClassTermDepartmentAssignment.academic_level_department_id,
                        AcademicLevelDepartment.tenant_id == tenant_id,
                    ),
                )
                .join(
                    Department,
                    and_(
                        Department.id == AcademicLevelDepartment.department_id,
                        Department.tenant_id == tenant_id,
                    ),
                )
                .where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == academic_term_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _preview_subjects(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        items: list,
        selected_ids: set[UUID],
    ) -> list[PlacementImpactSubject]:
        output: list[PlacementImpactSubject] = []
        for item in items:
            if item.curriculum_subject_id not in selected_ids:
                continue
            subject = await SubjectRepository.get_subject_by_id(db, tenant_id, item.subject_id)
            output.append(
                PlacementImpactSubject(
                    curriculum_subject_id=item.curriculum_subject_id,
                    subject_id=item.subject_id,
                    subject_name=subject.name if subject else str(item.subject_id),
                )
            )
        return output

    @staticmethod
    async def impact_preview(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: PlacementImpactPreviewRequest,
    ) -> PlacementImpactPreviewResponse:
        tenant_id = actor.tenant_id
        student = await StudentRepository.get_by_id(db, tenant_id, student_id)
        if student is None:
            raise NotFoundException("Student not found.")
        current = await StudentEnrollmentRepository.get_current(db, tenant_id, student.id)
        if current is None or current.academic_session_id != payload.academic_session_id:
            raise ConflictException("Student has no current enrollment for this session.")
        target_class = await StudentPlacementService._require_target_class(
            db, tenant_id=tenant_id, class_id=payload.target_class_id
        )
        if target_class.academic_level_id != payload.target_academic_level_id:
            raise BadRequestException("Target class does not belong to target academic level.")

        old_subjects = (
            await CurriculumResolutionService.resolve_class_subjects(
                db,
                tenant_id=tenant_id,
                class_id=current.class_id,
                academic_term_id=payload.academic_term_id,
            )
            if current.class_id is not None
            else []
        )
        new_subjects = await CurriculumResolutionService.resolve_class_subjects(
            db,
            tenant_id=tenant_id,
            class_id=target_class.id,
            academic_term_id=payload.academic_term_id,
        )
        old_ids = {item.curriculum_subject_id for item in old_subjects}
        new_ids = {item.curriculum_subject_id for item in new_subjects}
        result_ids = set(
            (
                await db.execute(
                    select(StudentSubjectResult.curriculum_subject_id).where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.student_id == student.id,
                        StudentSubjectResult.academic_session_id == payload.academic_session_id,
                        StudentSubjectResult.academic_term_id == payload.academic_term_id,
                    )
                )
            ).scalars()
        )
        current_department = await StudentPlacementService._department_name(
            db,
            tenant_id=tenant_id,
            class_id=current.class_id,
            academic_term_id=payload.academic_term_id,
        )
        destination_department = await StudentPlacementService._department_name(
            db,
            tenant_id=tenant_id,
            class_id=target_class.id,
            academic_term_id=payload.academic_term_id,
        )
        teacher_comment_exists = (
            await db.execute(
                select(StudentTermTeacherComment.id).where(
                    StudentTermTeacherComment.tenant_id == tenant_id,
                    StudentTermTeacherComment.student_id == student.id,
                    StudentTermTeacherComment.academic_session_id == payload.academic_session_id,
                    StudentTermTeacherComment.academic_term_id == payload.academic_term_id,
                    StudentTermTeacherComment.status.in_(
                        [TeacherCommentStatus.SUBMITTED, TeacherCommentStatus.NEEDS_REVIEW]
                    ),
                ).limit(1)
            )
        ).scalar_one_or_none() is not None
        report_exists = (
            await db.execute(
                select(ReportCard.id).where(
                    ReportCard.tenant_id == tenant_id,
                    ReportCard.student_id == student.id,
                    ReportCard.academic_session_id == payload.academic_session_id,
                    ReportCard.academic_term_id == payload.academic_term_id,
                    ReportCard.superseded_at.is_(None),
                ).limit(1)
            )
        ).scalar_one_or_none() is not None

        warnings: list[str] = []
        historical_only = old_ids - new_ids
        destination_without_scores = new_ids - result_ids
        if historical_only:
            warnings.append(
                "Some existing results will remain preserved as historical-only in the destination context."
            )
        if teacher_comment_exists:
            warnings.append("The current teacher comment will require review after reassignment.")
        if report_exists:
            warnings.append(
                "Existing report cards will be marked affected; published revisions remain immutable."
            )
        warnings.append("Class ranking context may change and will be recalculated only on a new draft.")

        return PlacementImpactPreviewResponse(
            current_academic_level_id=current.academic_level_id,
            current_class_id=current.class_id,
            destination_academic_level_id=payload.target_academic_level_id,
            destination_class_id=target_class.id,
            current_department=current_department,
            destination_department=destination_department,
            department_changed=current_department != destination_department,
            subjects_remaining_applicable=await StudentPlacementService._preview_subjects(
                db,
                tenant_id=tenant_id,
                items=new_subjects,
                selected_ids=old_ids & new_ids,
            ),
            subjects_becoming_historical_only=await StudentPlacementService._preview_subjects(
                db,
                tenant_id=tenant_id,
                items=old_subjects,
                selected_ids=historical_only,
            ),
            destination_subjects_without_scores=await StudentPlacementService._preview_subjects(
                db,
                tenant_id=tenant_id,
                items=new_subjects,
                selected_ids=destination_without_scores,
            ),
            teacher_comment_requires_review=teacher_comment_exists,
            report_card_affected=report_exists,
            warnings=warnings,
        )
