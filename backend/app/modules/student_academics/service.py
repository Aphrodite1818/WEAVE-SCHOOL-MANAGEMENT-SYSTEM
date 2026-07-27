"""Canonical academic setup, assignment, score, and subject-card services."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.classes.repository import ClassRoomRepository
from app.modules.parents.models import ParentMembership
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    AcademicSessionCreate,
    AcademicSessionUpdate,
    AcademicTermCreate,
    AcademicTermUpdate,
    ClassSubjectCreate,
    ClassSubjectResponse,
    ClassSubjectTeacherCreate,
    ClassSubjectTeacherResponse,
    ClassSubjectTeacherUpdate,
    GradingScaleCreate,
    GradingScaleUpdate,
    StudentSubjectCardContextResponse,
    StudentSubjectCardListResponse,
    StudentSubjectCardResponse,
    StudentSubjectResultReopenRequest,
    StudentSubjectResultResponse,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
    TeacherAssignmentCreate,
    TeacherAssignmentDelete,
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
    ClassSubjectUpdate,
)
from app.modules.students.models import Student, StudentParentLinkStatus
from app.modules.students.repository import StudentParentLinkRepository, StudentRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import TeacherAccountStatus, TeacherMembership, TeacherMembershipStatus
from app.modules.teachers.repository import (
    TeacherMembershipRepository,
    TeacherMembershipSubjectRepository,
)
from app.modules.tenant_admins.models import TenantAdmin


class StudentAcademicService:
    """Business rules for tenant academic setup and score ownership."""

    _RESULT_FORWARD_TRANSITIONS = {
        AcademicResultStatus.DRAFT: AcademicResultStatus.SUBMITTED,
        AcademicResultStatus.SUBMITTED: AcademicResultStatus.APPROVED,
        AcademicResultStatus.APPROVED: AcademicResultStatus.LOCKED,
    }
    _RESULT_EDITABLE_STATUSES = {AcademicResultStatus.DRAFT}
    _RESULT_UPSERT_STATUSES = {
        AcademicResultStatus.DRAFT,
        AcademicResultStatus.SUBMITTED,
    }

    @staticmethod
    async def _build_class_subject_response(
        db: AsyncSession,
        class_subject: ClassSubject,
    ) -> ClassSubjectResponse:
        subject = await SubjectRepository.get_subject_by_id(
            db,
            class_subject.tenant_id,
            class_subject.subject_id,
        )
        classroom = await ClassRoomRepository.get_by_id(
            db,
            class_subject.tenant_id,
            class_subject.class_id,
        )
        lifecycle_status = (
            "archived"
            if class_subject.archived_at is not None
            else "active"
            if class_subject.is_active
            else "inactive"
        )
        class_is_archived = classroom.archived_at is not None if classroom else None
        subject_is_archived = subject.archived_at is not None if subject else None
        class_is_active = classroom.is_active if classroom else None
        subject_is_active = subject.is_active if subject else None
        activation_blocker = None
        if class_subject.archived_at is not None:
            activation_blocker = "Restore the mapping before activation."
        elif classroom is None:
            activation_blocker = "Class not found."
        elif not classroom.is_active:
            activation_blocker = "Class must be active before activating this mapping."
        elif classroom.archived_at is not None:
            activation_blocker = "Class must be restored before activating this mapping."
        elif subject is None:
            activation_blocker = "Subject not found."
        elif not subject.is_active:
            activation_blocker = "Subject must be active before activating this mapping."
        elif subject.archived_at is not None:
            activation_blocker = "Subject must be restored before activating this mapping."
        return ClassSubjectResponse(
            id=class_subject.id,
            tenant_id=class_subject.tenant_id,
            class_id=class_subject.class_id,
            subject_id=class_subject.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            is_core=class_subject.is_core,
            is_active=class_subject.is_active,
            lifecycle_status=lifecycle_status,
            archived_at=class_subject.archived_at,
            archived_by_admin_id=class_subject.archived_by_admin_id,
            class_is_active=class_is_active,
            class_is_archived=class_is_archived,
            subject_is_active=subject_is_active,
            subject_is_archived=subject_is_archived,
            can_activate=activation_blocker is None,
            activation_blocker=activation_blocker,
            created_at=class_subject.created_at,
            updated_at=class_subject.updated_at,
        )

    @staticmethod
    async def _set_compatibility_class_subject_teachers_active(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        is_active: bool,
    ) -> None:
        rows = await StudentAcademicRepository.list_class_subject_teachers_for_class_subject(
            db,
            tenant_id,
            class_subject_id,
        )
        for row in rows:
            row.is_active = is_active
            await StudentAcademicRepository.save_class_subject_teacher(db, row)

    @staticmethod
    async def _class_subject_dependency_counts(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> dict[str, int]:
        return {
            "active_teacher_assignments": await StudentAcademicRepository.count_teacher_assignments_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
                active_only=True,
            ),
            "teacher_assignment_history": await StudentAcademicRepository.count_teacher_assignments_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
            ),
            "student_results": await StudentAcademicRepository.count_results_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
            ),
            "report_card_lines": await StudentAcademicRepository.count_report_card_lines_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
            ),
            "compatibility_teacher_rows": await StudentAcademicRepository.count_class_subject_teachers_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
            ),
            "active_compatibility_teacher_rows": await StudentAcademicRepository.count_class_subject_teachers_for_class_subject(
                db,
                tenant_id,
                class_subject_id,
                active_only=True,
            ),
        }

    @staticmethod
    async def _validate_teacher_capability(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> TeacherMembership:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            teacher_membership_id,
            tenant_id=tenant_id,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")
        if membership.status != TeacherMembershipStatus.ACTIVE:
            raise BadRequestException("Teacher membership is not active.")
        if (
            membership.teacher_account.account_status != TeacherAccountStatus.ACTIVE
            or not membership.teacher_account.is_active
        ):
            raise BadRequestException("Teacher account is not active.")
        # Subject-specific approval requirement is removed from the pre-assignment validation stage.
        return membership

    @staticmethod
    async def _ensure_compatibility_assignment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_subject: ClassSubject,
        teacher_membership_id: uuid.UUID,
        is_active: bool,
    ) -> ClassSubjectTeacher:
        row = (
            await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                db,
                tenant_id,
                class_subject.class_id,
                class_subject.subject_id,
            )
        )
        if row is None:
            row = ClassSubjectTeacher(
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_membership_id=teacher_membership_id,
                is_core=class_subject.is_core,
                sort_order=0,
                is_active=is_active,
            )
            return await StudentAcademicRepository.create_class_subject_teacher(
                db,
                row,
            )
        row.teacher_membership_id = teacher_membership_id
        row.is_core = class_subject.is_core
        row.is_active = is_active
        return await StudentAcademicRepository.save_class_subject_teacher(db, row)

    @staticmethod
    async def _build_teacher_assignment_response(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            assignment.tenant_id,
            assignment.class_subject_id,
        )
        classroom = None
        subject = None
        if class_subject is not None:
            classroom = await ClassRoomRepository.get_by_id(
                db,
                assignment.tenant_id,
                class_subject.class_id,
            )
            subject = await SubjectRepository.get_subject_by_id(
                db,
                assignment.tenant_id,
                class_subject.subject_id,
            )
        teacher = await TeacherMembershipRepository.get_by_id(
            db,
            assignment.teacher_membership_id,
            tenant_id=assignment.tenant_id,
            load_account=True,
        )
        teacher_name = None
        if teacher is not None:
            teacher_name = " ".join(
                part
                for part in [
                    teacher.teacher_account.first_name,
                    teacher.teacher_account.last_name,
                ]
                if part
            ) or None
        return TeacherAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
            teacher_membership_id=assignment.teacher_membership_id,
            class_id=class_subject.class_id if class_subject else None,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=class_subject.subject_id if class_subject else None,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_name=teacher_name,
            teacher_staff_id=teacher.staff_id if teacher else None,
            is_active=assignment.is_active,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    @staticmethod
    async def create_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        payload: ClassSubjectCreate,
    ) -> ClassSubjectResponse:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise NotFoundException("Class not found or inactive.")
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            payload.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise NotFoundException("Subject not found or inactive.")
        existing = (
            await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                db,
                tenant_id,
                class_id,
                payload.subject_id,
            )
        )
        if existing is not None:
            if existing.archived_at is not None:
                raise ConflictException(
                    "This class-subject mapping is archived. Restore it before creating a new mapping."
                )
            if existing.is_active:
                raise ConflictException(
                    "This subject is already offered by the class."
                )
            raise ConflictException(
                "This class-subject mapping is inactive. Activate it instead of creating a new mapping."
            )
        row = await StudentAcademicRepository.create_class_subject(
            db,
            ClassSubject(
                tenant_id=tenant_id,
                class_id=class_id,
                subject_id=payload.subject_id,
                is_core=payload.is_core,
                is_active=True,
                archived_at=None,
                archived_by_admin_id=None,
            ),
        )
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def list_class_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        class_id: uuid.UUID | None = None,
        active_only: bool = False,
        include_archived: bool = False,
        lifecycle_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ClassSubjectResponse], int]:
        rows, total = await StudentAcademicRepository.list_class_subjects(
            db,
            tenant_id,
            class_id=class_id,
            active_only=active_only,
            include_archived=include_archived,
            lifecycle_status=lifecycle_status,
            skip=skip,
            limit=limit,
        )
        return [
            await StudentAcademicService._build_class_subject_response(db, row)
            for row in rows
        ], total

    @staticmethod
    async def deactivate_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.archived_at is not None:
            raise ConflictException(
                "Archived records cannot be deactivated. Restore them first."
            )
        if not row.is_active:
            return await StudentAcademicService._build_class_subject_response(db, row)
        counts = await StudentAcademicService._class_subject_dependency_counts(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
        )
        if counts["active_teacher_assignments"]:
            raise ConflictException(
                "Active teacher assignments must be ended before deactivating this class-subject mapping.",
                payload={"dependency_counts": counts},
            )
        row.is_active = False
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await StudentAcademicService._set_compatibility_class_subject_teachers_active(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
            is_active=False,
        )
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def activate_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.archived_at is not None:
            raise ConflictException("Archived class subjects must be restored before activation.")
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, row.class_id)
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Classroom must be active before activating this class subject.")
        subject = await SubjectRepository.get_subject_by_id(db, tenant_id, row.subject_id)
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before activating this class subject.")
        if row.is_active:
            return await StudentAcademicService._build_class_subject_response(db, row)
        row.is_active = True
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def update_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        payload: ClassSubjectUpdate,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.archived_at is not None:
            raise ConflictException("Archived class-subject mappings cannot be updated.")
        row.is_core = payload.is_core
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def archive_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        admin_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.archived_at is not None:
            raise ConflictException("Class-subject mapping is already archived.")
        if row.is_active:
            raise ConflictException(
                "Active class-subject mappings cannot be archived. Deactivate the mapping first."
            )
        counts = await StudentAcademicService._class_subject_dependency_counts(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
        )
        if counts["active_teacher_assignments"] or counts["active_compatibility_teacher_rows"]:
            raise ConflictException(
                "End active teacher state before archiving this class-subject mapping.",
                payload={"dependency_counts": counts},
            )
        row.is_active = False
        row.archived_at = datetime.now(timezone.utc)
        row.archived_by_admin_id = admin_id
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await StudentAcademicService._set_compatibility_class_subject_teachers_active(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
            is_active=False,
        )
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def restore_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.archived_at is None:
            return await StudentAcademicService._build_class_subject_response(db, row)
        row.archived_at = None
        row.archived_by_admin_id = None
        row.is_active = False
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await StudentAcademicService._set_compatibility_class_subject_teachers_active(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
            is_active=False,
        )
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def delete_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        row = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if row is None:
            raise NotFoundException("Class subject not found.")
        if row.is_active:
            raise ConflictException("Active class-subject mappings cannot be hard-deleted. Deactivate the mapping first.")
        if row.archived_at is not None:
            raise ConflictException("Archived class-subject mappings cannot be hard-deleted. Restore them first.")
        counts = await StudentAcademicService._class_subject_dependency_counts(
            db,
            tenant_id=tenant_id,
            class_subject_id=row.id,
        )
        blocking_counts = {
            "teacher_assignment_history": counts["teacher_assignment_history"],
            "student_results": counts["student_results"],
            "report_card_lines": counts["report_card_lines"],
        }
        if any(blocking_counts.values()):
            raise ConflictException(
                "Class-subject mapping has dependencies and cannot be hard-deleted.",
                payload={"dependency_counts": counts},
            )
        response = await StudentAcademicService._build_class_subject_response(db, row)
        compatibility_rows = await StudentAcademicRepository.list_class_subject_teachers_for_class_subject(
            db,
            tenant_id,
            row.id,
        )
        for compatibility_row in compatibility_rows:
            await StudentAcademicRepository.delete_class_subject_teacher(db, compatibility_row)
        await StudentAcademicRepository.delete_class_subject(db, row)
        await db.commit()
        return response

    @staticmethod
    async def create_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TeacherAssignmentCreate,
        class_subject_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        resolved_class_subject_id = class_subject_id or payload.class_subject_id
        if resolved_class_subject_id is None:
            raise BadRequestException("class_subject_id is required.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            resolved_class_subject_id,
        )
        if (
            class_subject is None
            or not class_subject.is_active
            or class_subject.archived_at is not None
        ):
            raise NotFoundException("Class subject not found or inactive.")
        classroom = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            class_subject.class_id,
        )
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Classroom must be active before assigning a teacher.")
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            class_subject.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before assigning a teacher.")
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        active = (
            await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db,
                tenant_id,
                class_subject.id,
            )
        )
        if active is not None:
            raise ConflictException(
                "An active teacher assignment already exists for this class subject."
            )
        effective_from = payload.effective_from or date.today()
        existing_assignments = await StudentAcademicRepository.list_teacher_assignments_for_class_subject(
            db,
            tenant_id,
            class_subject.id,
            lock=True,
        )
        for existing in existing_assignments:
            if existing.effective_to is None or existing.effective_to >= effective_from:
                raise ConflictException(
                    "Teacher assignment effective date overlaps existing assignment history."
                )
        assignment = await StudentAcademicRepository.create_teacher_assignment(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=effective_from,
                effective_to=None,
            ),
        )
        await StudentAcademicService._ensure_compatibility_assignment(
            db,
            tenant_id=tenant_id,
            class_subject=class_subject,
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
        )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(
            db,
            assignment,
        )

    @staticmethod
    async def end_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentEnd,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
            lock=True,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        if not assignment.is_active:
            if assignment.effective_to is None:
                effective_to = payload.effective_to or date.today()
                if effective_to < assignment.effective_from:
                    raise ConflictException("Assignment end date cannot be before its start date.")
                assignment.effective_to = effective_to
                assignment = await StudentAcademicRepository.save_teacher_assignment(
                    db,
                    assignment,
                )
                await db.commit()
                return await StudentAcademicService._build_teacher_assignment_response(
                    db,
                    assignment,
                )
            if payload.effective_to is not None and payload.effective_to != assignment.effective_to:
                raise ConflictException(
                    "Teacher assignment is already ended with a different effective date."
                )
            return await StudentAcademicService._build_teacher_assignment_response(
                db,
                assignment,
            )
        effective_to = payload.effective_to or date.today()
        if effective_to < assignment.effective_from:
            raise ConflictException("Assignment end date cannot be before its start date.")
        assignment.is_active = False
        assignment.effective_to = effective_to
        assignment = await StudentAcademicRepository.save_teacher_assignment(
            db,
            assignment,
        )
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            assignment.class_subject_id,
        )
        if class_subject is not None:
            await StudentAcademicService._ensure_compatibility_assignment(
                db,
                tenant_id=tenant_id,
                class_subject=class_subject,
                teacher_membership_id=assignment.teacher_membership_id,
                is_active=False,
            )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(
            db,
            assignment,
        )

    @staticmethod
    async def reassign_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentReassign,
    ) -> TeacherAssignmentResponse:
        current = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
            lock=True,
        )
        if current is None:
            raise NotFoundException("Teacher assignment not found.")
        if not current.is_active or current.effective_to is not None:
            raise ConflictException("Only the current active teacher assignment can be reassigned.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            current.class_subject_id,
        )
        if (
            class_subject is None
            or not class_subject.is_active
            or class_subject.archived_at is not None
        ):
            raise NotFoundException("Class subject not found or inactive.")
        classroom = await ClassRoomRepository.get_by_id(
            db,
            tenant_id,
            class_subject.class_id,
        )
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Classroom must be active before reassigning a teacher.")
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            class_subject.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before reassigning a teacher.")
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db,
            tenant_id,
            class_subject.id,
            lock=True,
        )
        if active is None or active.id != current.id:
            raise ConflictException(
                "The selected assignment is no longer the active teacher assignment."
            )
        if current.teacher_membership_id == payload.teacher_membership_id:
            raise ConflictException("This teacher is already assigned.")
        effective_from = payload.effective_from or date.today()
        if effective_from <= current.effective_from:
            raise ConflictException("Replacement effective date must be after the current assignment start date.")
        later_assignments = await StudentAcademicRepository.get_later_teacher_assignments(
            db,
            tenant_id,
            class_subject.id,
            current.effective_from,
            exclude_id=current.id,
            lock=True,
        )
        if later_assignments:
            raise ConflictException("Cannot reassign because later assignment history already exists.")

        current.is_active = False
        current.effective_to = effective_from - timedelta(days=1)
        if current.effective_to < current.effective_from:
            raise ConflictException("Replacement effective date creates an invalid assignment range.")
        await StudentAcademicRepository.save_teacher_assignment(db, current)

        replacement = await StudentAcademicRepository.create_teacher_assignment(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=effective_from,
                effective_to=None,
            ),
        )
        await StudentAcademicService._ensure_compatibility_assignment(
            db,
            tenant_id=tenant_id,
            class_subject=class_subject,
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
        )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(
            db,
            replacement,
        )

    @staticmethod
    async def delete_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentDelete,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
            lock=True,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        if assignment.is_active:
            raise ConflictException("End the teacher assignment before deleting it.")
        if await StudentAcademicRepository.has_teacher_assignment_dependencies(
            db,
            tenant_id,
            assignment.id,
        ):
            raise ConflictException(
                "This teacher assignment is referenced by academic records and cannot be deleted. End the assignment instead."
            )
        later_assignments = await StudentAcademicRepository.get_later_teacher_assignments(
            db,
            tenant_id,
            assignment.class_subject_id,
            assignment.effective_from,
            exclude_id=assignment.id,
            lock=True,
        )
        if later_assignments:
            raise ConflictException(
                "This teacher assignment has later assignment history and cannot be deleted."
            )
        response = await StudentAcademicService._build_teacher_assignment_response(
            db,
            assignment,
        )
        await StudentAcademicRepository.delete_teacher_assignment(db, assignment)
        await db.commit()
        return response

    @staticmethod
    async def list_teacher_assignment_responses(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TeacherAssignmentResponse], int]:
        rows, total = await StudentAcademicRepository.list_teacher_assignment_rows(
            db,
            tenant_id,
            teacher_id=teacher_id,
            class_id=class_id,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )
        return [
            await StudentAcademicService._build_teacher_assignment_response(db, row)
            for row in rows
        ], total

    @staticmethod
    async def assign_subject_to_class(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: ClassSubjectTeacherCreate,
    ) -> ClassSubjectTeacherResponse:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, payload.class_id)
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise NotFoundException("Class not found or inactive.")
        subject = await SubjectRepository.get_subject_by_id(db, tenant_id, payload.subject_id)
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise NotFoundException("Subject not found or inactive.")
        class_subject = (
            await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                db,
                tenant_id,
                payload.class_id,
                payload.subject_id,
            )
        )
        if class_subject is not None and class_subject.archived_at is not None:
            raise ConflictException(
                "This class subject is archived. Restore it before activation."
            )
        if class_subject is None:
            class_subject = await StudentAcademicRepository.create_class_subject(
                db,
                ClassSubject(
                    tenant_id=tenant_id,
                    class_id=payload.class_id,
                    subject_id=payload.subject_id,
                    is_core=payload.is_core,
                    is_active=True,
                    archived_at=None,
                    archived_by_admin_id=None,
                ),
            )
        assignment = await StudentAcademicService.create_teacher_assignment(
            db,
            tenant_id,
            TeacherAssignmentCreate(
                teacher_membership_id=payload.teacher_membership_id,
                class_subject_id=class_subject.id,
            ),
        )
        row = (
            await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                db,
                tenant_id,
                payload.class_id,
                payload.subject_id,
            )
        )
        if row is None:
            raise ConflictException("Assignment compatibility row was not created.")
        row.sort_order = payload.sort_order
        row.is_active = payload.is_active
        row.is_core = payload.is_core
        await StudentAcademicRepository.save_class_subject_teacher(db, row)
        await db.commit()
        return ClassSubjectTeacherResponse.model_validate(row)

    @staticmethod
    async def list_class_subject_teachers(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        class_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        active_only: bool = False,
    ) -> tuple[list[ClassSubjectTeacherResponse], int]:
        rows, total = await StudentAcademicRepository.list_class_subject_teachers(
            db,
            tenant_id,
            skip=skip,
            limit=limit,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            active_only=active_only,
        )
        return [ClassSubjectTeacherResponse.model_validate(row) for row in rows], total

    @staticmethod
    async def update_class_subject_teacher(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: ClassSubjectTeacherUpdate,
    ) -> ClassSubjectTeacherResponse:
        row = await StudentAcademicRepository.get_class_subject_teacher_by_id(
            db,
            tenant_id,
            assignment_id,
        )
        if row is None:
            raise NotFoundException("Subject assignment not found.")
        if payload.teacher_membership_id is not None:
            class_subject = (
                await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                    db,
                    tenant_id,
                    row.class_id,
                    row.subject_id,
                )
            )
            if class_subject is None:
                raise NotFoundException("Class subject not found.")
            active = (
                await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                    db,
                    tenant_id,
                    class_subject.id,
                )
            )
            if active is None:
                await StudentAcademicService.create_teacher_assignment(
                    db,
                    tenant_id,
                    TeacherAssignmentCreate(
                        teacher_membership_id=payload.teacher_membership_id,
                        class_subject_id=class_subject.id,
                    ),
                )
            else:
                await StudentAcademicService.reassign_teacher_assignment(
                    db,
                    tenant_id,
                    active.id,
                    TeacherAssignmentReassign(
                        teacher_membership_id=payload.teacher_membership_id,
                    ),
                )
            row.teacher_membership_id = payload.teacher_membership_id
        for field in ("is_core", "sort_order", "is_active"):
            if field in payload.model_fields_set and getattr(payload, field) is not None:
                setattr(row, field, getattr(payload, field))
        row = await StudentAcademicRepository.save_class_subject_teacher(db, row)
        await db.commit()
        return ClassSubjectTeacherResponse.model_validate(row)

    @staticmethod
    async def create_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicSessionCreate,
    ) -> AcademicSession:
        if await StudentAcademicRepository.get_academic_session_by_name(
            db,
            tenant_id,
            payload.name,
        ):
            raise ConflictException("Academic session already exists.")
        if payload.next_academic_session_id is not None:
            next_session = await StudentAcademicRepository.get_academic_session_by_id(
                db,
                tenant_id,
                payload.next_academic_session_id,
            )
            if next_session is None:
                raise NotFoundException("Next academic session not found.")
        row = await StudentAcademicRepository.create_academic_session(
            db,
            AcademicSession(
                tenant_id=tenant_id,
                name=payload.name,
                start_date=payload.start_date,
                end_date=payload.end_date,
                next_academic_session_id=payload.next_academic_session_id,
                status=AcademicSessionStatus.DRAFT,
                is_current=False,
            ),
        )
        await db.commit()
        return row

    @staticmethod
    async def update_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        payload: AcademicSessionUpdate,
    ) -> AcademicSession:
        row = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            academic_session_id,
        )
        if row is None:
            raise NotFoundException("Academic session not found.")
        if row.status in {AcademicSessionStatus.CLOSING, AcademicSessionStatus.CLOSED}:
            raise ConflictException("Closing or closed sessions cannot be edited.")
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        effective_start_date = update_data.get("start_date", row.start_date)
        effective_end_date = update_data.get("end_date", row.end_date)
        if (
            effective_start_date is not None
            and effective_end_date is not None
            and effective_end_date <= effective_start_date
        ):
            raise BadRequestException("Session end date must be after start date.")
        if "name" in update_data and update_data["name"] != row.name:
            if await StudentAcademicRepository.get_academic_session_by_name(
                db,
                tenant_id,
                update_data["name"],
            ):
                raise ConflictException("Academic session name already exists.")
        next_id = update_data.get("next_academic_session_id")
        if next_id == row.id:
            raise BadRequestException("A session cannot point to itself.")
        if next_id is not None and not await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            next_id,
        ):
            raise NotFoundException("Next academic session not found.")
        for field, value in update_data.items():
            setattr(row, field, value)
        row = await StudentAcademicRepository.save_academic_session(db, row)
        await db.commit()
        return row

    @staticmethod
    async def list_academic_sessions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicSession], int]:
        return await StudentAcademicRepository.list_academic_sessions(
            db,
            tenant_id,
            skip,
            limit,
        )


    @staticmethod
    async def create_academic_term(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    payload: AcademicTermCreate,
    ) -> AcademicTerm:
        academic_session = (
            await StudentAcademicRepository.get_academic_session_by_id(
                db,
                tenant_id,
                payload.academic_session_id,
            )
        )

        if academic_session is None:
            raise NotFoundException("Academic session not found.")

        if academic_session.status in {
            AcademicSessionStatus.CLOSING,
            AcademicSessionStatus.CLOSED,
        }:
            raise ConflictException(
                "Terms cannot be added to a closing or closed academic session."
            )

        existing = (
            await StudentAcademicRepository.get_term_by_session_and_name(
                db,
                tenant_id,
                academic_session.id,
                payload.name,
            )
        )

        if existing is not None:
            raise ConflictException(
                "Academic term already exists in this session."
            )

        if (
            payload.start_date is not None
            and payload.end_date is not None
            and payload.end_date <= payload.start_date
        ):
            raise BadRequestException(
                "Term end date must be after start date."
            )

        term = AcademicTerm(
            tenant_id=tenant_id,
            academic_session_id=academic_session.id,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            status=AcademicTermStatus.DRAFT,
            is_current=False,
        )

        term = await StudentAcademicRepository.create_academic_term(
            db,
            term,
        )

        await db.commit()
        return term

    @staticmethod
    async def update_academic_term(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    term_id: uuid.UUID,
    payload: AcademicTermUpdate,
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id,
            term_id,
        )

        if term is None:
            raise NotFoundException("Academic term not found.")

        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException(
                "Only draft academic terms can be edited."
            )

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        effective_start_date = update_data.get(
            "start_date",
            term.start_date,
        )
        effective_end_date = update_data.get(
            "end_date",
            term.end_date,
        )

        if (
            effective_start_date is not None
            and effective_end_date is not None
            and effective_end_date <= effective_start_date
        ):
            raise BadRequestException(
                "Term end date must be after start date."
            )

        new_name = update_data.get("name")

        if new_name is not None and new_name != term.name:
            existing = (
                await StudentAcademicRepository.get_term_by_session_and_name(
                    db,
                    tenant_id,
                    term.academic_session_id,
                    new_name,
                )
            )

            if existing is not None and existing.id != term.id:
                raise ConflictException(
                    "Academic term already exists in this session."
                )

        for field, value in update_data.items():
            setattr(term, field, value)

        term = await StudentAcademicRepository.save_academic_term(
            db,
            term,
        )

        await db.commit()
        return term






    @staticmethod
    async def open_academic_term(
        db : AsyncSession ,
        tenant_id : uuid.UUID,
        term_id : uuid.UUID,
        admin_id : uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id = tenant_id ,
            term_id = term_id
        )

        if term is None:
            raise NotFoundException("Academic term not found ")


        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException(
                "Only a draft academic term can be opened"
            )


        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db = db ,
            tenant_id=tenant_id,
            academic_session_id= term.academic_session_id
        )

        if academic_session is None:
            raise NotFoundException("Academic session not found")

        if academic_session.status != AcademicSessionStatus.OPEN:
            raise ConflictException("The session must be open before a term can be opened")

        current_term = await StudentAcademicRepository.get_current_term(
            db = db,
            tenant_id = tenant_id,
        )


        if current_term is not None and current_term.id != term.id:
            raise ConflictException(
                "Another academic term is currently open. Close it first"
            )



        term.status = AcademicTermStatus.OPEN
        term.is_current = True
        term.opened_at = datetime.now(timezone.utc)
        term.opened_by_admin_id = admin_id
        term.closed_at = None
        term.closed_by_admin_id = None

        term = await StudentAcademicRepository.save_academic_term(
            db,
            term,
        )

        await db.commit()
        return term





    @staticmethod
    async def close_academic_term(
        db: AsyncSession,
        tenant_id : uuid.UUID,
        term_id : uuid.UUID,
        admin_id : uuid.UUID
    ) -> AcademicTerm:
        term  = await StudentAcademicRepository.get_term_by_id(
            db = db,
            tenant_id= tenant_id,
            term_id = term_id
        )


        if term is None:
            raise NotFoundException(
                "Academic term not found"
            )



        if term.status != AcademicTermStatus.OPEN:
            raise ConflictException(
                "Only an open academic term can be closed"
            )

        term.status = AcademicTermStatus.CLOSED
        term.is_current = False
        term.closed_at = datetime.now(timezone.utc)
        term.closed_by_admin_id = admin_id

        term = await StudentAcademicRepository.save_academic_term(
            db,
            term,
        )

        await db.commit()
        return term












    @staticmethod
    async def list_academic_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        academic_session_id: uuid.UUID | None = None,
        statuses : set[AcademicTermStatus] | None = None
    ) -> tuple[list[AcademicTerm], int]:
        if academic_session_id is None:
            return await StudentAcademicRepository.list_terms(
                db,
                tenant_id,
                skip,
                limit,
                statuses = statuses
            )
        return await StudentAcademicRepository.list_terms_by_session(
            db,
            tenant_id,
            academic_session_id,
            skip,
            limit,
            statuses = statuses
        )




    @staticmethod
    async def _ensure_no_grading_overlap(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        minimum: Decimal,
        maximum: Decimal,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        rows, _ = await StudentAcademicRepository.list_grading_scales(
            db,
            tenant_id,
            limit=500,
            active_only=True,
        )
        for row in rows:
            if exclude_id is not None and row.id == exclude_id:
                continue
            if minimum <= row.max_score and maximum >= row.min_score:
                raise ConflictException("Grading scale ranges cannot overlap.")





    @staticmethod
    async def create_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: GradingScaleCreate,
    ) -> GradingScale:
        if await StudentAcademicRepository.get_grading_scale_by_grade(
            db,
            tenant_id,
            payload.grade,
        ):
            raise ConflictException("This grade already exists.")
        if payload.is_active:
            await StudentAcademicService._ensure_no_grading_overlap(
                db,
                tenant_id=tenant_id,
                minimum=payload.min_score,
                maximum=payload.max_score,
            )
        row = await StudentAcademicRepository.create_grading_scale(
            db,
            GradingScale(tenant_id=tenant_id, **payload.model_dump()),
        )
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def update_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        scale_id: uuid.UUID,
        payload: GradingScaleUpdate,
    ) -> GradingScale:
        row = await StudentAcademicRepository.get_grading_scale_by_id(
            db,
            tenant_id,
            scale_id,
        )
        if row is None:
            raise NotFoundException("Grading scale not found.")
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        minimum = update_data.get("min_score", row.min_score)
        maximum = update_data.get("max_score", row.max_score)
        if minimum > maximum:
            raise BadRequestException("Minimum score cannot exceed maximum score.")
        if update_data.get("is_active", row.is_active):
            await StudentAcademicService._ensure_no_grading_overlap(
                db,
                tenant_id=tenant_id,
                minimum=minimum,
                maximum=maximum,
                exclude_id=row.id,
            )
        for field, value in update_data.items():
            setattr(row, field, value)
        row = await StudentAcademicRepository.save_grading_scale(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def list_grading_scales(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> tuple[list[GradingScale], int]:
        return await StudentAcademicRepository.list_grading_scales(
            db,
            tenant_id,
            skip,
            limit,
            active_only,
        )

    @staticmethod
    async def _resolve_assignment_context(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: StudentSubjectResultUpsert,
    ) -> tuple[TeacherAssignment, ClassSubjectTeacher, ClassSubject]:
        assignment = None
        compatibility = None
        class_subject = None
        if payload.teacher_assignment_id is not None:
            assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
                db,
                tenant_id,
                payload.teacher_assignment_id,
            )
            if assignment is None or not assignment.is_active:
                raise NotFoundException("Active teacher assignment not found.")
            class_subject = await StudentAcademicRepository.get_class_subject_by_id(
                db,
                tenant_id,
                assignment.class_subject_id,
            )
            if class_subject is not None:
                compatibility = (
                    await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                        db,
                        tenant_id,
                        class_subject.class_id,
                        class_subject.subject_id,
                    )
                )
        else:
            compatibility = await StudentAcademicRepository.get_class_subject_teacher_by_id(
                db,
                tenant_id,
                payload.class_subject_teacher_id,
            )
            if compatibility is not None:
                class_subject = (
                    await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                        db,
                        tenant_id,
                        compatibility.class_id,
                        compatibility.subject_id,
                    )
                )
                if class_subject is not None:
                    assignment = (
                        await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                            db,
                            tenant_id,
                            class_subject.id,
                        )
                    )
        if (
            assignment is None
            or class_subject is None
            or not class_subject.is_active
            or class_subject.archived_at is not None
        ):
            raise NotFoundException("Active class-subject assignment not found.")
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            class_subject.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before recording results.")
        if compatibility is None:
            compatibility = await StudentAcademicService._ensure_compatibility_assignment(
                db,
                tenant_id=tenant_id,
                class_subject=class_subject,
                teacher_membership_id=assignment.teacher_membership_id,
                is_active=True,
            )
        return assignment, compatibility, class_subject

    @staticmethod
    async def _build_result_response(
        db: AsyncSession,
        result: StudentSubjectResult,
    ) -> StudentSubjectResultResponse:
        student = await StudentRepository.get_by_id(
            db,
            result.tenant_id,
            result.student_id,
            include_archived=True,
        )
        classroom = await ClassRoomRepository.get_by_id(
            db,
            result.tenant_id,
            result.class_id,
        )
        subject = await SubjectRepository.get_subject_by_id(
            db,
            result.tenant_id,
            result.subject_id,
        )
        teacher = await TeacherMembershipRepository.get_by_id(
            db,
            result.teacher_membership_id,
            tenant_id=result.tenant_id,
            load_account=True,
        )
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            result.tenant_id,
            result.academic_session_id,
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            result.tenant_id,
            result.academic_term_id,
        )
        teacher_name = None
        if teacher is not None:
            teacher_name = " ".join(
                part
                for part in [
                    teacher.teacher_account.first_name,
                    teacher.teacher_account.last_name,
                ]
                if part
            ) or None
        student_name = None
        if student is not None:
            student_name = " ".join(
                part
                for part in [student.first_name, student.last_name]
                if part
            ) or None
        return StudentSubjectResultResponse(
            id=result.id,
            tenant_id=result.tenant_id,
            student_id=result.student_id,
            student_name=student_name,
            admission_number=student.admission_number if student else None,
            class_id=result.class_id,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=result.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_membership_id=result.teacher_membership_id,
            teacher_name=teacher_name,
            class_subject_teacher_id=result.class_subject_teacher_id,
            teacher_assignment_id=result.teacher_assignment_id,
            academic_session_id=result.academic_session_id,
            academic_session_name=session.name if session else None,
            academic_term_id=result.academic_term_id,
            academic_term_name=(
                term.name.value if term and hasattr(term.name, "value") else str(term.name) if term else None
            ),
            test_score=result.test_score,
            assessment_score=result.assessment_score,
            exam_score=result.exam_score,
            total_score=result.total_score,
            grade=result.grade,
            remark=result.remark,
            status=result.status,
            recorded_by_actor_type=result.recorded_by_actor_type,
            recorded_by_actor_id=result.recorded_by_actor_id,
            submitted_at=result.submitted_at,
            submitted_by_actor_type=result.submitted_by_actor_type,
            submitted_by_actor_id=result.submitted_by_actor_id,
            approved_at=result.approved_at,
            approved_by_admin_id=result.approved_by_admin_id,
            locked_at=result.locked_at,
            locked_by_admin_id=result.locked_by_admin_id,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    @staticmethod
    def _result_actor_type(actor: TenantAdmin | TeacherMembership) -> str:
        return "teacher" if isinstance(actor, TeacherMembership) else "tenant_admin"

    @staticmethod
    def _ensure_result_complete(result: StudentSubjectResult) -> None:
        if any(
            score is None
            for score in (
                result.test_score,
                result.assessment_score,
                result.exam_score,
            )
        ):
            raise BadRequestException("All scores are required before submission.")

    @staticmethod
    def _apply_result_lifecycle_metadata(
        result: StudentSubjectResult,
        *,
        actor: TenantAdmin | TeacherMembership,
        next_status: AcademicResultStatus,
    ) -> None:
        now = datetime.now(timezone.utc)
        actor_type = StudentAcademicService._result_actor_type(actor)
        if next_status == AcademicResultStatus.SUBMITTED:
            result.submitted_at = now
            result.submitted_by_actor_type = actor_type
            result.submitted_by_actor_id = actor.id
        elif next_status == AcademicResultStatus.APPROVED:
            if result.submitted_at is None:
                result.submitted_at = now
                result.submitted_by_actor_type = result.recorded_by_actor_type
                result.submitted_by_actor_id = result.recorded_by_actor_id
            result.approved_at = now
            result.approved_by_admin_id = actor.id
        elif next_status == AcademicResultStatus.LOCKED:
            if result.submitted_at is None:
                result.submitted_at = now
                result.submitted_by_actor_type = result.recorded_by_actor_type
                result.submitted_by_actor_id = result.recorded_by_actor_id
            if result.approved_at is None:
                result.approved_at = now
                result.approved_by_admin_id = actor.id
            result.locked_at = now
            result.locked_by_admin_id = actor.id

    @staticmethod
    def _ensure_forward_result_transition(
        current_status: AcademicResultStatus,
        next_status: AcademicResultStatus,
    ) -> None:
        expected = StudentAcademicService._RESULT_FORWARD_TRANSITIONS.get(current_status)
        if expected != next_status:
            raise BadRequestException(
                f"Invalid result lifecycle transition: {current_status.value} to {next_status.value}."
            )

    @staticmethod
    async def upsert_student_result(
        db: AsyncSession,
        actor: TenantAdmin | TeacherMembership,
        payload: StudentSubjectResultUpsert,
    ) -> StudentSubjectResultResponse:
        tenant_id = actor.tenant_id
        assignment, compatibility, class_subject = (
            await StudentAcademicService._resolve_assignment_context(
                db,
                tenant_id,
                payload,
            )
        )
        if isinstance(actor, TeacherMembership) and assignment.teacher_membership_id != actor.id:
            raise ForbiddenException("Teachers may record scores only for their own assignments.")

        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            payload.student_id,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.class_id != class_subject.class_id:
            raise ForbiddenException("Student is not currently enrolled in the assigned class.")
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            payload.academic_session_id,
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id,
            payload.academic_term_id,
        )
        if session is None or term is None or term.academic_session_id != session.id:
            raise NotFoundException("Academic session or term is invalid.")
        if session.status == AcademicSessionStatus.CLOSED:
            raise ConflictException("Results cannot be changed after session closure.")

        existing = await StudentAcademicRepository.get_result_by_scope(
            db,
            tenant_id,
            student.id,
            compatibility.id,
            session.id,
            term.id,
        )
        if (
            existing is not None
            and existing.status not in StudentAcademicService._RESULT_EDITABLE_STATUSES
        ):
            if isinstance(actor, TeacherMembership):
                raise ForbiddenException("Submitted, approved, and locked scores are not editable by teachers.")
            raise ConflictException("Only draft scores can be edited.")
        if payload.status not in StudentAcademicService._RESULT_UPSERT_STATUSES:
            raise BadRequestException("Use the dedicated lifecycle endpoint for approval and locking.")

        total = sum(
            (
                score
                for score in (
                    payload.test_score,
                    payload.assessment_score,
                    payload.exam_score,
                )
                if score is not None
            ),
            Decimal("0"),
        )
        complete = all(
            score is not None
            for score in (
                payload.test_score,
                payload.assessment_score,
                payload.exam_score,
            )
        )
        grade = None
        remark = None
        if complete:
            scale = await StudentAcademicRepository.find_grade_for_score(
                db,
                tenant_id,
                total,
            )
            if scale is not None:
                grade = scale.grade
                remark = scale.remark
        if payload.status == AcademicResultStatus.SUBMITTED and not complete:
            raise BadRequestException("All three scores are required before submission.")

        if existing is None:
            result = StudentSubjectResult(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_membership_id=assignment.teacher_membership_id,
                class_subject_teacher_id=compatibility.id,
                teacher_assignment_id=assignment.id,
                academic_session_id=session.id,
                academic_term_id=term.id,
                test_score=payload.test_score,
                assessment_score=payload.assessment_score,
                exam_score=payload.exam_score,
                total_score=total,
                grade=grade,
                remark=remark,
                status=payload.status,
                recorded_by_actor_type=(
                    "teacher" if isinstance(actor, TeacherMembership) else "tenant_admin"
                ),
                recorded_by_actor_id=actor.id,
            )
            if payload.status == AcademicResultStatus.SUBMITTED:
                StudentAcademicService._apply_result_lifecycle_metadata(
                    result,
                    actor=actor,
                    next_status=payload.status,
                )
        else:
            result = existing
            previous_status = result.status
            result.teacher_membership_id = assignment.teacher_membership_id
            result.teacher_assignment_id = assignment.id
            result.test_score = payload.test_score
            result.assessment_score = payload.assessment_score
            result.exam_score = payload.exam_score
            result.total_score = total
            result.grade = grade
            result.remark = remark
            result.status = payload.status
            result.recorded_by_actor_type = (
                "teacher" if isinstance(actor, TeacherMembership) else "tenant_admin"
            )
            result.recorded_by_actor_id = actor.id
            if payload.status != previous_status:
                StudentAcademicService._ensure_forward_result_transition(
                    previous_status,
                    payload.status,
                )
                StudentAcademicService._apply_result_lifecycle_metadata(
                    result,
                    actor=actor,
                    next_status=payload.status,
                )
        result = await StudentAcademicRepository.upsert_result(db, result)
        await db.commit()
        return await StudentAcademicService._build_result_response(db, result)

    @staticmethod
    async def update_result_status(
        db: AsyncSession,
        actor: TenantAdmin,
        result_id: uuid.UUID,
        payload: StudentSubjectResultStatusUpdate,
    ) -> StudentSubjectResultResponse:
        result = await StudentAcademicRepository.get_result_by_id(
            db,
            actor.tenant_id,
            result_id,
        )
        if result is None:
            raise NotFoundException("Result not found.")
        StudentAcademicService._ensure_forward_result_transition(
            result.status,
            payload.status,
        )
        if payload.status == AcademicResultStatus.SUBMITTED:
            StudentAcademicService._ensure_result_complete(result)
        result.status = payload.status
        StudentAcademicService._apply_result_lifecycle_metadata(
            result,
            actor=actor,
            next_status=payload.status,
        )
        result = await StudentAcademicRepository.upsert_result(db, result)
        await db.commit()
        return await StudentAcademicService._build_result_response(db, result)

    @staticmethod
    async def reopen_result(
        db: AsyncSession,
        actor: TenantAdmin,
        result_id: uuid.UUID,
        payload: StudentSubjectResultReopenRequest,
    ) -> StudentSubjectResultResponse:
        result = await StudentAcademicRepository.get_result_by_id(
            db,
            actor.tenant_id,
            result_id,
        )
        if result is None:
            raise NotFoundException("Result not found.")
        if result.status != AcademicResultStatus.LOCKED:
            raise BadRequestException("Only locked results can be reopened.")
        if not payload.reason.strip():
            raise BadRequestException("A reopen reason is required.")

        from app.modules.report_cards.service import ReportCardService

        await ReportCardService.mark_outdated_for_score_change(
            db,
            result.tenant_id,
            result.student_id,
            result.academic_session_id,
            result.academic_term_id,
        )
        result.status = AcademicResultStatus.DRAFT
        result.submitted_at = None
        result.submitted_by_actor_type = None
        result.submitted_by_actor_id = None
        result.approved_at = None
        result.approved_by_admin_id = None
        result.locked_at = None
        result.locked_by_admin_id = None
        result = await StudentAcademicRepository.upsert_result(db, result)
        await db.commit()
        return await StudentAcademicService._build_result_response(db, result)

    @staticmethod
    async def _ensure_parent_can_view_student(
        db: AsyncSession,
        parent: ParentMembership,
        student_id: uuid.UUID,
    ) -> None:
        links = await StudentParentLinkRepository.list_for_membership(
            db,
            parent.tenant_id,
            parent.id,
            statuses=[
                StudentParentLinkStatus.ACTIVE,
                StudentParentLinkStatus.READ_ONLY,
                StudentParentLinkStatus.ALUMNI_READ_ONLY,
            ],
        )
        if not any(link.student_id == student_id for link in links):
            raise ForbiddenException("Parent membership cannot access this student.")

    @staticmethod
    async def list_results(
        db: AsyncSession,
        actor: TenantAdmin | TeacherMembership | Student | ParentMembership,
        *,
        skip: int = 0,
        limit: int = 100,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
    ) -> tuple[list[StudentSubjectResultResponse], int]:
        tenant_id = actor.tenant_id
        teacher_id = None
        finalized_only = False
        if isinstance(actor, TeacherMembership):
            teacher_id = actor.id
        elif isinstance(actor, Student):
            student_id = actor.id
            finalized_only = True
        elif isinstance(actor, ParentMembership):
            if student_id is None:
                raise BadRequestException("student_id is required for parent result access.")
            await StudentAcademicService._ensure_parent_can_view_student(
                db,
                actor,
                student_id,
            )
            finalized_only = True
        rows, total = await StudentAcademicRepository.list_results(
            db,
            tenant_id,
            skip=skip,
            limit=limit,
            student_id=student_id,
            class_id=class_id,
            teacher_id=teacher_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            finalized_only=finalized_only,
        )
        return [
            await StudentAcademicService._build_result_response(db, row)
            for row in rows
        ], total

    @staticmethod
    async def list_student_subject_cards(
        db: AsyncSession,
        *,
        actor: Student | ParentMembership,
        student_id: uuid.UUID | None = None,
    ) -> StudentSubjectCardListResponse:
        if isinstance(actor, Student):
            student_id = actor.id
        elif student_id is None:
            raise BadRequestException("student_id is required.")
        else:
            await StudentAcademicService._ensure_parent_can_view_student(
                db,
                actor,
                student_id,
            )
        student = await StudentRepository.get_by_id(
            db,
            actor.tenant_id,
            student_id,
            include_archived=True,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        classroom = (
            await ClassRoomRepository.get_by_id(
                db,
                actor.tenant_id,
                student.class_id,
            )
            if student.class_id
            else None
        )
        session = await StudentAcademicRepository.get_current_academic_session(
            db,
            actor.tenant_id,
        )
        term = await StudentAcademicRepository.get_current_term(
            db,
            actor.tenant_id,
        )
        class_subjects, _ = await StudentAcademicRepository.list_class_subjects(
            db,
            actor.tenant_id,
            class_id=student.class_id,
            active_only=True,
            limit=500,
        ) if student.class_id else ([], 0)

        cards: list[StudentSubjectCardResponse] = []
        for class_subject in class_subjects:
            subject = await SubjectRepository.get_subject_by_id(
                db,
                actor.tenant_id,
                class_subject.subject_id,
            )
            assignment = (
                await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                    db,
                    actor.tenant_id,
                    class_subject.id,
                )
            )
            compatibility = (
                await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                    db,
                    actor.tenant_id,
                    class_subject.class_id,
                    class_subject.subject_id,
                )
            )
            result = None
            if compatibility is not None and session is not None and term is not None:
                result = await StudentAcademicRepository.get_result_by_scope(
                    db,
                    actor.tenant_id,
                    student.id,
                    compatibility.id,
                    session.id,
                    term.id,
                )
            teacher = None
            if assignment is not None:
                teacher = await TeacherMembershipRepository.get_by_id(
                    db,
                    assignment.teacher_membership_id,
                    tenant_id=actor.tenant_id,
                    load_account=True,
                )
            teacher_name = None
            if teacher is not None:
                teacher_name = " ".join(
                    part
                    for part in [
                        teacher.teacher_account.first_name,
                        teacher.teacher_account.last_name,
                    ]
                    if part
                ) or None
            submitted = bool(
                result is not None
                and result.status == AcademicResultStatus.LOCKED
            )
            cards.append(
                StudentSubjectCardResponse(
                    id=class_subject.id,
                    result_id=result.id if submitted else None,
                    class_id=class_subject.class_id,
                    class_name=classroom.name if classroom else None,
                    class_arm=classroom.arm if classroom else None,
                    subject_id=class_subject.subject_id,
                    subject_name=subject.name if subject else None,
                    subject_code=subject.code if subject else None,
                    teacher_membership_id=(
                        assignment.teacher_membership_id if assignment else None
                    ),
                    teacher_name=teacher_name,
                    academic_session_id=session.id if session else None,
                    academic_session_name=session.name if session else None,
                    academic_term_id=term.id if term else None,
                    academic_term_name=(
                        term.name.value if term and hasattr(term.name, "value") else str(term.name) if term else None
                    ),
                    test_score=result.test_score if submitted else None,
                    assessment_score=result.assessment_score if submitted else None,
                    exam_score=result.exam_score if submitted else None,
                    total_score=result.total_score if submitted else None,
                    grade=result.grade if submitted else None,
                    remark=result.remark if submitted else None,
                    status="locked" if submitted else "pending",
                    is_complete=submitted,
                )
            )
        return StudentSubjectCardListResponse(
            items=cards,
            total=len(cards),
            context=StudentSubjectCardContextResponse(
                class_id=student.class_id,
                class_name=classroom.name if classroom else None,
                class_arm=classroom.arm if classroom else None,
                academic_session_id=session.id if session else None,
                academic_session_name=session.name if session else None,
                academic_term_id=term.id if term else None,
                academic_term_name=(
                    term.name.value if term and hasattr(term.name, "value") else str(term.name) if term else None
                ),
            ),
        )
