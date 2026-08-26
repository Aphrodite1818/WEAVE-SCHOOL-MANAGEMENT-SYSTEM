"""Canonical academic setup, assignment, score, and subject-card services."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.classes.models import AcademicLevelStatus
from app.modules.classes.repository import AcademicLevelRepository, ClassRoomRepository
from app.modules.parents.models import ParentMembership
from app.modules.report_cards.models import ReportCardStatus
from app.modules.student_academics.assessment_repository import AssessmentRepository
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumSubject,
)
from app.modules.student_academics.curriculum_service import CurriculumResolutionService
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
    AssessmentSchemeStatus,
    GradingScale,
    StudentProgressionRunStatus,
    StudentSubjectResult,
    TeacherAssignment,
    TeacherAssignmentLifecycleAudit,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    AcademicSessionCreate,
    AcademicSessionDependencyPreview,
    AcademicSessionResponse,
    AcademicSessionUpdate,
    AcademicTermCreate,
    AcademicTermDependencyPreview,
    AcademicTermResponse,
    AcademicTermUpdate,
    AssessmentComponentScoreResponse,
    GradingScaleCreate,
    GradingScaleReadiness,
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
)
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentEnrollment,
    StudentParentLinkStatus,
)
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentParentLinkRepository,
    StudentRepository,
)
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import (
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import TeacherMembershipRepository
from app.modules.tenant_admins.models import TenantAdmin


class StudentAcademicService:
    """Business rules for academic lifecycle, assignments, and result ownership."""

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

    # ------------------------------------------------------------------
    # Shared lifecycle helpers
    # ------------------------------------------------------------------
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
        *, start_date: date | None, end_date: date | None, require_complete: bool = False
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
            db, tenant_id, next_academic_session_id, lock=True
        )
        if next_session is None:
            raise NotFoundException("Next academic session not found.")
        if next_session.start_date is not None:
            if start_date is not None and next_session.start_date <= start_date:
                raise BadRequestException("Next academic session must start after this session.")
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
                db, tenant_id, cursor.next_academic_session_id, lock=True
            )
            if cursor is None:
                raise NotFoundException("Next academic session chain references a missing session.")

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
            raise BadRequestException("Term start date must fall within the session date range.")
        if session.end_date is not None and end_date is not None and end_date > session.end_date:
            raise BadRequestException("Term end date must fall within the session date range.")
        if start_date is None or end_date is None:
            return
        terms, _ = await StudentAcademicRepository.list_terms_by_session(
            db, tenant_id, session.id, limit=500, statuses=set()
        )
        for term in terms:
            if exclude_term_id is not None and term.id == exclude_term_id:
                continue
            if term.start_date is None or term.end_date is None:
                continue
            if start_date < term.end_date and end_date > term.start_date:
                raise ConflictException("Academic terms in the same session cannot overlap.")
            current_order = StudentAcademicService._TERM_ORDER[name]
            other_order = StudentAcademicService._TERM_ORDER[term.name]
            if current_order < other_order and start_date >= term.start_date:
                raise BadRequestException("Earlier terms must start before later terms.")
            if current_order > other_order and start_date <= term.start_date:
                raise BadRequestException("Later terms must start after earlier terms.")

    @staticmethod
    async def _specialization_blockers_for_next_term(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        term: AcademicTerm,
    ) -> tuple[dict[str, int], list[str]]:
        """Require specialization on the class, never on individual students."""
        terms = list(
            (
                await db.execute(
                    select(AcademicTerm).where(
                        AcademicTerm.tenant_id == tenant_id,
                        AcademicTerm.academic_session_id == term.academic_session_id,
                    )
                )
            ).scalars()
        )
        current_position = StudentAcademicService._TERM_ORDER[term.name]
        later_terms = [
            row for row in terms if StudentAcademicService._TERM_ORDER[row.name] > current_position
        ]
        if not later_terms:
            return {"students_missing_department": 0}, []
        next_term = min(later_terms, key=lambda row: StudentAcademicService._TERM_ORDER[row.name])
        next_position = StudentAcademicService._TERM_ORDER[next_term.name]
        levels = await AcademicLevelRepository.list_for_tenant(db, tenant_id, active_only=True)
        required_levels = {
            level.id: level
            for level in levels
            if level.specialization_required_from_term_position is not None
            and level.specialization_required_from_term_position <= next_position
        }
        if not required_levels:
            return {"students_missing_department": 0}, []
        enrollments = list(
            (
                await db.execute(
                    select(StudentEnrollment)
                    .join(Student, Student.id == StudentEnrollment.student_id)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.academic_session_id == term.academic_session_id,
                        StudentEnrollment.is_current.is_(True),
                        StudentEnrollment.academic_level_id.in_(required_levels),
                        Student.status == AcademicStatus.ACTIVE,
                        Student.is_archived.is_(False),
                    )
                )
            ).scalars()
        )
        class_ids = {row.class_id for row in enrollments if row.class_id is not None}
        assigned_class_ids: set[uuid.UUID] = set()
        if class_ids:
            assigned_class_ids = set(
                (
                    await db.execute(
                        select(ClassTermDepartmentAssignment.class_id).where(
                            ClassTermDepartmentAssignment.tenant_id == tenant_id,
                            ClassTermDepartmentAssignment.academic_term_id == next_term.id,
                            ClassTermDepartmentAssignment.class_id.in_(class_ids),
                        )
                    )
                ).scalars()
            )
        missing_by_level: dict[uuid.UUID, int] = {}
        for enrollment in enrollments:
            if enrollment.class_id is None or enrollment.class_id not in assigned_class_ids:
                missing_by_level[enrollment.academic_level_id] = (
                    missing_by_level.get(enrollment.academic_level_id, 0) + 1
                )
        blockers = [
            (
                f"{count} {required_levels[level_id].name} students are in classes without "
                f"a department for {next_term.name.value.replace('_', ' ').title()}."
            )
            for level_id, count in missing_by_level.items()
        ]
        return {"students_missing_department": sum(missing_by_level.values())}, blockers

    # ------------------------------------------------------------------
    # Session and term lifecycle
    # ------------------------------------------------------------------
    @staticmethod
    async def academic_session_dependency_preview(
        db: AsyncSession, tenant_id: uuid.UUID, session_id: uuid.UUID
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
        if session.status == AcademicSessionStatus.DRAFT and not counts["terms"]:
            blockers.append("Add at least one academic term before opening the session.")
        if session.status == AcademicSessionStatus.OPEN:
            if session.next_academic_session_id is None:
                blockers.append("Configure next_academic_session_id before closure.")
            if counts["open_terms"]:
                blockers.append("Close every term in this session before closing the session.")
            if counts["closing_terms"]:
                blockers.append("Finalize every closing term before closing the session.")
            if counts["draft_results"]:
                blockers.append(
                    "Draft results must be submitted, approved, or removed before closure."
                )
            if counts["submitted_results"]:
                blockers.append("Submitted results must be approved or returned before closure.")
            if counts["approved_but_unlocked_results"]:
                blockers.append("Approved results must be locked before closure.")
            if counts["unpublished_report_cards"]:
                blockers.append("Report cards must be published or archived before closure.")
            if counts["active_or_pending_progression_runs"]:
                blockers.append("A progression run is already active or pending for this session.")
            from app.modules.school_calendar.service import SchoolCalendarService

            terms, _ = await StudentAcademicRepository.list_terms_by_session(
                db, tenant_id, session_id, limit=500, statuses=set()
            )
            missing_calendar_terms = 0
            missing_calendar_dates = 0
            for term in terms:
                contribution = await SchoolCalendarService.inspect_term_closure_readiness(
                    db, tenant_id=tenant_id, term_id=term.id
                )
                if contribution.get("calendar_id") is None:
                    missing_calendar_terms += 1
                missing_calendar_dates += int(
                    contribution.get("counts", {}).get("missing_calendar_dates", 0) or 0
                )
                blockers.extend(contribution.get("blockers", []))
            counts["calendar_history_missing_terms"] = missing_calendar_terms
            counts["missing_calendar_dates"] = missing_calendar_dates
        can_start_closing = session.status == AcademicSessionStatus.OPEN and not blockers
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
            can_progress=can_start_closing and session.next_academic_session_id is not None,
            can_delete=can_delete,
        )

    @staticmethod
    async def academic_term_dependency_preview(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID
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
                blockers.append("Approved results must be locked before closing the term.")
            if counts["unpublished_report_cards"]:
                blockers.append(
                    "Report cards must be published or archived before closing the term."
                )
            from app.modules.school_calendar.service import SchoolCalendarService

            contribution = await SchoolCalendarService.inspect_term_closure_readiness(
                db, tenant_id=tenant_id, term_id=term_id
            )
            counts.update(contribution.get("counts", {}))
            blockers.extend(contribution.get("blockers", []))
            (
                specialization_counts,
                specialization_blockers,
            ) = await StudentAcademicService._specialization_blockers_for_next_term(
                db, tenant_id=tenant_id, term=term
            )
            counts.update(specialization_counts)
            blockers.extend(specialization_blockers)
        can_delete = (
            term.status == AcademicTermStatus.DRAFT
            and not term.is_current
            and counts["results"] == 0
            and counts["report_cards"] == 0
        )
        can_close = (
            term.status in {AcademicTermStatus.OPEN, AcademicTermStatus.CLOSING} and not blockers
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
    async def create_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicSessionCreate,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicSession:
        if await StudentAcademicRepository.get_academic_session_by_name(
            db, tenant_id, payload.name
        ):
            raise ConflictException("Academic session already exists.")
        await StudentAcademicService._validate_session_dates(
            start_date=payload.start_date, end_date=payload.end_date
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
            db, tenant_id, academic_session_id
        )
        if row is None:
            raise NotFoundException("Academic session not found.")
        if row.status in {AcademicSessionStatus.CLOSING, AcademicSessionStatus.CLOSED}:
            raise ConflictException("Closing or closed sessions cannot be edited.")
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("name") is None:
            update_data.pop("name", None)
        if row.status == AcademicSessionStatus.OPEN and {
            "name",
            "start_date",
            "end_date",
        }.intersection(update_data):
            raise ConflictException("Only progression configuration can be edited after opening.")
        effective_start = update_data.get("start_date", row.start_date)
        effective_end = update_data.get("end_date", row.end_date)
        await StudentAcademicService._validate_session_dates(
            start_date=effective_start, end_date=effective_end
        )
        if "name" in update_data and update_data["name"] != row.name:
            if await StudentAcademicRepository.get_academic_session_by_name(
                db, tenant_id, update_data["name"]
            ):
                raise ConflictException("Academic session name already exists.")
        next_id = update_data.get("next_academic_session_id", row.next_academic_session_id)
        await StudentAcademicService._validate_next_session_link(
            db,
            tenant_id=tenant_id,
            session_id=row.id,
            next_academic_session_id=next_id,
            start_date=effective_start,
            end_date=effective_end,
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
        **filters,
    ) -> tuple[list[AcademicSession], int]:
        return await StudentAcademicRepository.list_academic_sessions(
            db, tenant_id, skip, limit, **filters
        )

    @staticmethod
    async def delete_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicSessionResponse:
        row = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, session_id, lock=True
        )
        if row is None:
            raise NotFoundException("Academic session not found.")
        preview = await StudentAcademicService.academic_session_dependency_preview(
            db, tenant_id, session_id
        )
        if not preview.can_delete:
            StudentAcademicService._raise_dependency_conflict(
                "Only unused draft academic sessions can be deleted.", preview
            )
        response = AcademicSessionResponse.model_validate(row)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="session",
            entity_id=row.id,
            action="deleted",
            previous_status=row.status.value,
            new_status="deleted",
            acting_admin_id=acting_admin_id,
        )
        await StudentAcademicRepository.delete_academic_session(db, row)
        await db.commit()
        return response

    @staticmethod
    async def create_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicTermCreate,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicTerm:
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, payload.academic_session_id
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        if session.status in {AcademicSessionStatus.CLOSING, AcademicSessionStatus.CLOSED}:
            raise ConflictException(
                "Terms cannot be added to a closing or closed academic session."
            )
        if await StudentAcademicRepository.get_term_by_session_and_name(
            db, tenant_id, session.id, payload.name
        ):
            raise ConflictException("Academic term already exists in this session.")
        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=session,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        term = await StudentAcademicRepository.create_academic_term(
            db,
            AcademicTerm(
                tenant_id=tenant_id,
                academic_session_id=session.id,
                name=payload.name,
                start_date=payload.start_date,
                end_date=payload.end_date,
                status=AcademicTermStatus.DRAFT,
                is_current=False,
            ),
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
        from app.modules.subscriptions.cache import invalidate_tenant_subscription_cache

        await invalidate_tenant_subscription_cache(tenant_id)
        return term

    @staticmethod
    async def update_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        payload: AcademicTermUpdate,
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id)
        if term is None:
            raise NotFoundException("Academic term not found.")
        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException("Only draft academic terms can be edited.")
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("name") is None:
            update_data.pop("name", None)
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, term.academic_session_id
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=session,
            name=update_data.get("name", term.name),
            start_date=update_data.get("start_date", term.start_date),
            end_date=update_data.get("end_date", term.end_date),
            exclude_term_id=term.id,
        )
        if "name" in update_data and update_data["name"] != term.name:
            existing = await StudentAcademicRepository.get_term_by_session_and_name(
                db, tenant_id, term.academic_session_id, update_data["name"]
            )
            if existing is not None and existing.id != term.id:
                raise ConflictException("Academic term already exists in this session.")
        for field, value in update_data.items():
            setattr(term, field, value)
        term = await StudentAcademicRepository.save_academic_term(db, term)
        await db.commit()
        return term

    @staticmethod
    async def open_academic_term(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id, lock=True)
        if term is None:
            raise NotFoundException("Academic term not found.")
        if term.status != AcademicTermStatus.DRAFT:
            raise ConflictException("Only a draft academic term can be opened.")
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, term.academic_session_id, lock=True
        )
        if session is None:
            raise NotFoundException("Academic session not found.")
        if session.status != AcademicSessionStatus.OPEN or not session.is_current:
            raise ConflictException("The session must be open before a term can be opened.")
        current_term = await StudentAcademicRepository.get_current_term(db, tenant_id)
        if current_term is not None and current_term.id != term.id:
            raise ConflictException("Another academic term is currently open. Close it first.")
        await StudentAcademicService._validate_term_dates_and_order(
            db,
            tenant_id=tenant_id,
            session=session,
            name=term.name,
            start_date=term.start_date,
            end_date=term.end_date,
            exclude_term_id=term.id,
        )
        from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService
        from app.modules.school_calendar.service import SchoolCalendarService

        await TermPlanEntitlementService.ensure_open_eligible(db, tenant_id, term.id)
        readiness = await SchoolCalendarService.term_calendar_readiness(
            db, tenant_id=tenant_id, term_id=term.id
        )
        if readiness.get("blockers"):
            raise ConflictException(
                "Academic term cannot be opened until its calendar is ready.",
                payload={
                    "blocker_messages": readiness.get("blockers", []),
                    "dependency_counts": readiness.get("counts", {}),
                    "calendar_id": readiness.get("calendar_id"),
                },
            )
        previous = term.status
        term.status = AcademicTermStatus.OPEN
        term.is_current = True
        term.opened_at = datetime.now(timezone.utc)
        term.opened_by_admin_id = admin_id
        term.closing_started_at = None
        term.closed_at = None
        term.closed_by_admin_id = None
        try:
            term = await StudentAcademicRepository.save_academic_term(db, term)
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=tenant_id,
                entity_type="term",
                entity_id=term.id,
                action="opened",
                previous_status=previous.value,
                new_status=term.status.value,
                acting_admin_id=admin_id,
            )
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Another academic term is currently open. Close it first."
            ) from exc
        await db.commit()
        return term

    @staticmethod
    async def start_academic_term_closure(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id, lock=True)
        if term is None:
            raise NotFoundException("Academic term not found.")
        if term.status == AcademicTermStatus.CLOSING:
            return term
        if term.status != AcademicTermStatus.OPEN:
            raise ConflictException("Only an open academic term can start closing.")
        preview = await StudentAcademicService.academic_term_dependency_preview(
            db, tenant_id, term_id
        )
        if not preview.can_close:
            StudentAcademicService._raise_dependency_conflict(
                "Academic term has blockers and cannot start closing.", preview
            )
        previous = term.status
        term.status = AcademicTermStatus.CLOSING
        term.closing_started_at = datetime.now(timezone.utc)
        term = await StudentAcademicRepository.save_academic_term(db, term)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="closing_started",
            previous_status=previous.value,
            new_status=term.status.value,
            acting_admin_id=admin_id,
        )
        await db.commit()
        return term

    @staticmethod
    async def finalize_academic_term_closure(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID, admin_id: uuid.UUID
    ) -> AcademicTerm:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id, lock=True)
        if term is None:
            raise NotFoundException("Academic term not found.")
        if term.status != AcademicTermStatus.CLOSING:
            raise ConflictException("Only a closing academic term can be finalized.")
        preview = await StudentAcademicService.academic_term_dependency_preview(
            db, tenant_id, term_id
        )
        if not preview.can_close:
            StudentAcademicService._raise_dependency_conflict(
                "Academic term has blockers and cannot be finalized.", preview
            )
        previous = term.status
        now = datetime.now(timezone.utc)
        term.status = AcademicTermStatus.CLOSED
        term.is_current = False
        term.closing_started_at = term.closing_started_at or now
        term.closed_at = now
        term.closed_by_admin_id = admin_id
        term = await StudentAcademicRepository.save_academic_term(db, term)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="term",
            entity_id=term.id,
            action="closed",
            previous_status=previous.value,
            new_status=term.status.value,
            acting_admin_id=admin_id,
        )
        from app.modules.school_calendar.service import SchoolCalendarService
        from app.modules.subscriptions.term_entitlement_service import TermPlanEntitlementService

        await SchoolCalendarService.archive_term_calendar(
            db,
            tenant_id=tenant_id,
            academic_term_id=term.id,
            acting_admin_id=admin_id,
        )
        await TermPlanEntitlementService.close_for_term(db, tenant_id, term.id)
        await db.commit()
        from app.modules.subscriptions.cache import invalidate_tenant_subscription_cache

        await invalidate_tenant_subscription_cache(tenant_id)
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
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id, lock=True)
        if term is None:
            raise NotFoundException("Academic term not found.")
        if term.status != AcademicTermStatus.CLOSING:
            raise ConflictException("Only a closing academic term can have closure cancelled.")
        current = await StudentAcademicRepository.get_current_term(db, tenant_id)
        if current is not None and current.id != term.id:
            raise ConflictException("Another academic term is currently open.")
        previous = term.status
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
            previous_status=previous.value,
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
            db, tenant_id, term_id, admin_id
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
                statuses,
                name=name.value if hasattr(name, "value") else name,
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
            statuses,
            name=name.value if hasattr(name, "value") else name,
            is_current=is_current,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )

    @staticmethod
    async def delete_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        acting_admin_id: uuid.UUID | None = None,
    ) -> AcademicTermResponse:
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id, lock=True)
        if term is None:
            raise NotFoundException("Academic term not found.")
        preview = await StudentAcademicService.academic_term_dependency_preview(
            db, tenant_id, term_id
        )
        if not preview.can_delete:
            StudentAcademicService._raise_dependency_conflict(
                "Only unused draft academic terms can be deleted.", preview
            )
        response = AcademicTermResponse.model_validate(term)
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

    # ------------------------------------------------------------------
    # Grading scales
    # ------------------------------------------------------------------
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
            db, tenant_id, limit=500, active_only=True
        )
        for row in rows:
            if exclude_id is not None and row.id == exclude_id:
                continue
            if minimum <= row.max_score and maximum >= row.min_score:
                raise ConflictException("Grading scale ranges cannot overlap.")

    @staticmethod
    async def create_grading_scale(
        db: AsyncSession, tenant_id: uuid.UUID, payload: GradingScaleCreate
    ) -> GradingScale:
        if await StudentAcademicRepository.get_grading_scale_by_grade(db, tenant_id, payload.grade):
            raise ConflictException("This grade already exists.")
        if payload.is_active:
            await StudentAcademicService._ensure_no_grading_overlap(
                db,
                tenant_id=tenant_id,
                minimum=payload.min_score,
                maximum=payload.max_score,
            )
        row = await StudentAcademicRepository.create_grading_scale(
            db, GradingScale(tenant_id=tenant_id, **payload.model_dump())
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
        row = await StudentAcademicRepository.get_grading_scale_by_id(db, tenant_id, scale_id)
        if row is None:
            raise NotFoundException("Grading scale not found.")
        if row.is_active:
            raise ConflictException(
                "Active grading scales cannot be modified. Deactivate them first."
            )
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        update_data.pop("is_active", None)
        minimum = update_data.get("min_score", row.min_score)
        maximum = update_data.get("max_score", row.max_score)
        if minimum > maximum:
            raise BadRequestException("Minimum score cannot exceed maximum score.")
        for field, value in update_data.items():
            setattr(row, field, value)
        row = await StudentAcademicRepository.save_grading_scale(db, row)
        await db.commit()
        await db.refresh(row)
        return row

    @staticmethod
    async def activate_grading_scale(
        db: AsyncSession, tenant_id: uuid.UUID, scale_id: uuid.UUID
    ) -> GradingScale:
        row = await StudentAcademicRepository.get_grading_scale_by_id(db, tenant_id, scale_id)
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
        db: AsyncSession, tenant_id: uuid.UUID, scale_id: uuid.UUID
    ) -> GradingScale:
        row = await StudentAcademicRepository.get_grading_scale_by_id(db, tenant_id, scale_id)
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
        db: AsyncSession, tenant_id: uuid.UUID
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
        sorted_scales = sorted(scales, key=lambda item: item.min_score)
        missing: list[str] = []
        overlaps: list[str] = []
        current = Decimal("0.00")
        for scale in sorted_scales:
            if scale.min_score > current:
                missing.append(f"{current}-{scale.min_score - Decimal('0.01')}")
            elif scale.min_score < current:
                overlaps.append(f"{scale.min_score}-{current}")
            current = max(current, scale.max_score + Decimal("0.01"))
        if current <= Decimal("100.00"):
            missing.append(f"{current}-100.00")
        ready = not missing and not overlaps
        return GradingScaleReadiness(
            is_ready=ready,
            missing_coverage=missing,
            overlaps=overlaps,
            messages=(
                []
                if ready
                else [
                    "Grading scale coverage must strictly span 0.00 to 100.00 with no gaps or overlaps."
                ]
            ),
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
            db, tenant_id, skip, limit, active_only
        )

    # ------------------------------------------------------------------
    # Teacher assignments
    # ------------------------------------------------------------------
    @staticmethod
    async def _load_curriculum_subject_context(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> tuple[CurriculumSubject, Curriculum]:
        row = (
            await db.execute(
                select(CurriculumSubject, Curriculum)
                .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
                .where(
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.id == curriculum_subject_id,
                    CurriculumSubject.is_active.is_(True),
                    Curriculum.tenant_id == tenant_id,
                )
            )
        ).first()
        if row is None:
            raise NotFoundException("Curriculum subject not found or inactive.")
        return row[0], row[1]

    @staticmethod
    async def _ensure_curriculum_subject_offered_to_class(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        curriculum_subject: CurriculumSubject,
        curriculum: Curriculum,
        academic_term_id: uuid.UUID,
    ) -> None:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        if classroom is None or not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Classroom must be active before assigning a teacher.")
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, classroom.academic_level_id)
        if level is None or level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException("Academic level must be active before assigning a teacher.")
        if classroom.academic_level_id != curriculum.academic_level_id:
            raise ConflictException(
                "The selected curriculum subject does not belong to the class academic level."
            )
        term = await StudentAcademicRepository.get_term_by_id(db, tenant_id, academic_term_id)
        if term is None:
            raise NotFoundException("Academic term not found.")
        class_department = (
            await db.execute(
                select(ClassTermDepartmentAssignment).where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term.id,
                )
            )
        ).scalar_one_or_none()
        offerings = await CurriculumResolutionService.resolve_curriculum_offerings(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
            academic_term_id=term.id,
            department_id=(
                class_department.department_id if class_department is not None else None
            ),
        )
        if curriculum_subject.id not in {offering.curriculum_subject_id for offering in offerings}:
            raise ConflictException(
                "This curriculum subject is not offered to the class for the selected term."
            )

    @staticmethod
    async def _validate_teacher_capability(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_membership_id: uuid.UUID,
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
        return membership

    @staticmethod
    async def _build_teacher_assignment_response(
        db: AsyncSession, assignment: TeacherAssignment
    ) -> TeacherAssignmentResponse:
        curriculum_subject, _ = await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=assignment.tenant_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
        )
        classroom = await ClassRoomRepository.get_by_id(
            db, assignment.tenant_id, assignment.class_id
        )
        subject = await SubjectRepository.get_subject_by_id(
            db, assignment.tenant_id, curriculum_subject.subject_id
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
            curriculum_subject_id=assignment.curriculum_subject_id,
            teacher_membership_id=assignment.teacher_membership_id,
            class_id=assignment.class_id,
            class_name=classroom.academic_level_name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=curriculum_subject.subject_id,
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
    def _build_teacher_assignment_response_from_record(
        record: dict,
    ) -> TeacherAssignmentResponse:
        assignment = record["assignment"]
        return TeacherAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
            teacher_membership_id=assignment.teacher_membership_id,
            class_id=record.get("class_id") or assignment.class_id,
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
    async def _record_teacher_assignment_audit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID | None,
        class_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
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
                class_id=class_id,
                curriculum_subject_id=curriculum_subject_id,
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
    async def create_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TeacherAssignmentCreate,
        acting_admin_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        (
            curriculum_subject,
            curriculum,
        ) = await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=payload.curriculum_subject_id,
        )
        await StudentAcademicService._ensure_curriculum_subject_offered_to_class(
            db,
            tenant_id=tenant_id,
            class_id=payload.class_id,
            curriculum_subject=curriculum_subject,
            curriculum=curriculum,
            academic_term_id=payload.academic_term_id,
        )
        subject = await SubjectRepository.get_subject_by_id(
            db, tenant_id, curriculum_subject.subject_id
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before assigning a teacher.")
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
        )
        active = (
            await StudentAcademicRepository.get_active_teacher_assignment_for_curriculum_subject(
                db,
                tenant_id,
                curriculum_subject.id,
                payload.class_id,
            )
        )
        if active is not None:
            raise ConflictException(
                "An active teacher assignment already exists for this curriculum subject."
            )
        effective_from = payload.effective_from or date.today()
        history = await StudentAcademicRepository.list_teacher_assignments_for_curriculum_subject(
            db,
            tenant_id,
            curriculum_subject.id,
            payload.class_id,
            lock=True,
        )
        if any(row.effective_to is None or row.effective_to >= effective_from for row in history):
            raise ConflictException(
                "Teacher assignment effective date overlaps existing assignment history."
            )
        try:
            assignment = await StudentAcademicRepository.create_teacher_assignment(
                db,
                TeacherAssignment(
                    tenant_id=tenant_id,
                    class_id=payload.class_id,
                    curriculum_subject_id=curriculum_subject.id,
                    teacher_membership_id=payload.teacher_membership_id,
                    is_active=True,
                    effective_from=effective_from,
                    effective_to=None,
                ),
            )
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "An active teacher assignment already exists for this curriculum subject."
            ) from exc
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_id=assignment.class_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
            action="assignment_created",
            new_teacher_membership_id=assignment.teacher_membership_id,
            previous_state=None,
            new_state="active",
            new_effective_from=assignment.effective_from,
            acting_admin_id=acting_admin_id,
        )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db, assignment)

    @staticmethod
    async def teacher_assignment_dependency_preview(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> TeacherAssignmentDependencyPreview:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db, tenant_id, assignment_id
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        counts = await StudentAcademicRepository.count_teacher_assignment_dependencies(
            db, tenant_id, assignment_id
        )
        has_dependencies = any(counts.values())
        blockers = (
            ["Historical results or report-card lines reference this assignment."]
            if has_dependencies
            else []
        )
        return TeacherAssignmentDependencyPreview(
            assignment_id=assignment.id,
            dependency_counts=counts,
            can_end=assignment.is_active,
            can_reassign=assignment.is_active and assignment.effective_to is None,
            can_delete=(not assignment.is_active and not has_dependencies),
            blocker_messages=blockers,
        )

    @staticmethod
    async def end_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentEnd,
        acting_admin_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db, tenant_id, assignment_id, lock=True
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        if not assignment.is_active:
            if assignment.effective_to is None:
                raise ConflictException("Historical assignment is missing an effective end date.")
            if payload.effective_to is not None and payload.effective_to != assignment.effective_to:
                raise ConflictException(
                    "Teacher assignment is already ended with a different effective date."
                )
            return await StudentAcademicService._build_teacher_assignment_response(db, assignment)
        effective_to = payload.effective_to or date.today()
        if effective_to < assignment.effective_from:
            raise ConflictException("Assignment end date cannot be before its start date.")
        previous_teacher = assignment.teacher_membership_id
        assignment.is_active = False
        assignment.effective_to = effective_to
        assignment = await StudentAcademicRepository.save_teacher_assignment(db, assignment)
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_id=assignment.class_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
            action="assignment_ended",
            previous_teacher_membership_id=previous_teacher,
            new_teacher_membership_id=previous_teacher,
            previous_state="active",
            new_state="ended",
            previous_effective_from=assignment.effective_from,
            new_effective_from=assignment.effective_from,
            new_effective_to=assignment.effective_to,
            acting_admin_id=acting_admin_id,
        )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db, assignment)

    @staticmethod
    async def reassign_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentReassign,
        acting_admin_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        current = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db, tenant_id, assignment_id, lock=True
        )
        if current is None:
            raise NotFoundException("Teacher assignment not found.")
        if not current.is_active or current.effective_to is not None:
            raise ConflictException("Only the current active teacher assignment can be reassigned.")
        (
            curriculum_subject,
            curriculum,
        ) = await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=current.curriculum_subject_id,
        )
        current_term = await StudentAcademicRepository.get_current_term(db, tenant_id)
        if current_term is not None:
            await StudentAcademicService._ensure_curriculum_subject_offered_to_class(
                db,
                tenant_id=tenant_id,
                class_id=current.class_id,
                curriculum_subject=curriculum_subject,
                curriculum=curriculum,
                academic_term_id=current_term.id,
            )
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
        )
        active = (
            await StudentAcademicRepository.get_active_teacher_assignment_for_curriculum_subject(
                db,
                tenant_id,
                current.curriculum_subject_id,
                current.class_id,
                lock=True,
            )
        )
        if active is None or active.id != current.id:
            raise ConflictException(
                "The selected assignment is no longer the active teacher assignment."
            )
        if current.teacher_membership_id == payload.teacher_membership_id:
            raise ConflictException("This teacher is already assigned.")
        effective_from = payload.effective_from or date.today()
        if effective_from <= current.effective_from:
            raise ConflictException(
                "Replacement effective date must be after the current assignment start date."
            )
        later = await StudentAcademicRepository.get_later_teacher_assignments(
            db,
            tenant_id,
            current.curriculum_subject_id,
            current.class_id,
            current.effective_from,
            exclude_id=current.id,
            lock=True,
        )
        if later:
            raise ConflictException(
                "Cannot reassign because later assignment history already exists."
            )
        previous_teacher = current.teacher_membership_id
        current.is_active = False
        current.effective_to = effective_from - timedelta(days=1)
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
                    class_id=current.class_id,
                    curriculum_subject_id=current.curriculum_subject_id,
                    teacher_membership_id=payload.teacher_membership_id,
                    is_active=True,
                    effective_from=effective_from,
                    effective_to=None,
                ),
            )
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "An active teacher assignment already exists for this curriculum subject."
            ) from exc
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=replacement.id,
            class_id=replacement.class_id,
            curriculum_subject_id=replacement.curriculum_subject_id,
            action="teacher_reassigned",
            previous_teacher_membership_id=previous_teacher,
            new_teacher_membership_id=replacement.teacher_membership_id,
            previous_state="active",
            new_state="active",
            previous_effective_from=current.effective_from,
            previous_effective_to=current.effective_to,
            new_effective_from=replacement.effective_from,
            acting_admin_id=acting_admin_id,
        )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db, replacement)

    @staticmethod
    async def delete_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentDelete,
        acting_admin_id: uuid.UUID | None = None,
    ) -> TeacherAssignmentResponse:
        _ = payload.confirmation
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db, tenant_id, assignment_id, lock=True
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        if assignment.is_active:
            raise ConflictException("End the teacher assignment before deleting it.")
        preview = await StudentAcademicService.teacher_assignment_dependency_preview(
            db, tenant_id, assignment.id
        )
        if not preview.can_delete:
            StudentAcademicService._raise_dependency_conflict(
                "This teacher assignment has dependencies and cannot be deleted.", preview
            )
        response = await StudentAcademicService._build_teacher_assignment_response(db, assignment)
        await StudentAcademicService._record_teacher_assignment_audit(
            db,
            tenant_id=tenant_id,
            assignment_id=assignment.id,
            class_id=assignment.class_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
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
        curriculum_subject_id: uuid.UUID | None = None,
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
            curriculum_subject_id=curriculum_subject_id,
            subject_id=subject_id,
            status=status,
            effective_from_from=effective_from_from,
            effective_from_to=effective_from_to,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [
            StudentAcademicService._build_teacher_assignment_response_from_record(record)
            for record in records
        ], total

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    @staticmethod
    async def _resolve_assignment_context(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: StudentSubjectResultUpsert,
    ) -> tuple[TeacherAssignment, CurriculumSubject]:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db, tenant_id, payload.teacher_assignment_id
        )
        if assignment is None or not assignment.is_active:
            raise NotFoundException("Active teacher assignment not found.")
        curriculum_subject, _ = await StudentAcademicService._load_curriculum_subject_context(
            db,
            tenant_id=tenant_id,
            curriculum_subject_id=assignment.curriculum_subject_id,
        )
        subject = await SubjectRepository.get_subject_by_id(
            db, tenant_id, curriculum_subject.subject_id
        )
        if subject is None or not subject.is_active or subject.archived_at is not None:
            raise ConflictException("Subject must be active before recording results.")
        return assignment, curriculum_subject

    @staticmethod
    async def _build_result_response(
        db: AsyncSession,
        result: StudentSubjectResult,
        component_rows=None,
        scheme=None,
    ) -> StudentSubjectResultResponse:
        student = await StudentRepository.get_by_id(
            db, result.tenant_id, result.student_id, include_archived=True
        )
        classroom = await ClassRoomRepository.get_by_id(db, result.tenant_id, result.class_id)
        subject = await SubjectRepository.get_subject_by_id(db, result.tenant_id, result.subject_id)
        teacher = await TeacherMembershipRepository.get_by_id(
            db,
            result.teacher_membership_id,
            tenant_id=result.tenant_id,
            load_account=True,
        )
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, result.tenant_id, result.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, result.tenant_id, result.academic_term_id
        )
        if scheme is None:
            scheme = await AssessmentRepository.get_scheme(
                db, result.tenant_id, result.assessment_scheme_id
            )
        if component_rows is None:
            component_rows = await StudentAcademicRepository.list_result_component_scores(
                db, result.tenant_id, result
            )
        components = [
            AssessmentComponentScoreResponse(
                assessment_component_id=component.id,
                name=component.name,
                code=component.code,
                position=component.position,
                maximum_score=component.maximum_score,
                score=score.score if score is not None else None,
            )
            for component, score in component_rows
        ]
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
        student_name = (
            " ".join(part for part in [student.first_name, student.last_name] if part)
            if student is not None
            else None
        ) or None
        return StudentSubjectResultResponse(
            id=result.id,
            tenant_id=result.tenant_id,
            student_id=result.student_id,
            student_name=student_name,
            admission_number=student.admission_number if student else None,
            class_id=result.class_id,
            class_name=classroom.academic_level_name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=result.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_membership_id=result.teacher_membership_id,
            teacher_name=teacher_name,
            curriculum_subject_id=result.curriculum_subject_id,
            teacher_assignment_id=result.teacher_assignment_id,
            academic_session_id=result.academic_session_id,
            academic_session_name=session.name if session else None,
            academic_term_id=result.academic_term_id,
            academic_term_name=(
                term.name.value
                if term and hasattr(term.name, "value")
                else str(term.name)
                if term
                else None
            ),
            assessment_scheme_id=result.assessment_scheme_id,
            assessment_scheme_name=scheme.name if scheme else "Assessment scheme",
            components=components,
            maximum_score=sum(
                (component.maximum_score for component, _ in component_rows),
                Decimal("0"),
            ),
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
    async def _ensure_result_complete(db: AsyncSession, result: StudentSubjectResult) -> None:
        rows = await StudentAcademicRepository.list_result_component_scores(
            db, result.tenant_id, result
        )
        if not rows or any(score is None for _, score in rows):
            raise BadRequestException("Every configured assessment component is required.")

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
        current_status: AcademicResultStatus, next_status: AcademicResultStatus
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
        if isinstance(actor, TeacherMembership):
            raise ForbiddenException("Teachers have read-only access to academic results.")
        assignment, curriculum_subject = await StudentAcademicService._resolve_assignment_context(
            db, tenant_id, payload
        )
        student = await StudentRepository.get_by_id(db, tenant_id, payload.student_id)
        if student is None:
            raise NotFoundException("Student not found.")
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, tenant_id, payload.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, tenant_id, payload.academic_term_id
        )
        if session is None or term is None or term.academic_session_id != session.id:
            raise NotFoundException("Academic session or term is invalid.")
        if not session.is_current or session.status != AcademicSessionStatus.OPEN:
            raise ConflictException("Results can only be modified in the current open session.")
        if not term.is_current or term.status != AcademicTermStatus.OPEN:
            raise ConflictException("Results can only be modified in the current open term.")
        enrollment = await StudentEnrollmentRepository.get_authoritative_for_session(
            db, tenant_id, student.id, session.id
        )
        if enrollment is None or enrollment.class_id != assignment.class_id:
            raise ForbiddenException(
                "Student is not enrolled in the assigned class for this session."
            )
        offerings = await CurriculumResolutionService.resolve_student_offerings(
            db,
            tenant_id=tenant_id,
            student_id=student.id,
            academic_term_id=term.id,
        )
        if curriculum_subject.id not in {offering.curriculum_subject_id for offering in offerings}:
            raise ForbiddenException(
                "This subject is not offered to the student's class specialization for this term."
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
        existing = await StudentAcademicRepository.get_result_by_scope(
            db,
            tenant_id,
            student.id,
            assignment.id,
            session.id,
            term.id,
            lock=True,
        )
        if (
            existing is not None
            and existing.status not in StudentAcademicService._RESULT_EDITABLE_STATUSES
        ):
            raise ConflictException("Only draft scores can be edited.")
        if payload.status not in StudentAcademicService._RESULT_UPSERT_STATUSES:
            raise BadRequestException(
                "Use the dedicated lifecycle endpoint for approval and locking."
            )
        scheme = await AssessmentRepository.get_active_scheme(db, tenant_id)
        if scheme is None or scheme.status != AssessmentSchemeStatus.ACTIVE:
            raise ConflictException("An active assessment scheme is required before score entry.")
        components = await AssessmentRepository.list_components(db, tenant_id, scheme.id)
        if not components or sum(
            (item.maximum_score for item in components), Decimal("0")
        ) != Decimal("100"):
            raise ConflictException("The active assessment scheme must total 100.")
        component_by_id = {item.id: item for item in components}
        provided = {
            item.assessment_component_id: item.score
            for item in payload.component_scores
            if item.score is not None
        }
        if set(provided) - set(component_by_id):
            raise BadRequestException(
                "One or more scores reference an invalid assessment component."
            )
        for component_id, score in provided.items():
            component = component_by_id[component_id]
            if score > component.maximum_score:
                raise BadRequestException(
                    f"{component.name} score cannot exceed {component.maximum_score}."
                )
        total = sum(provided.values(), Decimal("0"))
        complete = len(provided) == len(components)
        grade = remark = None
        grading_scale_id = None
        if complete:
            scale = await StudentAcademicRepository.find_grade_for_score(db, tenant_id, total)
            if scale is not None:
                grade = scale.grade
                remark = scale.remark
                grading_scale_id = scale.id
        if payload.status == AcademicResultStatus.SUBMITTED and not complete:
            raise BadRequestException("Every configured assessment component is required.")
        if payload.status == AcademicResultStatus.SUBMITTED and grade is None:
            raise ConflictException("An active grading scale must cover the final numeric score.")
        actor_type = StudentAcademicService._result_actor_type(actor)
        is_new = existing is None
        previous_status = existing.status if existing is not None else None
        if existing is None:
            result = StudentSubjectResult(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=assignment.class_id,
                subject_id=curriculum_subject.subject_id,
                teacher_membership_id=assignment.teacher_membership_id,
                curriculum_subject_id=curriculum_subject.id,
                teacher_assignment_id=assignment.id,
                student_enrollment_id=enrollment.id,
                academic_session_id=session.id,
                academic_term_id=term.id,
                assessment_scheme_id=scheme.id,
                grading_scale_id=grading_scale_id,
                total_score=total,
                grade=grade,
                remark=remark,
                status=payload.status,
                recorded_by_actor_type=actor_type,
                recorded_by_actor_id=actor.id,
            )
        else:
            result = existing
            if result.assessment_scheme_id != scheme.id:
                raise ConflictException(
                    "This result belongs to a different assessment scheme and cannot be edited."
                )
            result.teacher_assignment_id = assignment.id
            result.teacher_membership_id = assignment.teacher_membership_id
            result.total_score = total
            result.grade = grade
            result.remark = remark
            result.grading_scale_id = grading_scale_id
            result.status = payload.status
            result.recorded_by_actor_type = actor_type
            result.recorded_by_actor_id = actor.id
        if payload.status == AcademicResultStatus.SUBMITTED:
            if previous_status is not None and previous_status != payload.status:
                StudentAcademicService._ensure_forward_result_transition(
                    previous_status, payload.status
                )
            StudentAcademicService._apply_result_lifecycle_metadata(
                result, actor=actor, next_status=payload.status
            )
        try:
            result = await StudentAcademicRepository.upsert_result(db, result)
            await StudentAcademicRepository.replace_result_scores(db, result, provided)
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("Concurrent modification of this result.") from exc
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=tenant_id,
            entity_type="student_result",
            entity_id=result.id,
            action=(
                "create"
                if is_new
                else "submit"
                if previous_status != result.status
                and result.status == AcademicResultStatus.SUBMITTED
                else "edit"
            ),
            previous_status=previous_status.value if previous_status else None,
            new_status=result.status.value,
            acting_admin_id=actor.id if isinstance(actor, TenantAdmin) else None,
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
        result = await StudentAcademicRepository.get_result_by_id(db, actor.tenant_id, result_id)
        if result is None:
            raise NotFoundException("Result not found.")
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, actor.tenant_id, result.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, actor.tenant_id, result.academic_term_id
        )
        if session and (not session.is_current or session.status != AcademicSessionStatus.OPEN):
            raise ConflictException("Results can only be modified in the current open session.")
        if term and (not term.is_current or term.status != AcademicTermStatus.OPEN):
            raise ConflictException("Results can only be modified in the current open term.")
        previous = result.status
        StudentAcademicService._ensure_forward_result_transition(result.status, payload.status)
        if payload.status == AcademicResultStatus.SUBMITTED:
            await StudentAcademicService._ensure_result_complete(db, result)
        result.status = payload.status
        StudentAcademicService._apply_result_lifecycle_metadata(
            result, actor=actor, next_status=payload.status
        )
        result = await StudentAcademicRepository.upsert_result(db, result)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="student_result",
            entity_id=result.id,
            action={
                AcademicResultStatus.SUBMITTED: "submit",
                AcademicResultStatus.APPROVED: "approve",
                AcademicResultStatus.LOCKED: "lock",
            }.get(payload.status, "status_update"),
            previous_status=previous.value,
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
        result = await StudentAcademicRepository.get_result_by_id(db, actor.tenant_id, result_id)
        if result is None:
            raise NotFoundException("Result not found.")
        if result.status != AcademicResultStatus.LOCKED:
            raise BadRequestException("Only locked results can be reopened.")
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db, actor.tenant_id, result.academic_session_id
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db, actor.tenant_id, result.academic_term_id
        )
        if session and (not session.is_current or session.status != AcademicSessionStatus.OPEN):
            raise ConflictException("Results can only be modified in the current open session.")
        if term and (not term.is_current or term.status != AcademicTermStatus.OPEN):
            raise ConflictException("Results can only be modified in the current open term.")
        from app.modules.report_cards.service import ReportCardService

        await ReportCardService.mark_outdated_for_score_change(
            db,
            result.tenant_id,
            result.student_id,
            result.academic_session_id,
            result.academic_term_id,
        )
        previous = result.status
        result.status = AcademicResultStatus.DRAFT
        result.submitted_at = None
        result.submitted_by_actor_type = None
        result.submitted_by_actor_id = None
        result.approved_at = None
        result.approved_by_admin_id = None
        result.locked_at = None
        result.locked_by_admin_id = None
        result = await StudentAcademicRepository.upsert_result(db, result)
        await StudentAcademicService._record_academic_lifecycle(
            db,
            tenant_id=actor.tenant_id,
            entity_type="student_result",
            entity_id=result.id,
            action="reopen",
            previous_status=previous.value,
            new_status=result.status.value,
            acting_admin_id=actor.id,
            reason=payload.reason,
        )
        await db.commit()
        return await StudentAcademicService._build_result_response(db, result)

    @staticmethod
    async def _ensure_parent_can_view_student(
        db: AsyncSession, parent: ParentMembership, student_id: uuid.UUID
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
                raise BadRequestException("student_id is required for parent result access.")
            await StudentAcademicService._ensure_parent_can_view_student(db, actor, student_id)
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
        component_rows = await StudentAcademicRepository.list_result_component_scores_batch(
            db, tenant_id, rows
        )
        schemes = await AssessmentRepository.get_schemes_by_id(
            db, tenant_id, {row.assessment_scheme_id for row in rows}
        )
        return [
            await StudentAcademicService._build_result_response(
                db,
                row,
                component_rows.get(row.id, []),
                schemes.get(row.assessment_scheme_id),
            )
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
            await StudentAcademicService._ensure_parent_can_view_student(db, actor, student_id)
        student = await StudentRepository.get_by_id(
            db, actor.tenant_id, student_id, include_archived=True
        )
        if student is None:
            raise NotFoundException("Student not found.")
        session = await StudentAcademicRepository.get_current_academic_session(db, actor.tenant_id)
        term = await StudentAcademicRepository.get_current_term(db, actor.tenant_id)
        enrollment = (
            await StudentEnrollmentRepository.get_authoritative_for_session(
                db, actor.tenant_id, student.id, session.id
            )
            if session is not None
            else None
        )
        classroom = (
            await ClassRoomRepository.get_by_id(db, actor.tenant_id, enrollment.class_id)
            if enrollment is not None and enrollment.class_id is not None
            else None
        )
        curriculum = (
            await CurriculumResolutionService.resolve_student_curriculum(
                db,
                tenant_id=actor.tenant_id,
                student_id=student.id,
                academic_term_id=term.id,
            )
            if term is not None
            else []
        )
        active_scheme = await AssessmentRepository.get_active_scheme(db, actor.tenant_id)
        active_components = (
            await AssessmentRepository.list_components(db, actor.tenant_id, active_scheme.id)
            if active_scheme is not None
            else []
        )
        cards: list[StudentSubjectCardResponse] = []
        for offering in curriculum:
            subject = await SubjectRepository.get_subject_by_id(
                db, actor.tenant_id, offering.subject_id
            )
            assignment = (
                await StudentAcademicRepository.get_active_teacher_assignment_for_curriculum_subject(
                    db,
                    actor.tenant_id,
                    offering.curriculum_subject_id,
                    classroom.id,
                )
                if classroom is not None
                else None
            )
            result = None
            if session is not None and term is not None:
                result = (
                    await db.execute(
                        select(StudentSubjectResult).where(
                            StudentSubjectResult.tenant_id == actor.tenant_id,
                            StudentSubjectResult.student_id == student.id,
                            StudentSubjectResult.curriculum_subject_id
                            == offering.curriculum_subject_id,
                            StudentSubjectResult.academic_session_id == session.id,
                            StudentSubjectResult.academic_term_id == term.id,
                        )
                    )
                ).scalar_one_or_none()
            teacher = (
                await TeacherMembershipRepository.get_by_id(
                    db,
                    assignment.teacher_membership_id,
                    tenant_id=actor.tenant_id,
                    load_account=True,
                )
                if assignment is not None
                else None
            )
            teacher_name = (
                " ".join(
                    part
                    for part in [
                        teacher.teacher_account.first_name,
                        teacher.teacher_account.last_name,
                    ]
                    if part
                )
                if teacher is not None
                else None
            ) or None
            locked = bool(result is not None and result.status == AcademicResultStatus.LOCKED)
            component_rows = (
                await StudentAcademicRepository.list_result_component_scores(
                    db, actor.tenant_id, result
                )
                if locked
                else [(component, None) for component in active_components]
            )
            cards.append(
                StudentSubjectCardResponse(
                    id=offering.curriculum_subject_id,
                    result_id=result.id if locked else None,
                    curriculum_subject_id=offering.curriculum_subject_id,
                    class_id=classroom.id if classroom else None,
                    class_name=classroom.academic_level_name if classroom else None,
                    class_arm=classroom.arm if classroom else None,
                    subject_id=offering.subject_id,
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
                        else str(term.name)
                        if term
                        else None
                    ),
                    assessment_scheme_id=(
                        result.assessment_scheme_id
                        if locked
                        else active_scheme.id
                        if active_scheme
                        else None
                    ),
                    assessment_scheme_name=(active_scheme.name if active_scheme else None),
                    components=[
                        AssessmentComponentScoreResponse(
                            assessment_component_id=component.id,
                            name=component.name,
                            code=component.code,
                            position=component.position,
                            maximum_score=component.maximum_score,
                            score=score.score if score is not None else None,
                        )
                        for component, score in component_rows
                    ],
                    maximum_score=sum(
                        (component.maximum_score for component, _ in component_rows),
                        Decimal("0"),
                    ),
                    total_score=result.total_score if locked else None,
                    grade=result.grade if locked else None,
                    remark=result.remark if locked else None,
                    status="locked" if locked else "pending",
                    is_complete=locked,
                )
            )
        return StudentSubjectCardListResponse(
            items=cards,
            total=len(cards),
            context=StudentSubjectCardContextResponse(
                class_id=enrollment.class_id if enrollment else None,
                class_name=classroom.academic_level_name if classroom else None,
                class_arm=classroom.arm if classroom else None,
                academic_session_id=session.id if session else None,
                academic_session_name=session.name if session else None,
                academic_term_id=term.id if term else None,
                academic_term_name=(
                    term.name.value
                    if term and hasattr(term.name, "value")
                    else str(term.name)
                    if term
                    else None
                ),
            ),
        )
