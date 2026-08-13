"""Canonical student progression decisions and placement operations."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.auth_identity.models import ActorType
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.models import (
    AcademicLevelProgressionMode,
    ClassRoom,
    ProgressionSelectionTargetType,
)
from app.modules.classes.repository import AcademicLevelRepository, ClassRoomRepository
from app.modules.parents.models import Parent
from app.modules.parents.repository import ParentMembershipRepository
from app.modules.student_academics.lifecycle_repository import (
    AcademicSessionLifecycleRepository,
    StudentProgressionRepository,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    StudentProgressionItem,
    StudentProgressionItemAction,
    StudentProgressionItemStatus,
    StudentProgressionRun,
)
from app.modules.student_academics.schemas import (
    AcademicSessionResponse,
    ProgressionDestinationResponse,
    StudentProgressionItemResponse,
    StudentProgressionSelectionResponse,
)
from app.modules.student_academics.service import StudentAcademicService
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentEnrollment,
    StudentEnrollmentOutcome,
    StudentParentLinkStatus,
)
from app.modules.students.repository import (
    StudentEnrollmentRepository,
    StudentParentLinkRepository,
    StudentRepository,
)
from app.modules.students.service import StudentLifecycleService
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.teachers.models import Teacher


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AcademicProgressionService:
    """Own deterministic, student-selected, and terminal progression rules."""

    @staticmethod
    async def open_session(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        session_id: uuid.UUID,
    ) -> AcademicSessionResponse:
        try:
            session = await AcademicSessionLifecycleRepository.get_by_id(
                db, actor.tenant_id, session_id, lock=True
            )
            if session is None:
                raise NotFoundException("Academic session not found.")
            if session.status != AcademicSessionStatus.DRAFT:
                raise ConflictException("Only draft sessions can be opened.")
            await StudentAcademicService._validate_session_dates(
                start_date=session.start_date,
                end_date=session.end_date,
                require_complete=True,
            )
            from app.modules.school_calendar.repository import SchoolCalendarRepository

            if await SchoolCalendarRepository.get_configuration(db, actor.tenant_id) is None:
                raise ConflictException(
                    "Configure the school calendar before opening an academic session.",
                    payload={
                        "blocker_messages": [
                            "School calendar configuration is required before session opening."
                        ]
                    },
                )
            preview = await StudentAcademicService.academic_session_dependency_preview(
                db, actor.tenant_id, session.id
            )
            if not preview.can_open:
                StudentAcademicService._raise_dependency_conflict(
                    "Academic session has blockers and cannot be opened.", preview
                )
            current = await AcademicSessionLifecycleRepository.get_current_open(
                db, actor.tenant_id, lock=True
            )
            if current is not None and current.id != session.id:
                raise ConflictException(
                    "Close the current academic session before opening another."
                )
            previous_status = session.status
            session.status = AcademicSessionStatus.OPEN
            session.is_current = True
            session.closing_started_at = None
            session.closed_at = None
            session.closed_by_admin_id = None
            await AcademicSessionLifecycleRepository.save(db, session)
            await StudentAcademicService._record_academic_lifecycle(
                db,
                tenant_id=actor.tenant_id,
                entity_type="session",
                entity_id=session.id,
                action="opened",
                previous_status=previous_status.value,
                new_status=session.status.value,
                acting_admin_id=actor.id,
            )
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "Close the current academic session before opening another."
            ) from exc
        except Exception:
            await db.rollback()
            raise
        await db.refresh(session)
        return AcademicSessionResponse.model_validate(session)

    @staticmethod
    async def _load_progression_enrollments(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> list[StudentEnrollment]:
        result = await db.execute(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_session_id == academic_session_id,
                StudentEnrollment.is_current.is_(True),
            )
            .order_by(StudentEnrollment.student_id)
            .with_for_update()
        )
        return list(result.scalars().all())

    @staticmethod
    async def _validate_class_graph(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        enrollments: list[StudentEnrollment],
    ) -> dict[uuid.UUID, tuple[ClassRoom, ClassRoom | None]]:
        graph: dict[uuid.UUID, tuple[ClassRoom, ClassRoom | None]] = {}
        for class_id in {row.class_id for row in enrollments}:
            classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
            if classroom is None:
                raise ConflictException(f"Enrollment references missing class {class_id}.")
            level = await AcademicLevelRepository.get_by_id(
                db, tenant_id, classroom.academic_level_id, lock=True
            )
            if level is None or not level.is_active or level.archived_at is not None:
                raise ConflictException(f"Class {classroom.id} has no active academic level.")

            target_class: ClassRoom | None = None
            if level.progression_mode == AcademicLevelProgressionMode.DIRECT:
                if level.next_level_id is None:
                    raise ConflictException(
                        f"Configure the next academic level for {level.name} before closure."
                    )
                target_level = await AcademicLevelRepository.get_by_id(
                    db, tenant_id, level.next_level_id, lock=True
                )
                if target_level is None or not target_level.is_active or target_level.archived_at:
                    raise ConflictException(f"The next level for {level.name} is inactive.")
                target_class = await ClassRoomRepository.get_by_level_and_arm(
                    db, tenant_id, level.next_level_id, classroom.arm
                )
                if target_class is not None and (
                    not target_class.is_active or target_class.archived_at is not None
                ):
                    target_class = None
            elif level.progression_mode == AcademicLevelProgressionMode.STUDENT_SELECTION:
                options = await AcademicLevelRepository.list_progression_options(
                    db, tenant_id, level.id, lock=True
                )
                if not options:
                    raise ConflictException(
                        f"Configure student-selection destinations for {level.name} before closure."
                    )
            graph[classroom.id] = (classroom, target_class)
        return graph

    @staticmethod
    async def _downgrade_graduated_parent_access(
        db: AsyncSession, *, tenant_id: uuid.UUID, student_id: uuid.UUID
    ) -> None:
        links = await StudentParentLinkRepository.list_for_student(
            db,
            tenant_id,
            student_id,
            statuses=[StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY],
            lock=True,
        )
        membership_ids: set[uuid.UUID] = set()
        for link in links:
            link.status = StudentParentLinkStatus.ALUMNI_READ_ONLY
            link.ended_at = None
            link.end_reason = None
            await StudentParentLinkRepository.save(db, link)
            membership_ids.add(link.parent_membership_id)
        for membership_id in membership_ids:
            membership = await ParentMembershipRepository.get_by_id(
                db, membership_id, tenant_id=tenant_id, lock=True
            )
            if membership is not None:
                await StudentLifecycleService._recalculate_parent_membership(db, membership)

    @staticmethod
    async def _create_next_enrollment(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student: Student,
        item: StudentProgressionItem,
        target_class: ClassRoom,
        next_session: AcademicSession,
        changed_by_admin_id: uuid.UUID | None,
    ) -> StudentProgressionItem:
        if student.is_archived or student.status != AcademicStatus.ACTIVE:
            item.status = StudentProgressionItemStatus.CANCELLED
            item.reason = "Student lifecycle is no longer active."
            item.processed_at = _utc_now()
            return await StudentProgressionRepository.save_item(db, item)
        if not target_class.is_active or target_class.archived_at is not None:
            item.status = StudentProgressionItemStatus.BLOCKED
            item.reason = "Selected classroom is inactive."
            return await StudentProgressionRepository.save_item(db, item)
        if next_session.status not in {AcademicSessionStatus.DRAFT, AcademicSessionStatus.OPEN}:
            raise ConflictException("The target academic session is not available for placement.")

        current = await StudentEnrollmentRepository.get_current(
            db, tenant_id, student.id, lock=True
        )
        if current is not None:
            if (
                current.academic_session_id == next_session.id
                and current.class_id == target_class.id
            ):
                item.to_enrollment_id = current.id
                item.to_class_id = current.class_id
                item.status = StudentProgressionItemStatus.COMPLETED
                item.reason = "Next class already assigned."
                item.processed_at = _utc_now()
                return await StudentProgressionRepository.save_item(db, item)
            raise ConflictException("Student already has a different current enrollment.")

        next_enrollment = await StudentEnrollmentRepository.add(
            db,
            StudentEnrollment(
                tenant_id=tenant_id,
                student_id=student.id,
                class_id=target_class.id,
                academic_session_id=next_session.id,
                started_on=next_session.start_date or date.today(),
                is_current=True,
                outcome=StudentEnrollmentOutcome.PROMOTED,
                reason="Academic progression placement",
                changed_by_admin_id=changed_by_admin_id,
            ),
        )
        student.class_id = target_class.id
        await StudentRepository.save(db, student)
        item.to_enrollment_id = next_enrollment.id
        item.to_class_id = target_class.id
        item.status = StudentProgressionItemStatus.COMPLETED
        item.reason = "Next class assigned."
        item.processed_at = _utc_now()
        return await StudentProgressionRepository.save_item(db, item)

    @staticmethod
    async def _progress_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        run: StudentProgressionRun,
        enrollment: StudentEnrollment,
        classroom: ClassRoom,
        target_class: ClassRoom | None,
        next_session: AcademicSession,
        effective_date: date,
    ) -> StudentProgressionItem:
        existing = await StudentProgressionRepository.get_item_by_run_and_student(
            db, run.id, enrollment.student_id, lock=True
        )
        if existing is not None:
            return existing
        student = await StudentRepository.get_by_id(
            db, actor.tenant_id, enrollment.student_id, lock=True, include_archived=True
        )
        if student is None:
            raise ConflictException(f"Enrollment {enrollment.id} references a missing student.")
        if student.is_archived or student.promotion_hold or student.status != AcademicStatus.ACTIVE:
            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_class_id=classroom.id,
                    action=StudentProgressionItemAction.SKIP,
                    status=StudentProgressionItemStatus.CANCELLED,
                    reason="Student is archived, on promotion hold, or not active.",
                    processed_at=_utc_now(),
                ),
            )

        level = await AcademicLevelRepository.get_by_id(
            db, actor.tenant_id, classroom.academic_level_id, lock=True
        )
        if level is None:
            raise ConflictException("Classroom academic level is missing.")
        enrollment.is_current = False
        enrollment.ended_on = effective_date
        enrollment.changed_by_admin_id = actor.id

        if level.progression_mode == AcademicLevelProgressionMode.TERMINAL:
            enrollment.outcome = StudentEnrollmentOutcome.GRADUATED
            enrollment.reason = "Automatic terminal-level graduation"
            await StudentEnrollmentRepository.save(db, enrollment)
            student.status = AcademicStatus.GRADUATED
            student.graduation_date = effective_date
            student.class_id = None
            student.promotion_hold = True
            student.is_active = False
            student.account_status = StudentAccountStatus.INACTIVE
            await StudentRepository.save(db, student)
            await StudentLifecycleService._revoke_student_access(db, student, reason="graduated")
            await AuthIdentityService.deactivate_for_actor(
                db, actor_type=ActorType.STUDENT, actor_id=student.id
            )
            await AcademicProgressionService._downgrade_graduated_parent_access(
                db, tenant_id=actor.tenant_id, student_id=student.id
            )
            return await StudentProgressionRepository.add_item(
                db,
                StudentProgressionItem(
                    tenant_id=actor.tenant_id,
                    progression_run_id=run.id,
                    student_id=student.id,
                    from_enrollment_id=enrollment.id,
                    from_class_id=classroom.id,
                    action=StudentProgressionItemAction.TERMINAL,
                    status=StudentProgressionItemStatus.COMPLETED,
                    reason="Terminal level completed.",
                    processed_at=_utc_now(),
                ),
            )

        enrollment.outcome = StudentEnrollmentOutcome.PROMOTED
        enrollment.reason = "Academic session completed"
        await StudentEnrollmentRepository.save(db, enrollment)
        is_direct = level.progression_mode == AcademicLevelProgressionMode.DIRECT
        direct_needs_placement = is_direct and target_class is None
        item = await StudentProgressionRepository.add_item(
            db,
            StudentProgressionItem(
                tenant_id=actor.tenant_id,
                progression_run_id=run.id,
                student_id=student.id,
                from_enrollment_id=enrollment.id,
                from_class_id=classroom.id,
                action=(
                    StudentProgressionItemAction.DIRECT
                    if is_direct
                    else StudentProgressionItemAction.STUDENT_SELECTION
                ),
                status=(
                    StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT
                    if direct_needs_placement
                    else (
                        StudentProgressionItemStatus.COMPLETED
                        if is_direct
                        else StudentProgressionItemStatus.AWAITING_SELECTION
                    )
                ),
                selected_level_id=(level.next_level_id if direct_needs_placement else None),
                reason=(
                    (
                        f"No active {classroom.arm} arm exists in the next level; "
                        "administrator classroom placement is required."
                    )
                    if direct_needs_placement
                    else (
                        "Promoted to configured next class."
                        if is_direct
                        else "Choose a configured progression destination."
                    )
                ),
            ),
        )
        if level.progression_mode == AcademicLevelProgressionMode.STUDENT_SELECTION:
            student.class_id = None
            await StudentRepository.save(db, student)
            return item
        if target_class is None:
            student.class_id = None
            await StudentRepository.save(db, student)
            return item
        return await AcademicProgressionService._create_next_enrollment(
            db,
            tenant_id=actor.tenant_id,
            student=student,
            item=item,
            target_class=target_class,
            next_session=next_session,
            changed_by_admin_id=actor.id,
        )

    @staticmethod
    async def _selection_response(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        item: StudentProgressionItem,
    ) -> StudentProgressionSelectionResponse:
        source_class = await ClassRoomRepository.get_by_id(db, tenant_id, item.from_class_id)
        if source_class is None:
            raise ConflictException("Progression source classroom is missing.")
        level = await AcademicLevelRepository.get_by_id(
            db, tenant_id, source_class.academic_level_id
        )
        if level is None:
            raise ConflictException("Progression source level is missing.")
        student = await StudentRepository.get_by_id(
            db, tenant_id, item.student_id, include_archived=True
        )
        destinations: list[ProgressionDestinationResponse] = []
        options = await AcademicLevelRepository.list_progression_options(db, tenant_id, level.id)
        for option in options:
            if option.target_level_id:
                target_level = await AcademicLevelRepository.get_by_id(
                    db, tenant_id, option.target_level_id
                )
                if target_level and target_level.is_active and not target_level.archived_at:
                    destinations.append(
                        ProgressionDestinationResponse(
                            id=target_level.id,
                            target_type=ProgressionSelectionTargetType.LEVEL.value,
                            label=target_level.name,
                            academic_level_id=target_level.id,
                        )
                    )
            elif option.target_classroom_id:
                target_class = await ClassRoomRepository.get_by_id(
                    db, tenant_id, option.target_classroom_id
                )
                if target_class and target_class.is_active and not target_class.archived_at:
                    destinations.append(
                        ProgressionDestinationResponse(
                            id=target_class.id,
                            target_type=ProgressionSelectionTargetType.CLASSROOM.value,
                            label=f"{target_class.academic_level_name} {target_class.arm}",
                            academic_level_id=target_class.academic_level_id,
                        )
                    )
        selected_label = next(
            (
                destination.label
                for destination in destinations
                if destination.id in {item.selected_level_id, item.selected_classroom_id}
            ),
            None,
        )
        if selected_label is None and item.selected_level_id is not None:
            selected_level = await AcademicLevelRepository.get_by_id(
                db, tenant_id, item.selected_level_id
            )
            if selected_level is not None:
                selected_label = selected_level.name
        return StudentProgressionSelectionResponse(
            item=StudentProgressionItemResponse.model_validate(item),
            student_name=(
                " ".join(part for part in [student.first_name, student.last_name] if part)
                if student
                else None
            ),
            admission_number=student.admission_number if student else None,
            source_class_label=f"{level.name} {source_class.arm}",
            selection_target_type=(
                level.selection_target_type.value if level.selection_target_type else None
            ),
            selected_destination_label=selected_label,
            destinations=destinations,
        )

    @staticmethod
    async def get_student_selection(
        db: AsyncSession, *, student: Student
    ) -> StudentProgressionSelectionResponse | None:
        item = await StudentProgressionRepository.get_latest_item_for_student(
            db, student.tenant_id, student.id
        )
        if item is None or item.action != StudentProgressionItemAction.STUDENT_SELECTION:
            return None
        run = await StudentProgressionRepository.get_run_by_id(
            db, student.tenant_id, item.progression_run_id
        )
        if run is None:
            return None
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db, student.tenant_id, run.next_academic_session_id
        )
        if next_session is None or next_session.status != AcademicSessionStatus.OPEN:
            return None
        return await AcademicProgressionService._selection_response(
            db, tenant_id=student.tenant_id, item=item
        )

    @staticmethod
    async def get_admin_student_selection(
        db: AsyncSession, *, actor: TenantAdmin, student_id: uuid.UUID
    ) -> StudentProgressionSelectionResponse | None:
        student = await StudentRepository.get_by_id(
            db, actor.tenant_id, student_id, include_archived=True
        )
        if student is None:
            raise NotFoundException("Student not found.")
        item = await StudentProgressionRepository.get_latest_item_for_student(
            db, actor.tenant_id, student.id
        )
        if item is None:
            return None
        if (
            item.action != StudentProgressionItemAction.STUDENT_SELECTION
            and item.status != StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT
        ):
            return None
        return await AcademicProgressionService._selection_response(
            db, tenant_id=actor.tenant_id, item=item
        )

    @staticmethod
    async def get_parent_child_selection(
        db: AsyncSession,
        *,
        parent: Parent,
        student_id: uuid.UUID,
    ) -> StudentProgressionSelectionResponse | None:
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
            raise NotFoundException("Linked student was not found.")
        student = await StudentRepository.get_by_id(
            db, parent.tenant_id, student_id, include_archived=True
        )
        if student is None:
            raise NotFoundException("Linked student was not found.")
        return await AcademicProgressionService.get_student_selection(db, student=student)

    @staticmethod
    async def list_teacher_pending_progressions(
        db: AsyncSession,
        *,
        teacher: Teacher,
    ) -> list[StudentProgressionItemResponse]:
        classrooms = await ClassRoomRepository.list_by_teacher_membership(
            db,
            teacher.tenant_id,
            teacher.id,
        )
        class_ids = [classroom.id for classroom in classrooms]
        if not class_ids:
            return []
        result = await db.execute(
            select(StudentProgressionItem)
            .where(
                StudentProgressionItem.tenant_id == teacher.tenant_id,
                StudentProgressionItem.from_class_id.in_(class_ids),
                StudentProgressionItem.status.in_(
                    [
                        StudentProgressionItemStatus.AWAITING_SELECTION,
                        StudentProgressionItemStatus.SELECTION_SUBMITTED,
                        StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT,
                        StudentProgressionItemStatus.BLOCKED,
                    ]
                ),
            )
            .order_by(StudentProgressionItem.updated_at.desc())
        )
        return [
            StudentProgressionItemResponse.model_validate(item) for item in result.scalars().all()
        ]

    @staticmethod
    async def _select_destination(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        destination_id: uuid.UUID,
        changed_by_admin_id: uuid.UUID | None,
    ) -> StudentProgressionSelectionResponse:
        item = await StudentProgressionRepository.get_latest_item_for_student(
            db, tenant_id, student_id, lock=True
        )
        if item is None or item.action != StudentProgressionItemAction.STUDENT_SELECTION:
            raise NotFoundException("Pending student progression was not found.")
        if item.status in {
            StudentProgressionItemStatus.COMPLETED,
            StudentProgressionItemStatus.CANCELLED,
        }:
            if destination_id in {item.selected_level_id, item.selected_classroom_id}:
                return await AcademicProgressionService._selection_response(
                    db, tenant_id=tenant_id, item=item
                )
            raise ConflictException("This progression can no longer be changed.")
        student = await StudentRepository.get_by_id(
            db, tenant_id, student_id, lock=True, include_archived=True
        )
        if student is None or student.is_archived or student.status != AcademicStatus.ACTIVE:
            item.status = StudentProgressionItemStatus.CANCELLED
            item.reason = "Student lifecycle is no longer active."
            await StudentProgressionRepository.save_item(db, item)
            await db.commit()
            raise ConflictException("Inactive students cannot submit progression selections.")
        source_class = await ClassRoomRepository.get_by_id(
            db, tenant_id, item.from_class_id, lock=True
        )
        if source_class is None:
            raise ConflictException("Progression source classroom is missing.")
        level = await AcademicLevelRepository.get_by_id(
            db, tenant_id, source_class.academic_level_id, lock=True
        )
        if (
            level is None
            or level.progression_mode != AcademicLevelProgressionMode.STUDENT_SELECTION
        ):
            raise ConflictException("Student-selection configuration is no longer valid.")
        options = await AcademicLevelRepository.list_progression_options(
            db, tenant_id, level.id, lock=True
        )
        option = next(
            (
                candidate
                for candidate in options
                if destination_id in {candidate.target_level_id, candidate.target_classroom_id}
            ),
            None,
        )
        if option is None:
            raise ConflictException("Destination is not configured for this student.")
        run = await StudentProgressionRepository.get_run_by_id(
            db, tenant_id, item.progression_run_id, lock=True
        )
        if run is None:
            raise ConflictException("Progression run is missing.")
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db, tenant_id, run.next_academic_session_id, lock=True
        )
        if next_session is None:
            raise ConflictException("Target academic session is missing.")
        if changed_by_admin_id is None and next_session.status != AcademicSessionStatus.OPEN:
            raise ConflictException(
                "Progression selection becomes available when the next academic session opens."
            )

        item.selected_level_id = option.target_level_id
        item.selected_classroom_id = option.target_classroom_id
        item.status = StudentProgressionItemStatus.SELECTION_SUBMITTED
        item.reason = "Student destination selected."
        if option.target_classroom_id:
            target_class = await ClassRoomRepository.get_by_id(
                db, tenant_id, option.target_classroom_id, lock=True
            )
            if target_class is None or not target_class.is_active or target_class.archived_at:
                raise ConflictException("Selected classroom is inactive.")
            await AcademicProgressionService._create_next_enrollment(
                db,
                tenant_id=tenant_id,
                student=student,
                item=item,
                target_class=target_class,
                next_session=next_session,
                changed_by_admin_id=changed_by_admin_id,
            )
        else:
            target_level = await AcademicLevelRepository.get_by_id(
                db, tenant_id, option.target_level_id, lock=True
            )
            if target_level is None or not target_level.is_active or target_level.archived_at:
                raise ConflictException("Selected academic level is inactive.")
            target_class = await ClassRoomRepository.get_by_level_and_arm(
                db, tenant_id, target_level.id, source_class.arm
            )
            if (
                target_class is not None
                and target_class.is_active
                and target_class.archived_at is None
            ):
                await AcademicProgressionService._create_next_enrollment(
                    db,
                    tenant_id=tenant_id,
                    student=student,
                    item=item,
                    target_class=target_class,
                    next_session=next_session,
                    changed_by_admin_id=changed_by_admin_id,
                )
            else:
                item.status = StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT
                item.reason = (
                    f"{target_level.name} selected, but no active {source_class.arm} arm exists; "
                    "administrator classroom placement is required."
                )
                await StudentProgressionRepository.save_item(db, item)
        await db.commit()
        await db.refresh(item)
        return await AcademicProgressionService._selection_response(
            db, tenant_id=tenant_id, item=item
        )

    @staticmethod
    async def submit_student_selection(
        db: AsyncSession, *, student: Student, destination_id: uuid.UUID
    ) -> StudentProgressionSelectionResponse:
        return await AcademicProgressionService._select_destination(
            db,
            tenant_id=student.tenant_id,
            student_id=student.id,
            destination_id=destination_id,
            changed_by_admin_id=None,
        )

    @staticmethod
    async def admin_override_selection(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: uuid.UUID,
        destination_id: uuid.UUID,
    ) -> StudentProgressionSelectionResponse:
        return await AcademicProgressionService._select_destination(
            db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
            destination_id=destination_id,
            changed_by_admin_id=actor.id,
        )

    @staticmethod
    async def place_student(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: uuid.UUID,
        classroom_id: uuid.UUID,
    ) -> StudentProgressionSelectionResponse:
        item = await StudentProgressionRepository.get_latest_item_for_student(
            db, actor.tenant_id, student_id, lock=True
        )
        if item is None or item.status not in {
            StudentProgressionItemStatus.AWAITING_CLASS_PLACEMENT,
            StudentProgressionItemStatus.BLOCKED,
        }:
            raise ConflictException("Student is not awaiting classroom placement.")
        if item.selected_level_id is None:
            raise ConflictException("Student has no selected academic level.")
        target_class = await ClassRoomRepository.get_by_id(
            db, actor.tenant_id, classroom_id, lock=True
        )
        if (
            target_class is None
            or target_class.academic_level_id != item.selected_level_id
            or not target_class.is_active
            or target_class.archived_at is not None
        ):
            raise ConflictException("Classroom must be active and belong to the selected level.")
        student = await StudentRepository.get_by_id(
            db, actor.tenant_id, student_id, lock=True, include_archived=True
        )
        run = await StudentProgressionRepository.get_run_by_id(
            db, actor.tenant_id, item.progression_run_id, lock=True
        )
        if student is None or run is None:
            raise ConflictException("Progression records are incomplete.")
        next_session = await AcademicSessionLifecycleRepository.get_by_id(
            db, actor.tenant_id, run.next_academic_session_id, lock=True
        )
        if next_session is None:
            raise ConflictException("Target academic session is missing.")
        await AcademicProgressionService._create_next_enrollment(
            db,
            tenant_id=actor.tenant_id,
            student=student,
            item=item,
            target_class=target_class,
            next_session=next_session,
            changed_by_admin_id=actor.id,
        )
        await db.commit()
        await db.refresh(item)
        return await AcademicProgressionService._selection_response(
            db, tenant_id=actor.tenant_id, item=item
        )
