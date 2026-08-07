"""Canonical academic setup, assignment, score, and subject-card services."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.classes.repository import ClassRoomRepository
from app.modules.report_cards.models import ReportCardStatus
from app.modules.parents.models import ParentMembership
from app.modules.student_academics.models import (
    SchoolAssessmentConfig,
    AcademicLifecycleAudit,
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    StudentProgressionRunStatus,
    StudentSubjectResult,
    TeacherAssignment,
    TeacherAssignmentLifecycleAudit,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    GradingScaleReadiness,
    AcademicSessionCreate,
    AcademicSessionDependencyPreview,
    AcademicSessionUpdate,
    AcademicTermCreate,
    AcademicTermDependencyPreview,
    AcademicTermUpdate,
    ClassSubjectCreate,
    ClassSubjectBulkCreate,
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
    TeacherAssignmentDependencyPreview,
    TeacherAssignmentEnd,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
    ClassSubjectUpdate,
)
from app.modules.students.models import Student, StudentParentLinkStatus
from app.modules.students.repository import (
    StudentParentLinkRepository,
    StudentRepository,
    StudentEnrollmentRepository,
)
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import (
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
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
    _TERM_ORDER = {
        AcademicTermName.FIRST_TERM: 1,
        AcademicTermName.SECOND_TERM: 2,
        AcademicTermName.THIRD_TERM: 3,
    }

    @staticmethod
    async def _record_academic_lifecycle(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        previous_status: str | None,
        new_status: str | None,
        acting_admin_id: uuid.UUID | None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        await StudentAcademicRepository.add_academic_lifecycle_audit(
            db,
            AcademicLifecycleAudit(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                previous_status=previous_status,
                new_status=new_status,
                acting_admin_id=acting_admin_id,
                reason=reason,
                metadata_json=metadata,
            ),
        )

    @staticmethod
    def _raise_dependency_conflict(message: str, preview) -> None:
        raise ConflictException(
            message,
            payload={
                "dependency_counts": preview.dependency_counts,
                "blocker_messages": preview.blocker_messages,
            },
        )

    @staticmethod
    async def _validate_session_dates(
        *,
        start_date: date | None,
        end_date: date | None,
        require_complete: bool = False,
    ) -> None:
        if require_complete and (start_date is None or end_date is None):
            raise BadRequestException("Session start and end dates are required.")
        if start_date is not None and end_date is not None and end_date <= start_date:
            raise BadRequestException("Session end date must be after start date.")

    @staticmethod
    async def _validate_next_session_link(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        next_academic_session_id: uuid.UUID | None,
        start_date: date | None,
        end_date: date | None,
    ) -> None:
        if next_academic_session_id is None:
            return
        if next_academic_session_id == session_id:
            raise BadRequestException("A session cannot point to itself.")

        next_session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            next_academic_session_id,
            lock=True,
        )
        if next_session is None:
            raise NotFoundException("Next academic session not found.")
        if next_session.start_date is not None:
            if start_date is not None and next_session.start_date <= start_date:
                raise BadRequestException(
                    "Next academic session must start after this session."
                )
            if end_date is not None and next_session.start_date <= end_date:
                raise BadRequestException(
                    "Next academic session must start after this session ends."
                )

        visited = {session_id}
        cursor = next_session
        while cursor.next_academic_session_id is not None:
            if cursor.next_academic_session_id in visited:
                raise BadRequestException(
                    "Academic session progression links cannot contain cycles."
                )
            visited.add(cursor.next_academic_session_id)
            cursor = await StudentAcademicRepository.get_academic_session_by_id(
                db,
                tenant_id,
                cursor.next_academic_session_id,
                lock=True,
            )
            if cursor is None:
                raise NotFoundException(
                    "Next academic session chain references a missing session."
                )

    @staticmethod
    async def _validate_term_dates_and_order(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        session: AcademicSession,
        name: AcademicTermName,
        start_date: date | None,
        end_date: date | None,
        exclude_term_id: uuid.UUID | None = None,
    ) -> None:
        if start_date is not None and end_date is not None and end_date <= start_date:
            raise BadRequestException("Term end date must be after start date.")
        if (
            session.start_date is not None
            and start_date is not None
            and start_date < session.start_date
        ):
            raise BadRequestException(
                "Term start date must fall within the session date range."
            )
        if (
            session.end_date is not None
            and end_date is not None
            and end_date > session.end_date
        ):
            raise BadRequestException(
                "Term end date must fall within the session date range."
            )
        if start_date is None or end_date is None:
            return

        terms, _ = await StudentAcademicRepository.list_terms_by_session(
            db,
            tenant_id,
            session.id,
            limit=500,
            statuses=set(),
        )
        for term in terms:
            if exclude_term_id is not None and term.id == exclude_term_id:
                continue
            if (
                start_date is not None
                and end_date is not None
                and term.start_date is not None
                and term.end_date is not None
            ):
                overlaps = start_date < term.end_date and end_date > term.start_date
                if overlaps:
                    raise ConflictException(
                        "Academic terms in the same session cannot overlap."
                    )
            if (
                start_date is not None
                and end_date is not None
                and term.start_date is not None
                and term.end_date is not None
            ):
                current_order = StudentAcademicService._TERM_ORDER[name]
                other_order = StudentAcademicService._TERM_ORDER[term.name]
                if current_order < other_order and start_date >= term.start_date:
                    raise BadRequestException(
                        "Earlier terms must start before later terms."
                    )
                if current_order > other_order and start_date <= term.start_date:
                    raise BadRequestException(
                        "Later terms must start after earlier terms."
                    )

    @staticmethod
    async def academic_session_dependency_preview(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> AcademicSessionDependencyPreview:
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, session_id
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        counts = {
            "terms": await StudentAcademicRepository.count_academic_terms(
                db, tenant_id, academic_session_id=session_id
            ),
            "open_terms": await StudentAcademicRepository.count_academic_terms(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={AcademicTermStatus.OPEN},
            ),
            "closing_terms": await StudentAcademicRepository.count_academic_terms(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={AcademicTermStatus.CLOSING},
            ),
            "draft_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={AcademicResultStatus.DRAFT},
            ),
            "submitted_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={AcademicResultStatus.SUBMITTED},
            ),
            "approved_but_unlocked_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={AcademicResultStatus.APPROVED},
            ),
            "results": await StudentAcademicRepository.count_results(
                db, tenant_id, academic_session_id=session_id
            ),
            "unpublished_report_cards": await StudentAcademicRepository.count_report_cards(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={ReportCardStatus.DRAFT},
            ),
            "report_cards": await StudentAcademicRepository.count_report_cards(
                db, tenant_id, academic_session_id=session_id
            ),
            "enrollments": await StudentAcademicRepository.count_enrollments(
                db, tenant_id, session_id
            ),
            "active_or_pending_progression_runs": await StudentAcademicRepository.count_progression_runs(
                db,
                tenant_id,
                academic_session_id=session_id,
                statuses={
                    StudentProgressionRunStatus.PENDING,
                    StudentProgressionRunStatus.PROCESSING,
                },
            ),
            "progression_runs": await StudentAcademicRepository.count_progression_runs(
                db, tenant_id, academic_session_id=session_id
            ),
            "inbound_next_sessions": await StudentAcademicRepository.count_inbound_next_sessions(
                db, tenant_id, session_id
            ),
        }
        blockers: list[str] = []
        can_open = session.status == AcademicSessionStatus.DRAFT and counts["terms"] > 0
        if session.status == AcademicSessionStatus.DRAFT and counts["terms"] == 0:
            blockers.append(
                "Add at least one academic term before opening the session."
            )
        if session.status == AcademicSessionStatus.OPEN:
            if session.next_academic_session_id is None:
                blockers.append("Configure next_academic_session_id before closure.")
            if counts["open_terms"]:
                blockers.append(
                    "Close every term in this session before closing the session."
                )
            if counts["closing_terms"]:
                blockers.append(
                    "Finalize every closing term before closing the session."
                )
            if counts["draft_results"]:
                blockers.append(
                    "Draft results must be submitted, approved, or removed before closure."
                )
            if counts["submitted_results"]:
                blockers.append(
                    "Submitted results must be approved or returned before closure."
                )
            if counts["approved_but_unlocked_results"]:
                blockers.append("Approved results must be locked before closure.")
            if counts["unpublished_report_cards"]:
                blockers.append(
                    "Report cards must be published or archived before closure."
                )
            if counts["active_or_pending_progression_runs"]:
                blockers.append(
                    "A progression run is already active or pending for this session."
                )
            from app.modules.school_calendar.service import SchoolCalendarService

            terms, _ = await StudentAcademicRepository.list_terms_by_session(
                db,
                tenant_id,
                session_id,
                limit=500,
                statuses=set(),
            )
            calendar_history_missing = 0
            calendar_history_incomplete = 0
            for term in terms:
                contribution = (
                    await SchoolCalendarService.inspect_term_closure_readiness(
                        db,
                        tenant_id=tenant_id,
                        term_id=term.id,
                    )
                )
                if contribution.get("calendar_id") is None:
                    calendar_history_missing += 1
                calendar_counts = contribution.get("counts", {})
                calendar_history_incomplete += int(
                    calendar_counts.get("missing_calendar_dates", 0) or 0
                )
                blockers.extend(contribution.get("blockers", []))
            counts["calendar_history_missing_terms"] = calendar_history_missing
            counts["missing_calendar_dates"] = calendar_history_incomplete
        can_start_closing = (
            session.status == AcademicSessionStatus.OPEN and not blockers
        )
        can_delete = (
            session.status == AcademicSessionStatus.DRAFT
            and not session.is_current
            and counts["terms"] == 0
            and counts["enrollments"] == 0
            and counts["results"] == 0
            and counts["report_cards"] == 0
            and counts["progression_runs"] == 0
            and counts["inbound_next_sessions"] == 0
        )
        return AcademicSessionDependencyPreview(
            session_id=session_id,
            dependency_counts=counts,
            blocker_messages=blockers,
            can_open=can_open,
            can_close=can_start_closing,
            can_start_closing=can_start_closing,
            can_progress=can_start_closing
            and session.next_academic_session_id is not None,
            can_delete=can_delete,
        )

    @staticmethod
    async def academic_term_dependency_preview(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> AcademicTermDependencyPreview:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id)
        if term is None:
            raise NotFoundException("Academic term not found.")
        counts = {
            "draft_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_term_id=term_id,
                statuses={AcademicResultStatus.DRAFT},
            ),
            "submitted_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_term_id=term_id,
                statuses={AcademicResultStatus.SUBMITTED},
            ),
            "approved_but_unlocked_results": await StudentAcademicRepository.count_results(
                db,
                tenant_id,
                academic_term_id=term_id,
                statuses={AcademicResultStatus.APPROVED},
            ),
            "results": await StudentAcademicRepository.count_results(
                db, tenant_id, academic_term_id=term_id
            ),
            "unpublished_report_cards": await StudentAcademicRepository.count_report_cards(
                db,
                tenant_id,
                academic_term_id=term_id,
                statuses={ReportCardStatus.DRAFT},
            ),
            "report_cards": await StudentAcademicRepository.count_report_cards(
                db, tenant_id, academic_term_id=term_id
            ),
        }
        blockers: list[str] = []
        if term.status in {AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING}:
            if counts["draft_results"]:
                blockers.append(
                    "Draft results must be submitted, approved, or removed before closing the term."
                )
            if counts["submitted_results"]:
                blockers.append(
                    "Submitted results must be approved or returned before closing the term."
                )
            if counts["approved_but_unlocked_results"]:
                blockers.append(
                    "Approved results must be locked before closing the term."
                )
            if counts["unpublished_report_cards"]:
                blockers.append(
                    "Report cards must be published or archived before closing the term."
                )
            from app.modules.school_calendar.service import SchoolCalendarService

            contribution = await SchoolCalendarService.inspect_term_closure_readiness(
                db,
                tenant_id=tenant_id,
                term_id=term_id,
            )
            counts.update(contribution.get("counts", {}))
            blockers.extend(contribution.get("blockers", []))
        can_delete = (
            term.status == AcademicTermStatus.DRAFT
            and not term.is_current
            and counts["results"] == 0
            and counts["report_cards"] == 0
        )
        can_close = (
            term.status in {AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING}
            and not blockers
        )
        return AcademicTermDependencyPreview(
            term_id=term_id,
            dependency_counts=counts,
            blocker_messages=blockers,
            can_open=term.status == AcademicTermStatus.DRAFT,
            can_close=can_close,
            can_start_closing=term.status == AcademicTermStatus.OPEN and can_close,
            can_finalize_close=term.status == AcademicTermStatus.CLOSING and can_close,
            can_cancel_closure=term.status == AcademicTermStatus.CLOSING,
            can_delete=can_delete,
        )

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
            else "active" if class_subject.is_active else "inactive"
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
            activation_blocker = (
                "Class must be restored before activating this mapping."
            )
        elif subject is None:
            activation_blocker = "Subject not found."
        elif not subject.is_active:
            activation_blocker = (
                "Subject must be active before activating this mapping."
            )
        elif subject.archived_at is not None:
            activation_blocker = (
                "Subject must be restored before activating this mapping."
            )
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
            teacher_name = (
                " ".join(
                    part
                    for part in [
                        teacher.teacher_account.first_name,
                        teacher.teacher_account.last_name,
                    ]
                    if part
                )
                or None
            )
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
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
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
                raise ConflictException("This subject is already offered by the class.")
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
    async def create_class_subjects_bulk(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        payload: ClassSubjectBulkCreate,
    ) -> list[ClassSubjectResponse]:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
            raise NotFoundException("Class not found or inactive.")

        subjects = await SubjectRepository.get_subjects_by_id(
            db=db,
            tenant_id=tenant_id,
            subject_ids=payload.subject_ids,
        )
        subjects_by_id = {subject.id: subject for subject in subjects}
        missing_subject_ids = [
            str(subject_id)
            for subject_id in payload.subject_ids
            if subject_id not in subjects_by_id
        ]
        inactive_subject_names = [
            subject.name
            for subject in subjects
            if not subject.is_active or subject.archived_at is not None
        ]
        if missing_subject_ids:
            raise NotFoundException(
                detail="One or more subjects were not found.",
                payload={"subject_ids": missing_subject_ids},
            )
        if inactive_subject_names:
            raise ConflictException(
                detail="One or more selected subjects are inactive or archived.",
                payload={"subjects": inactive_subject_names},
            )

        existing_rows, _ = await StudentAcademicRepository.list_class_subjects(
            db,
            tenant_id,
            class_id=class_id,
            include_archived=True,
            limit=500,
        )
        existing_by_subject_id = {
            row.subject_id: row
            for row in existing_rows
            if row.subject_id in set(payload.subject_ids)
        }
        if existing_by_subject_id:
            conflicts = []
            for subject_id, row in existing_by_subject_id.items():
                subject = subjects_by_id.get(subject_id)
                status = (
                    "archived"
                    if row.archived_at is not None
                    else "active" if row.is_active else "inactive"
                )
                conflicts.append(
                    {
                        "subject_id": str(subject_id),
                        "subject_name": subject.name if subject else None,
                        "status": status,
                    }
                )
            raise ConflictException(
                detail="One or more selected subjects are already attached to this class.",
                payload={"conflicts": conflicts},
            )

        rows = []
        for subject_id in payload.subject_ids:
            row = await StudentAcademicRepository.create_class_subject(
                db,
                ClassSubject(
                    tenant_id=tenant_id,
                    class_id=class_id,
                    subject_id=subject_id,
                    is_core=payload.is_core,
                    is_active=True,
                    archived_at=None,
                    archived_by_admin_id=None,
                ),
            )
            rows.append(row)

        await db.commit()
        return [
            await StudentAcademicService._build_class_subject_response(db, row)
            for row in rows
        ]

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
    def _build_teacher_assignment_response_from_record(
        record: dict,
    ) -> TeacherAssignmentResponse:
        assignment = record["assignment"]
        return TeacherAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
            teacher_membership_id=assignment.teacher_membership_id,
            class_id=record.get("class_id"),
            class_name=record.get("class_name"),
            class_arm=record.get("class_arm"),
            subject_id=record.get("subject_id"),
            subject_name=record.get("subject_name"),
            subject_code=record.get("subject_code"),
            teacher_name=record.get("teacher_name"),
            teacher_staff_id=record.get("teacher_staff_id"),
            is_active=assignment.is_active,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    @staticmethod
    async def teacher_assignment_dependency_preview(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> TeacherAssignmentDependencyPreview:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        counts = await StudentAcademicRepository.count_teacher_assignment_dependencies(
            db,
            tenant_id,
            assignment.id,
        )
        later_assignments = (
            await StudentAcademicRepository.get_later_teacher_assignments(
                db,
                tenant_id,
                assignment.class_subject_id,
                assignment.effective_from,
                exclude_id=assignment.id,
            )
        )
        counts["later_assignment_history"] = len(later_assignments)
        blockers: list[str] = []
        is_current = assignment.is_active and assignment.effective_to is None
        is_malformed_historical = (
            not assignment.is_active and assignment.effective_to is None
        )
        if is_malformed_historical:
            blockers.append(
                "This ended assignment is missing an effective end date and requires administrative repair."
            )
        if assignment.is_active:
            blockers.append("End the teacher assignment before deleting it.")
        if (
            counts["student_results"]
            or counts["report_card_references"]
            or counts["other_academic_records"]
        ):
            blockers.append(
                "This teacher assignment is referenced by academic records."
            )
        if counts["later_assignment_history"]:
            blockers.append("This teacher assignment has later assignment history.")
        return TeacherAssignmentDependencyPreview(
            assignment_id=assignment.id,
            dependency_counts=counts,
            can_end=is_current,
            can_reassign=is_current and counts["later_assignment_history"] == 0,
            can_delete=(
                not assignment.is_active
                and not is_malformed_historical
                and not any(counts.values())
            ),
            blocker_messages=blockers,
        )

    @staticmethod
    async def _record_teacher_assignment_audit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID | None,
        class_subject_id: uuid.UUID,
        action: str,
        previous_teacher_membership_id: uuid.UUID | None = None,
        new_teacher_membership_id: uuid.UUID | None = None,
        previous_state: str | None = None,
        new_state: str | None = None,
        previous_effective_from: date | None = None,
        previous_effective_to: date | None = None,
        new_effective_from: date | None = None,
        new_effective_to: date | None = None,
        acting_admin_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> None:
        await StudentAcademicRepository.create_teacher_assignment_lifecycle_audit(
            db,
            TeacherAssignmentLifecycleAudit(
                tenant_id=tenant_id,
                assignment_id=assignment_id,
                class_subject_id=class_subject_id,
                action=action,
                previous_teacher_membership_id=previous_teacher_membership_id,
                new_teacher_membership_id=new_teacher_membership_id,
                previous_state=previous_state,
                new_state=new_state,
                previous_effective_from=previous_effective_from,
                previous_effective_to=previous_effective_to,
                new_effective_from=new_effective_from,
                new_effective_to=new_effective_to,
                acting_admin_id=acting_admin_id,
                reason=reason,
            ),
        )

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
            raise ConflictException(
                "Archived class subjects must be restored before activation."
            )
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, row.class_id)
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
            raise ConflictException(
                "Classroom must be active before activating this class subject."
            )
        subject = await SubjectRepository.get_subject_by_id(
            db, tenant_id, row.subject_id
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException(
                "Subject must be active before activating this class subject."
            )
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
            raise ConflictException(
                "Archived class-subject mappings cannot be updated."
            )
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
        if (
            counts["active_teacher_assignments"]
            or counts["active_compatibility_teacher_rows"]
        ):
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
            raise ConflictException(
                "Active class-subject mappings cannot be hard-deleted. Deactivate the mapping first."
            )
        if row.archived_at is not None:
            raise ConflictException(
                "Archived class-subject mappings cannot be hard-deleted. Restore them first."
            )
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
            await StudentAcademicRepository.delete_class_subject_teacher(
                db, compatibility_row
            )
        await StudentAcademicRepository.delete_class_subject(db, row)
        await db.commit()
        return response

    @staticmethod
    async def create_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TeacherAssignmentCreate,
        class_subject_id: uuid.UUID | None = None,
        acting_admin_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        resolved_class_subject_id = class_subject_id or payload.class_subject_id
        if resolved_class_subject_id is None:
            raise BadRequestException("class_subject_id is required.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            resolved_class_subject_id,
            lock=True,
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
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
            raise ConflictException(
                "Classroom must be active before assigning a teacher."
            )
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            class_subject.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException(
                "Subject must be active before assigning a teacher."
            )
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
        )
        if active is not None:
            raise ConflictException(
                "An active teacher assignment already exists for this class subject."
            )
        effective_from = payload.effective_from or date.today()
        existing_assignments = (
            await StudentAcademicRepository.list_teacher_assignments_for_class_subject(
                db,
                tenant_id,
                class_subject.id,
                lock=True,
            )
        )
        for existing in existing_assignments:
            if existing.effective_to is None or existing.effective_to >= effective_from:
                raise ConflictException(
                    "Teacher assignment effective date overlaps existing assignment history."
                )
        try:
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
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "An active teacher assignment already exists for this class subject."
            ) from exc
        await StudentAcademicService._ensure_compatibility_assignment(
            db,
            tenant_id=tenant_id,
            class_subject=class_subject,
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
        )
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_subject_id=class_subject.id,
            action="assignment_created",
            new_teacher_membership_id=payload.teacher_membership_id,
            previous_state=None,
            new_state="active",
            new_effective_from=assignment.effective_from,
            new_effective_to=assignment.effective_to,
            acting_admin_id=acting_admin_id,
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
        acting_admin_id: uuid.UUID | None = None,
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
                raise ConflictException(
                    "This historical assignment is missing an effective end date and requires administrative repair."
                )
            if (
                payload.effective_to is not None
                and payload.effective_to != assignment.effective_to
            ):
                raise ConflictException(
                    "Teacher assignment is already ended with a different effective date."
                )
            return await StudentAcademicService._build_teacher_assignment_response(
                db,
                assignment,
            )
        effective_to = payload.effective_to or date.today()
        if effective_to < assignment.effective_from:
            raise ConflictException(
                "Assignment end date cannot be before its start date."
            )
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
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_subject_id=assignment.class_subject_id,
            action="assignment_ended",
            previous_teacher_membership_id=assignment.teacher_membership_id,
            new_teacher_membership_id=assignment.teacher_membership_id,
            previous_state="active",
            new_state="ended",
            previous_effective_from=assignment.effective_from,
            previous_effective_to=None,
            new_effective_from=assignment.effective_from,
            new_effective_to=assignment.effective_to,
            acting_admin_id=acting_admin_id,
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
        acting_admin_id: uuid.UUID | None = None,
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
            raise ConflictException(
                "Only the current active teacher assignment can be reassigned."
            )
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
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
            raise ConflictException(
                "Classroom must be active before reassigning a teacher."
            )
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            class_subject.subject_id,
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException(
                "Subject must be active before reassigning a teacher."
            )
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
        if effective_from < current.effective_from:
            raise ConflictException(
                "Replacement effective date cannot be before the current assignment start date."
            )
        later_assignments = (
            await StudentAcademicRepository.get_later_teacher_assignments(
                db,
                tenant_id,
                class_subject.id,
                current.effective_from,
                exclude_id=current.id,
                lock=True,
            )
        )
        if later_assignments:
            raise ConflictException(
                "Cannot reassign because later assignment history already exists."
            )

        current.is_active = False
        current.effective_to = (
            effective_from
            if effective_from == current.effective_from
            else effective_from - timedelta(days=1)
        )
        if current.effective_to < current.effective_from:
            raise ConflictException(
                "Replacement effective date creates an invalid assignment range."
            )
        await StudentAcademicRepository.save_teacher_assignment(db, current)

        try:
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
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "An active teacher assignment already exists for this class subject."
            ) from exc
        await StudentAcademicService._ensure_compatibility_assignment(
            db,
            tenant_id=tenant_id,
            class_subject=class_subject,
            teacher_membership_id=payload.teacher_membership_id,
            is_active=True,
        )
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=replacement.id,
            class_subject_id=class_subject.id,
            action="teacher_reassigned",
            previous_teacher_membership_id=current.teacher_membership_id,
            new_teacher_membership_id=payload.teacher_membership_id,
            previous_state="active",
            new_state="active",
            previous_effective_from=current.effective_from,
            previous_effective_to=current.effective_to,
            new_effective_from=replacement.effective_from,
            new_effective_to=replacement.effective_to,
            acting_admin_id=acting_admin_id,
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
        acting_admin_id: uuid.UUID | None = None,
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
        preview = await StudentAcademicService.teacher_assignment_dependency_preview(
            db,
            tenant_id,
            assignment.id,
        )
        if not preview.can_delete:
            raise ConflictException(
                "This teacher assignment has dependencies and cannot be deleted.",
                payload={
                    "dependency_counts": preview.dependency_counts,
                    "blocker_messages": preview.blocker_messages,
                },
            )
        response = await StudentAcademicService._build_teacher_assignment_response(
            db,
            assignment,
        )
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_subject_id=assignment.class_subject_id,
            action="assignment_deleted",
            previous_teacher_membership_id=assignment.teacher_membership_id,
            previous_state="ended",
            new_state="deleted",
            previous_effective_from=assignment.effective_from,
            previous_effective_to=assignment.effective_to,
            acting_admin_id=acting_admin_id,
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
        class_subject_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        status: str | None = None,
        effective_from_from: date | None = None,
        effective_from_to: date | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TeacherAssignmentResponse], int]:
        records, total = await StudentAcademicRepository.list_teacher_assignment_rows(
            db,
            tenant_id,
            teacher_id=teacher_id,
            class_id=class_id,
            class_subject_id=class_subject_id,
            subject_id=subject_id,
            status=status,
            effective_from_from=effective_from_from,
            effective_from_to=effective_from_to,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [
            StudentAcademicService._build_teacher_assignment_response_from_record(
                record
            )
            for record in records
        ], total

    @staticmethod
    async def assign_subject_to_class(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: ClassSubjectTeacherCreate,
    ) -> ClassSubjectTeacherResponse:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, payload.class_id)
        if (
            classroom is None
            or not classroom.is_active
            or classroom.archived_at is not None
        ):
            raise NotFoundException("Class not found or inactive.")
        subject = await SubjectRepository.get_subject_by_id(
            db, tenant_id, payload.subject_id
        )
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
            active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db,
                tenant_id,
                class_subject.id,
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
            if (
                field in payload.model_fields_set
                and getattr(payload, field) is not None
            ):
                setattr(row, field, getattr(payload, field))
        row = await StudentAcademicRepository.save_class_subject_teacher(db, row)
        await db.commit()
        return ClassSubjectTeacherResponse.model_validate(row)

    @staticmethod
    async def create_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicSessionCreate,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicSession:
        if await StudentAcademicRepository.get_academic_session_by_name(
            db,
            tenant_id,
            payload.name,
        ):
            raise ConflictException("Academic session already exists.")
        await StudentAcademicService._validate_session_dates(
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
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
        await StudentAcademicService._validate_next_session_link(
            db,
            tenant_id=tenant_id,
            session_id=row.id,
            next_academic_session_id=payload.next_academic_session_id,
            start_date=row.start_date,
            end_date=row.end_date,
        )
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="session",
            entity_id=row.id,
            action="created",
            previous_status=None,
            new_status=row.status.value,
            acting_admin_id=acting_admin_id,
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
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("name") is None:
            update_data.pop("name", None)
        if row.status == AcademicSessionStatus.OPEN:
            critical = {"name", "start_date", "end_date"}
            if critical.intersection(update_data):
                raise ConflictException(
                    "Only progression configuration can be edited after opening."
                )
        effective_start_date = update_data.get("start_date", row.start_date)
        effective_end_date = update_data.get("end_date", row.end_date)
        await StudentAcademicService._validate_session_dates(
            start_date=effective_start_date,
            end_date=effective_end_date,
        )
        if "name" in update_data and update_data["name"] != row.name:
            if await StudentAcademicRepository.get_academic_session_by_name(
                db,
                tenant_id,
                update_data["name"],
            ):
                raise ConflictException("Academic session name already exists.")
        next_id = update_data.get(
            "next_academic_session_id", row.next_academic_session_id
        )
        await StudentAcademicService._validate_next_session_link(
            db,
            tenant_id=tenant_id,
            session_id=row.id,
            next_academic_session_id=next_id,
            start_date=effective_start_date,
            end_date=effective_end_date,
        )
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
        *,
        search: str | None = None,
        status: AcademicSessionStatus | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
    ) -> tuple[list[AcademicSession], int]:
        return await StudentAcademicRepository.list_academic_sessions(
            db,
            tenant_id,
            skip,
            limit,
            search=search,
            status=status,
            is_current=is_current,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )

    @staticmethod
    async def create_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicTermCreate,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicTerm:
        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            payload.academic_session_id,
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

        existing = await StudentAcademicRepository.get_term_by_session_and_name(
            db,
            tenant_id,
            academic_session.id,
            payload.name,
        )

        if existing is not None:
            raise ConflictException("Academic term already exists in this session.")

        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=academic_session,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
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
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="created",
            previous_status=None,
            new_status=term.status.value,
            acting_admin_id=acting_admin_id,
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
            raise ConflictException("Only draft academic terms can be edited.")

        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("name") is None:
            update_data.pop("name", None)

        effective_start_date = update_data.get(
            "start_date",
            term.start_date,
        )
        effective_end_date = update_data.get(
            "end_date",
            term.end_date,
        )

        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            term.academic_session_id,
        )
        if academic_session is None:
            raise NotFoundException("Academic session not found.")
        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=academic_session,
            name=update_data.get("name", term.name),
            start_date=effective_start_date,
            end_date=effective_end_date,
            exclude_term_id=term.id,
        )

        new_name = update_data.get("name")

        if new_name is not None and new_name != term.name:
            existing = await StudentAcademicRepository.get_term_by_session_and_name(
                db,
                tenant_id,
                term.academic_session_id,
                new_name,
            )

            if existing is not None and existing.id != term.id:
                raise ConflictException("Academic term already exists in this session.")

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
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id=tenant_id,
            term_id=term_id,
            lock=True,
        )

        if term is None:
            raise NotFoundException("Academic term not found ")

        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException("Only a draft academic term can be opened")

        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=term.academic_session_id,
            lock=True,
        )

        if academic_session is None:
            raise NotFoundException("Academic session not found")

        if (
            academic_session.status != AcademicSessionStatus.OPEN
            or not academic_session.is_current
        ):
            raise ConflictException(
                "The session must be open before a term can be opened"
            )

        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=academic_session,
            name=term.name,
            start_date=term.start_date,
            end_date=term.end_date,
            exclude_term_id=term.id,
        )

        current_term = await StudentAcademicRepository.get_current_term(
            db=db,
            tenant_id=tenant_id,
        )

        if current_term is not None and current_term.id != term.id:
            raise ConflictException(
                "Another academic term is currently open. Close it first"
            )

        from app.modules.school_calendar.service import SchoolCalendarService

        calendar_readiness = await SchoolCalendarService.term_calendar_readiness(
            db,
            tenant_id=tenant_id,
            term_id=term.id,
        )
        if calendar_readiness.get("blockers"):
            raise ConflictException(
                "Academic term cannot be opened until its calendar is ready.",
                payload={
                    "blocker_messages": calendar_readiness.get("blockers", []),
                    "dependency_counts": calendar_readiness.get("counts", {}),
                    "calendar_id": calendar_readiness.get("calendar_id"),
                },
            )

        previous_status = term.status
        term.status = AcademicTermStatus.OPEN
        term.is_current = True
        term.opened_at = datetime.now(timezone.utc)
        term.opened_by_admin_id = admin_id
        term.closing_started_at = None
        term.closed_at = None
        term.closed_by_admin_id = None

        try:
            term = await StudentAcademicRepository.save_academic_term(
                db,
                term,
            )
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=tenant_id,
                entity_type="term",
                entity_id=term.id,
                action="opened",
                previous_status=previous_status.value,
                new_status=term.status.value,
                acting_admin_id=admin_id,
            )
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Another academic term is currently open. Close it first"
            ) from exc

        await db.commit()
        return term

    @staticmethod
    async def start_academic_term_closure(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db=db,
            tenant_id=tenant_id,
            term_id=term_id,
            lock=True,
        )

        if term is None:
            raise NotFoundException("Academic term not found")

        if term.status == AcademicTermStatus.CLOSING:
            return term

        if term.status != AcademicTermStatus.OPEN:
            raise ConflictException("Only an open academic term can start closing")

        preview = await StudentAcademicService.academic_term_dependency_preview(
            db,
            tenant_id,
            term_id,
        )
        if not preview.can_close:
            StudentAcademicService._raise_dependency_conflict(
                "Academic term has blockers and cannot start closing.",
                preview,
            )

        previous_status = term.status
        now = datetime.now(timezone.utc)
        term.status = AcademicTermStatus.CLOSING
        term.closing_started_at = now
        term = await StudentAcademicRepository.save_academic_term(db, term)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="closing_started",
            previous_status=previous_status.value,
            new_status=term.status.value,
            acting_admin_id=admin_id,
        )
        await db.commit()
        return term

    @staticmethod
    async def finalize_academic_term_closure(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db=db,
            tenant_id=tenant_id,
            term_id=term_id,
            lock=True,
        )

        if term is None:
            raise NotFoundException("Academic term not found")

        if term.status != AcademicTermStatus.CLOSING:
            raise ConflictException("Only a closing academic term can be finalized")

        preview = await StudentAcademicService.academic_term_dependency_preview(
            db,
            tenant_id,
            term_id,
        )
        if not preview.can_close:
            StudentAcademicService._raise_dependency_conflict(
                "Academic term has blockers and cannot be finalized.",
                preview,
            )

        previous_status = term.status
        now = datetime.now(timezone.utc)
        term.status = AcademicTermStatus.CLOSED
        term.is_current = False
        term.closing_started_at = term.closing_started_at or now
        term.closed_at = now
        term.closed_by_admin_id = admin_id

        term = await StudentAcademicRepository.save_academic_term(
            db,
            term,
        )
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="closed",
            previous_status=previous_status.value,
            new_status=term.status.value,
            acting_admin_id=admin_id,
        )

        from app.modules.school_calendar.service import SchoolCalendarService

        await SchoolCalendarService.archive_term_calendar(
            db,
            tenant_id=tenant_id,
            academic_term_id=term.id,
            acting_admin_id=admin_id,
        )

        await db.commit()
        return term

    @staticmethod
    async def cancel_academic_term_closure(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        admin_id: uuid.UUID,
        *,
        reason: str,
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id=tenant_id,
            term_id=term_id,
            lock=True,
        )
        if term is None:
            raise NotFoundException("Academic term not found")
        if term.status != AcademicTermStatus.CLOSING:
            raise ConflictException(
                "Only a closing academic term can have closure cancelled."
            )

        current_term = await StudentAcademicRepository.get_current_term(
            db,
            tenant_id=tenant_id,
        )
        if current_term is not None and current_term.id != term.id:
            raise ConflictException("Another academic term is currently open.")

        previous_status = term.status
        term.status = AcademicTermStatus.OPEN
        term.is_current = True
        term.closing_started_at = None
        term.closed_at = None
        term.closed_by_admin_id = None
        term = await StudentAcademicRepository.save_academic_term(db, term)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="closure_cancelled",
            previous_status=previous_status.value,
            new_status=term.status.value,
            acting_admin_id=admin_id,
            reason=reason,
        )
        await db.commit()
        return term

    @staticmethod
    async def close_academic_term(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        return await StudentAcademicService.start_academic_term_closure(
            db,
            tenant_id,
            term_id,
            admin_id,
        )

    @staticmethod
    async def list_academic_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        academic_session_id: uuid.UUID | None = None,
        statuses: set[AcademicTermStatus] | None = None,
        name: AcademicTermName | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        if academic_session_id is None:
            return await StudentAcademicRepository.list_terms(
                db,
                tenant_id,
                skip,
                limit,
                statuses=statuses,
                name=name,
                is_current=is_current,
                start_date_from=start_date_from,
                start_date_to=start_date_to,
            )
        return await StudentAcademicRepository.list_terms_by_session(
            db,
            tenant_id,
            academic_session_id,
            skip,
            limit,
            statuses=statuses,
            name=name,
            is_current=is_current,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )

    @staticmethod
    async def delete_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        *,
        acting_admin_id: uuid.UUID,
    ) -> AcademicSession:
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            academic_session_id,
            lock=True,
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        preview = await StudentAcademicService.academic_session_dependency_preview(
            db,
            tenant_id,
            academic_session_id,
        )
        if not preview.can_delete:
            StudentAcademicService._raise_dependency_conflict(
                "Only unused draft academic sessions can be deleted.",
                preview,
            )
        response = AcademicSession(
            id=session.id,
            tenant_id=session.tenant_id,
            name=session.name,
            start_date=session.start_date,
            end_date=session.end_date,
            status=session.status,
            is_current=session.is_current,
            closing_started_at=session.closing_started_at,
            closed_at=session.closed_at,
            closed_by_admin_id=session.closed_by_admin_id,
            next_academic_session_id=session.next_academic_session_id,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="session",
            entity_id=session.id,
            action="deleted",
            previous_status=session.status.value,
            new_status="deleted",
            acting_admin_id=acting_admin_id,
        )
        await StudentAcademicRepository.delete_academic_session(db, session)
        await db.commit()
        return response

    @staticmethod
    async def delete_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        acting_admin_id: uuid.UUID,
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(
            db,
            tenant_id,
            term_id,
            lock=True,
        )
        if term is None:
            raise NotFoundException("Academic term not found.")
        preview = await StudentAcademicService.academic_term_dependency_preview(
            db,
            tenant_id,
            term_id,
        )
        if not preview.can_delete:
            StudentAcademicService._raise_dependency_conflict(
                "Only unused draft academic terms can be deleted.",
                preview,
            )
        response = AcademicTerm(
            id=term.id,
            tenant_id=term.tenant_id,
            academic_session_id=term.academic_session_id,
            name=term.name,
            start_date=term.start_date,
            end_date=term.end_date,
            status=term.status,
            is_current=term.is_current,
            opened_at=term.opened_at,
            closing_started_at=term.closing_started_at,
            closed_at=term.closed_at,
            opened_by_admin_id=term.opened_by_admin_id,
            closed_by_admin_id=term.closed_by_admin_id,
            created_at=term.created_at,
            updated_at=term.updated_at,
        )
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="deleted",
            previous_status=term.status.value,
            new_status="deleted",
            acting_admin_id=acting_admin_id,
        )
        await StudentAcademicRepository.delete_academic_term(db, term)
        await db.commit()
        return response

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
        if row.is_active:
            raise ConflictException(
                "Active grading scales cannot be modified. Deactivate them first."
            )

        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        minimum = update_data.get("min_score", row.min_score)
        maximum = update_data.get("max_score", row.max_score)
        if minimum > maximum:
            raise BadRequestException("Minimum score cannot exceed maximum score.")

        # We don't allow activating via update anymore since we have explicit endpoints
        if "is_active" in update_data:
            del update_data["is_active"]

        for field, value in update_data.items():
            setattr(row, field, value)

        row = await StudentAcademicRepository.save_grading_scale(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def activate_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        scale_id: uuid.UUID,
    ) -> GradingScale:
        row = await StudentAcademicRepository.get_grading_scale_by_id(
            db, tenant_id, scale_id
        )
        if row is None:
            raise NotFoundException("Grading scale not found.")
        if row.is_active:
            return row

        await StudentAcademicService._ensure_no_grading_overlap(
            db,
            tenant_id=tenant_id,
            minimum=row.min_score,
            maximum=row.max_score,
            exclude_id=row.id,
        )
        row.is_active = True
        row = await StudentAcademicRepository.save_grading_scale(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def deactivate_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        scale_id: uuid.UUID,
    ) -> GradingScale:
        row = await StudentAcademicRepository.get_grading_scale_by_id(
            db, tenant_id, scale_id
        )
        if row is None:
            raise NotFoundException("Grading scale not found.")
        if not row.is_active:
            return row

        row.is_active = False
        row = await StudentAcademicRepository.save_grading_scale(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def preview_grading_scale_readiness(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> GradingScaleReadiness:
        scales, _ = await StudentAcademicRepository.list_grading_scales(
            db, tenant_id, limit=1000, active_only=True
        )

        if not scales:
            return GradingScaleReadiness(
                is_ready=False,
                missing_coverage=["0.00-100.00"],
                overlaps=[],
                messages=["No active grading scales found."],
            )

        sorted_scales = sorted(scales, key=lambda s: s.min_score)
        missing = []
        overlaps = []
        current = Decimal("0.00")

        for s in sorted_scales:
            if s.min_score > current:
                missing.append(f"{current}-{s.min_score - Decimal('0.01')}")
            elif s.min_score < current:
                overlaps.append(f"{s.min_score}-{current}")
            current = max(current, s.max_score + Decimal("0.01"))

        if current <= Decimal("100.00"):
            missing.append(f"{current}-100.00")

        is_ready = not missing and not overlaps
        messages = []
        if not is_ready:
            messages.append(
                "Grading scale coverage must strictly span 0.00 to 100.00 with no gaps or overlaps."
            )

        return GradingScaleReadiness(
            is_ready=is_ready,
            missing_coverage=missing,
            overlaps=overlaps,
            messages=messages,
        )

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
                compatibility = await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                    db,
                    tenant_id,
                    class_subject.class_id,
                    class_subject.subject_id,
                )
        else:
            compatibility = (
                await StudentAcademicRepository.get_class_subject_teacher_by_id(
                    db,
                    tenant_id,
                    payload.class_subject_teacher_id,
                )
            )
            if compatibility is not None:
                class_subject = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                    db,
                    tenant_id,
                    compatibility.class_id,
                    compatibility.subject_id,
                )
                if class_subject is not None:
                    assignment = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                        db,
                        tenant_id,
                        class_subject.id,
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
            compatibility = (
                await StudentAcademicService._ensure_compatibility_assignment(
                    db,
                    tenant_id=tenant_id,
                    class_subject=class_subject,
                    teacher_membership_id=assignment.teacher_membership_id,
                    is_active=True,
                )
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
            teacher_name = (
                " ".join(
                    part
                    for part in [
                        teacher.teacher_account.first_name,
                        teacher.teacher_account.last_name,
                    ]
                    if part
                )
                or None
            )
        student_name = None
        if student is not None:
            student_name = (
                " ".join(
                    part for part in [student.first_name, student.last_name] if part
                )
                or None
            )
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
                term.name.value
                if term and hasattr(term.name, "value")
                else str(term.name) if term else None
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
        expected = StudentAcademicService._RESULT_FORWARD_TRANSITIONS.get(
            current_status
        )
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
        (
            assignment,
            compatibility,
            class_subject,
        ) = await StudentAcademicService._resolve_assignment_context(
            db,
            tenant_id,
            payload,
        )
        if (
            isinstance(actor, TeacherMembership)
            and assignment.teacher_membership_id != actor.id
        ):
            raise ForbiddenException(
                "Teachers may record scores only for their own assignments."
            )

        student = await StudentRepository.get_by_id(
            db,
            tenant_id,
            payload.student_id,
        )
        if student is None:
            raise NotFoundException("Student not found.")

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
        if not session.is_current or session.status != AcademicSessionStatus.OPEN:
            raise ConflictException(
                "Results can only be modified in the current open session."
            )
        if not term.is_current or term.status != AcademicTermStatus.OPEN:
            raise ConflictException(
                "Results can only be modified in the current open term."
            )

        enrollment = await StudentEnrollmentRepository.get_current(
            db, tenant_id, student.id
        )
        if (
            enrollment is None
            or enrollment.academic_session_id != session.id
            or enrollment.class_id != class_subject.class_id
        ):
            raise ForbiddenException(
                "Student is not enrolled in the assigned class for this session."
            )

        if (
            assignment.effective_from
            and term.end_date
            and assignment.effective_from > term.end_date
        ):
            raise ConflictException("Teacher assignment starts after the term ends.")
        if (
            assignment.effective_to
            and term.start_date
            and assignment.effective_to < term.start_date
        ):
            raise ConflictException("Teacher assignment ends before the term starts.")

        try:
            existing = await StudentAcademicRepository.get_result_by_scope(
                db,
                tenant_id,
                student.id,
                compatibility.id,
                session.id,
                term.id,
                lock=True,
            )
        except Exception:
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
                raise ForbiddenException(
                    "Submitted, approved, and locked scores are not editable by teachers."
                )
            raise ConflictException("Only draft scores can be edited.")
        if payload.status not in StudentAcademicService._RESULT_UPSERT_STATUSES:
            raise BadRequestException(
                "Use the dedicated lifecycle endpoint for approval and locking."
            )

        from sqlalchemy import select

        config = (
            await db.execute(
                select(SchoolAssessmentConfig).where(
                    SchoolAssessmentConfig.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if config is None:
            config = SchoolAssessmentConfig(
                tenant_id=tenant_id, test_max=20, assessment_max=20, exam_max=60
            )

        if payload.test_score is not None and payload.test_score > config.test_max:
            raise BadRequestException(f"Test score cannot exceed {config.test_max}.")
        if (
            payload.assessment_score is not None
            and payload.assessment_score > config.assessment_max
        ):
            raise BadRequestException(
                f"Assessment score cannot exceed {config.assessment_max}."
            )
        if payload.exam_score is not None and payload.exam_score > config.exam_max:
            raise BadRequestException(f"Exam score cannot exceed {config.exam_max}.")

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
        grading_scale_id = None
        if complete:
            scale = await StudentAcademicRepository.find_grade_for_score(
                db,
                tenant_id,
                total,
            )
            if scale is not None:
                grade = scale.grade
                remark = scale.remark
                grading_scale_id = scale.id

        if payload.status == AcademicResultStatus.SUBMITTED and not complete:
            raise BadRequestException(
                "All three scores are required before submission."
            )

        is_new = False
        if existing is None:
            is_new = True
            result = StudentSubjectResult(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_membership_id=assignment.teacher_membership_id,
                class_subject_teacher_id=compatibility.id,
                teacher_assignment_id=assignment.id,
                student_enrollment_id=enrollment.id,
                academic_session_id=session.id,
                academic_term_id=term.id,
                grading_scale_id=grading_scale_id,
                test_score=payload.test_score,
                assessment_score=payload.assessment_score,
                exam_score=payload.exam_score,
                total_score=total,
                grade=grade,
                remark=remark,
                status=payload.status,
                recorded_by_actor_type=(
                    "teacher"
                    if isinstance(actor, TeacherMembership)
                    else "tenant_admin"
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
            result.teacher_assignment_id = assignment.id
            result.teacher_membership_id = assignment.teacher_membership_id
            result.test_score = payload.test_score
            result.assessment_score = payload.assessment_score
            result.exam_score = payload.exam_score
            result.total_score = total
            result.grade = grade
            result.remark = remark
            result.grading_scale_id = grading_scale_id
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

        try:
            result = await StudentAcademicRepository.upsert_result(db, result)
            await db.flush()
        except IntegrityError:
            raise ConflictException("Concurrent modification of this result.")

        actor_id = actor.id if hasattr(actor, "id") else None
        if is_new:
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=tenant_id,
                entity_type="student_result",
                entity_id=result.id,
                action="create",
                previous_status=None,
                new_status=result.status.value,
                acting_admin_id=actor_id if isinstance(actor, TenantAdmin) else None,
            )
        elif not is_new and payload.status != existing.status:
            action = (
                "submit" if payload.status == AcademicResultStatus.SUBMITTED else "edit"
            )
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=tenant_id,
                entity_type="student_result",
                entity_id=result.id,
                action=action,
                previous_status=previous_status.value,
                new_status=result.status.value,
                acting_admin_id=actor_id if isinstance(actor, TenantAdmin) else None,
            )

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

        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, actor.tenant_id, result.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, actor.tenant_id, result.academic_term_id
        )
        if session and (
            not session.is_current or session.status != AcademicSessionStatus.OPEN
        ):
            raise ConflictException(
                "Results can only be modified in the current open session."
            )
        if term and (not term.is_current or term.status != AcademicTermStatus.OPEN):
            raise ConflictException(
                "Results can only be modified in the current open term."
            )

        previous_status = result.status
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
        await db.flush()

        action_map = {
            AcademicResultStatus.SUBMITTED: "submit",
            AcademicResultStatus.APPROVED: "approve",
            AcademicResultStatus.LOCKED: "lock",
        }
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="student_result",
            entity_id=result.id,
            action=action_map.get(payload.status, "status_update"),
            previous_status=previous_status.value,
            new_status=result.status.value,
            acting_admin_id=actor.id,
        )

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

        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, actor.tenant_id, result.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, actor.tenant_id, result.academic_term_id
        )
        if session and (
            not session.is_current or session.status != AcademicSessionStatus.OPEN
        ):
            raise ConflictException(
                "Results can only be modified in the current open session."
            )
        if term and (not term.is_current or term.status != AcademicTermStatus.OPEN):
            raise ConflictException(
                "Results can only be modified in the current open term."
            )

        from app.modules.report_cards.service import ReportCardService

        await ReportCardService.mark_outdated_for_score_change(
            db,
            result.tenant_id,
            result.student_id,
            result.academic_session_id,
            result.academic_term_id,
        )
        previous_status = result.status
        result.status = AcademicResultStatus.DRAFT
        result.submitted_at = None
        result.submitted_by_actor_type = None
        result.submitted_by_actor_id = None
        result.approved_at = None
        result.approved_by_admin_id = None
        result.locked_at = None
        result.locked_by_admin_id = None
        result = await StudentAcademicRepository.upsert_result(db, result)
        await db.flush()

        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="student_result",
            entity_id=result.id,
            action="reopen",
            previous_status=previous_status.value,
            new_status=result.status.value,
            acting_admin_id=actor.id,
            reason=payload.reason,
        )

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
        teacher_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        teacher_assignment_id: uuid.UUID | None = None,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        status: AcademicResultStatus | None = None,
        search: str | None = None,
        is_complete: bool | None = None,
        has_grade: bool | None = None,
    ) -> tuple[list[StudentSubjectResultResponse], int]:
        tenant_id = actor.tenant_id
        finalized_only = False
        if isinstance(actor, TeacherMembership):
            if teacher_id is None:
                teacher_id = actor.id
            elif teacher_id != actor.id:
                raise ForbiddenException("Teachers can only view their own results.")
        elif isinstance(actor, Student):
            student_id = actor.id
            finalized_only = True
        elif isinstance(actor, ParentMembership):
            if student_id is None:
                raise BadRequestException(
                    "student_id is required for parent result access."
                )
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
            subject_id=subject_id,
            teacher_assignment_id=teacher_assignment_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            status=status,
            search=search,
            is_complete=is_complete,
            has_grade=has_grade,
            finalized_only=finalized_only,
        )
        return [
            await StudentAcademicService._build_result_response(db, row) for row in rows
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
        class_subjects, _ = (
            await StudentAcademicRepository.list_class_subjects(
                db,
                actor.tenant_id,
                class_id=student.class_id,
                active_only=True,
                limit=500,
            )
            if student.class_id
            else ([], 0)
        )

        cards: list[StudentSubjectCardResponse] = []
        for class_subject in class_subjects:
            subject = await SubjectRepository.get_subject_by_id(
                db,
                actor.tenant_id,
                class_subject.subject_id,
            )
            assignment = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db,
                actor.tenant_id,
                class_subject.id,
            )
            compatibility = await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                db,
                actor.tenant_id,
                class_subject.class_id,
                class_subject.subject_id,
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
                teacher_name = (
                    " ".join(
                        part
                        for part in [
                            teacher.teacher_account.first_name,
                            teacher.teacher_account.last_name,
                        ]
                        if part
                    )
                    or None
                )
            submitted = bool(
                result is not None and result.status == AcademicResultStatus.LOCKED
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
                        term.name.value
                        if term and hasattr(term.name, "value")
                        else str(term.name) if term else None
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
                    term.name.value
                    if term and hasattr(term.name, "value")
                    else str(term.name) if term else None
                ),
            ),
        )
