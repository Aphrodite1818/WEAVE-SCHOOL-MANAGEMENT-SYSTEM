"""Authoritative immutable student-enrollment placement service."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.attendance.models import StudentAttendanceRecord, StudentAttendanceSheet
from app.modules.classes.models import AcademicLevel, ClassRoom
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.lifecycle_repository import AcademicSessionLifecycleRepository
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    StudentSubjectResult,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.enrollment_schemas import (
    StudentBatchClassAssignmentRequest,
    StudentClassChangeRequest,
)
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentEnrollment,
    StudentEnrollmentOutcome,
)
from app.modules.students.repository import StudentEnrollmentRepository, StudentRepository
from app.modules.students.schemas import (
    StudentBatchClassAssignmentResponse,
    StudentDetailResponse,
    StudentEnrollmentDetailResponse,
)
from app.modules.students.service import StudentService
from app.modules.tenant_admins.models import TenantAdmin


class StudentEnrollmentService:
    """Own immutable placement history and current-class transitions."""

    @staticmethod
    async def list_history(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> list[StudentEnrollmentDetailResponse]:
        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            student_id,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")

        rows = (
            await db.execute(
                select(StudentEnrollment, ClassRoom, AcademicLevel, AcademicSession)
                .join(
                    AcademicLevel,
                    AcademicLevel.id == StudentEnrollment.academic_level_id,
                )
                .join(
                    AcademicSession,
                    AcademicSession.id == StudentEnrollment.academic_session_id,
                )
                .outerjoin(ClassRoom, ClassRoom.id == StudentEnrollment.class_id)
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
        for enrollment, classroom, level, session in rows:
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
                    class_name=classroom.academic_level_name if classroom else None,
                    class_arm=classroom.arm if classroom else None,
                    academic_level_name=level.name,
                    academic_session_name=session.name,
                )
            )
        return output

    @staticmethod
    async def _segment_dependency_counts(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        enrollment_id: UUID,
        on_or_after: date | None = None,
    ) -> dict[str, int]:
        attendance_filters = [
            StudentAttendanceRecord.tenant_id == tenant_id,
            StudentAttendanceRecord.student_enrollment_id == enrollment_id,
        ]
        if on_or_after is not None:
            attendance_filters.append(StudentAttendanceSheet.attendance_date >= on_or_after)
        attendance_query = (
            select(func.count())
            .select_from(StudentAttendanceRecord)
            .join(
                StudentAttendanceSheet,
                StudentAttendanceSheet.id == StudentAttendanceRecord.sheet_id,
            )
            .where(*attendance_filters)
        )

        result_filters = [
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.student_enrollment_id == enrollment_id,
        ]
        result_query = select(func.count()).select_from(StudentSubjectResult).where(*result_filters)
        if on_or_after is not None:
            result_query = result_query.join(
                AcademicTerm,
                AcademicTerm.id == StudentSubjectResult.academic_term_id,
            ).where(
                AcademicTerm.tenant_id == tenant_id,
                (
                    AcademicTerm.end_date.is_(None)
                    | (AcademicTerm.end_date >= on_or_after)
                ),
            )

        attendance = int((await db.execute(attendance_query)).scalar_one() or 0)
        results = int((await db.execute(result_query)).scalar_one() or 0)
        return {"attendance": attendance, "results": results}

    @staticmethod
    async def _ensure_backdated_split_safe(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        enrollment: StudentEnrollment,
        effective_date: date,
    ) -> None:
        if effective_date >= date.today():
            return
        counts = await StudentEnrollmentService._segment_dependency_counts(
            db,
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            on_or_after=effective_date,
        )
        blockers = {key: value for key, value in counts.items() if value > 0}
        if blockers:
            raise ConflictException(
                "The enrollment cannot be backdated across preserved academic evidence.",
                payload={"dependency_counts": blockers},
            )

    @staticmethod
    async def _current_open_term(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        academic_session_id: UUID,
    ) -> AcademicTerm | None:
        terms, _ = await StudentAcademicRepository.list_terms(
            db,
            tenant_id,
            limit=10,
            statuses={AcademicTermStatus.OPEN},
            is_current=True,
        )
        return next(
            (term for term in terms if term.academic_session_id == academic_session_id),
            None,
        )

    @staticmethod
    async def _department_for_class(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        class_id: UUID | None,
        academic_term_id: UUID,
    ) -> UUID | None:
        if class_id is None:
            return None
        return (
            await db.execute(
                select(ClassTermDepartmentAssignment.department_id).where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == academic_term_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def _ensure_specialization_transfer_safe(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        enrollment: StudentEnrollment,
        target_class: ClassRoom,
    ) -> None:
        term = await StudentEnrollmentService._current_open_term(
            db,
            tenant_id=tenant_id,
            academic_session_id=enrollment.academic_session_id,
        )
        if term is None or enrollment.class_id is None:
            return

        old_department = await StudentEnrollmentService._department_for_class(
            db,
            tenant_id=tenant_id,
            class_id=enrollment.class_id,
            academic_term_id=term.id,
        )
        new_department = await StudentEnrollmentService._department_for_class(
            db,
            tenant_id=tenant_id,
            class_id=target_class.id,
            academic_term_id=term.id,
        )
        if old_department == new_department:
            return

        old_offerings = await CurriculumResolutionService.resolve_curriculum_offerings(
            db,
            tenant_id=tenant_id,
            academic_level_id=enrollment.academic_level_id,
            academic_term_id=term.id,
            department_id=old_department,
        )
        new_offerings = await CurriculumResolutionService.resolve_curriculum_offerings(
            db,
            tenant_id=tenant_id,
            academic_level_id=enrollment.academic_level_id,
            academic_term_id=term.id,
            department_id=new_department,
        )
        old_ids = {row.curriculum_subject_id for row in old_offerings}
        new_ids = {row.curriculum_subject_id for row in new_offerings}
        affected = old_ids.symmetric_difference(new_ids)
        if not affected:
            return

        affected_results = int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentSubjectResult)
                    .where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.student_id == student_id,
                        StudentSubjectResult.academic_term_id == term.id,
                        StudentSubjectResult.curriculum_subject_id.in_(affected),
                    )
                )
            ).scalar_one()
            or 0
        )
        if affected_results:
            raise ConflictException(
                "The class change would alter specialization for subjects with existing results.",
                payload={
                    "dependency_counts": {"affected_results": affected_results},
                    "affected_curriculum_subject_ids": sorted(str(value) for value in affected),
                },
            )

    @staticmethod
    async def _create_segment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
        academic_level_id: UUID,
        class_id: UUID | None,
        academic_session_id: UUID,
        started_on: date,
        outcome: StudentEnrollmentOutcome,
        reason: str,
        acting_admin_id: UUID | None,
    ) -> StudentEnrollment:
        try:
            return await StudentEnrollmentRepository.add(
                db,
                StudentEnrollment(
                    tenant_id=tenant_id,
                    student_id=student_id,
                    academic_level_id=academic_level_id,
                    class_id=class_id,
                    academic_session_id=academic_session_id,
                    started_on=started_on,
                    entry_outcome=outcome,
                    entry_reason=reason,
                    created_by_admin_id=acting_admin_id,
                ),
            )
        except IntegrityError as exc:
            await db.rollback()
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
        acting_admin_id: UUID | None,
    ) -> StudentEnrollment:
        if ended_on < enrollment.started_on:
            raise ConflictException("Enrollment end date cannot precede its start date.")
        enrollment.ended_on = ended_on
        enrollment.exit_outcome = outcome
        enrollment.exit_reason = reason
        enrollment.ended_by_admin_id = acting_admin_id
        return await StudentEnrollmentRepository.save(db, enrollment)

    @staticmethod
    async def change_class(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentClassChangeRequest,
    ) -> StudentDetailResponse:
        tenant_id = actor.tenant_id
        await ensure_academic_write_window(db, tenant_id=tenant_id)

        student = await StudentRepository.get_by_id(db, tenant_id, student_id, lock=True)
        if student is None:
            raise NotFoundException("Student not found.")
        if student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}:
            raise BadRequestException("Only active or suspended students can change class.")

        target_class = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            payload.target_class_id,
            lock=True,
        )
        if target_class is None or not target_class.is_active or target_class.archived_at is not None:
            raise NotFoundException("Target class not found.")

        session = await AcademicSessionLifecycleRepository.get_by_id(
            db,
            tenant_id,
            payload.academic_session_id,
            lock=True,
        )
        if (
            session is None
            or not session.is_current
            or session.status != AcademicSessionStatus.OPEN
        ):
            raise NotFoundException("Academic session not found or not open.")

        current = await StudentEnrollmentRepository.get_current(
            db,
            tenant_id,
            student.id,
            lock=True,
        )
        if current is None:
            raise ConflictException("Student has no current enrollment to change.")
        if current.academic_session_id != session.id:
            raise ConflictException(
                "Class change must affect the student's current academic-session enrollment."
            )
        if target_class.academic_level_id != current.academic_level_id:
            raise BadRequestException("Class change cannot change the student's academic level.")
        if current.class_id == target_class.id:
            raise ConflictException("Student is already in the target class.")
        if payload.effective_date < current.started_on:
            raise BadRequestException("Class-change date cannot precede the current placement.")

        await StudentEnrollmentService._ensure_specialization_transfer_safe(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            enrollment=current,
            target_class=target_class,
        )

        if payload.effective_date == current.started_on:
            dependencies = await StudentEnrollmentService._segment_dependency_counts(
                db,
                tenant_id=tenant_id,
                enrollment_id=current.id,
            )
            blockers = {key: value for key, value in dependencies.items() if value > 0}
            if blockers:
                raise ConflictException(
                    "A used enrollment cannot have its historical class rewritten.",
                    payload={"dependency_counts": blockers},
                )
            current.class_id = target_class.id
            current.entry_outcome = StudentEnrollmentOutcome.RECLASSIFIED
            current.entry_reason = payload.reason
            current.created_by_admin_id = actor.id
            await StudentEnrollmentRepository.save(db, current)
        else:
            await StudentEnrollmentService._ensure_backdated_split_safe(
                db,
                tenant_id=tenant_id,
                enrollment=current,
                effective_date=payload.effective_date,
            )
            await StudentEnrollmentService._close_segment(
                db,
                enrollment=current,
                ended_on=payload.effective_date - timedelta(days=1),
                outcome=StudentEnrollmentOutcome.RECLASSIFIED,
                reason=payload.reason,
                acting_admin_id=actor.id,
            )
            await StudentEnrollmentService._create_segment(
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

        await db.commit()
        await db.refresh(student)
        return await StudentService._build_detail_response(db, student)

    @staticmethod
    async def assign_class_batch(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        payload: StudentBatchClassAssignmentRequest,
    ) -> StudentBatchClassAssignmentResponse:
        """Place currently-unassigned enrollments; never hide a bulk transfer."""

        tenant_id = actor.tenant_id
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        target_class = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            payload.target_class_id,
            lock=True,
        )
        if target_class is None or not target_class.is_active or target_class.archived_at is not None:
            raise NotFoundException("Target class not found.")

        session = await AcademicSessionLifecycleRepository.get_current_open(
            db,
            tenant_id,
            lock=True,
        )
        if session is None:
            raise ConflictException("An open academic session is required for class placement.")

        effective_date = payload.effective_date
        resolved: list[tuple[Student, StudentEnrollment]] = []
        for student_id in payload.student_ids:
            student = await StudentRepository.get_by_id(db, tenant_id, student_id, lock=True)
            if student is None or student.is_archived:
                raise NotFoundException(f"Student {student_id} not found.")
            if student.status not in {AcademicStatus.ACTIVE, AcademicStatus.SUSPENDED}:
                raise ConflictException(
                    f"Student {student.admission_number} is not eligible for class placement."
                )
            enrollment = await StudentEnrollmentRepository.get_current(
                db,
                tenant_id,
                student.id,
                lock=True,
            )
            if enrollment is None:
                raise ConflictException(
                    f"Student {student.admission_number} has no current enrollment."
                )
            if enrollment.academic_session_id != session.id:
                raise ConflictException(
                    f"Student {student.admission_number} is not enrolled in the current session."
                )
            if enrollment.academic_level_id != target_class.academic_level_id:
                raise BadRequestException(
                    f"Student {student.admission_number} is not enrolled in the target class level."
                )
            if enrollment.class_id is not None:
                if enrollment.class_id == target_class.id:
                    raise ConflictException(
                        f"Student {student.admission_number} is already in the target class."
                    )
                raise ConflictException(
                    f"Student {student.admission_number} already has a class; use the class-change endpoint."
                )
            if effective_date < enrollment.started_on:
                raise BadRequestException(
                    f"Class placement for {student.admission_number} cannot predate enrollment."
                )
            resolved.append((student, enrollment))

        for student, enrollment in resolved:
            if effective_date == enrollment.started_on:
                dependencies = await StudentEnrollmentService._segment_dependency_counts(
                    db,
                    tenant_id=tenant_id,
                    enrollment_id=enrollment.id,
                )
                if any(dependencies.values()):
                    raise ConflictException(
                        f"Student {student.admission_number} already has academic evidence on the unassigned enrollment."
                    )
                enrollment.class_id = target_class.id
                enrollment.entry_outcome = StudentEnrollmentOutcome.RECLASSIFIED
                enrollment.entry_reason = payload.reason
                enrollment.created_by_admin_id = actor.id
                await StudentEnrollmentRepository.save(db, enrollment)
                continue

            await StudentEnrollmentService._ensure_backdated_split_safe(
                db,
                tenant_id=tenant_id,
                enrollment=enrollment,
                effective_date=effective_date,
            )
            await StudentEnrollmentService._close_segment(
                db,
                enrollment=enrollment,
                ended_on=effective_date - timedelta(days=1),
                outcome=StudentEnrollmentOutcome.RECLASSIFIED,
                reason=payload.reason,
                acting_admin_id=actor.id,
            )
            await StudentEnrollmentService._create_segment(
                db,
                tenant_id=tenant_id,
                student_id=student.id,
                academic_level_id=enrollment.academic_level_id,
                class_id=target_class.id,
                academic_session_id=enrollment.academic_session_id,
                started_on=effective_date,
                outcome=StudentEnrollmentOutcome.RECLASSIFIED,
                reason=payload.reason,
                acting_admin_id=actor.id,
            )

        await db.commit()
        return StudentBatchClassAssignmentResponse(
            updated_student_ids=[student.id for student, _ in resolved],
            target_class_id=target_class.id,
            updated_count=len(resolved),
        )
