"""Canonical academic setup, assignment, score, and subject-card services."""

from __future__ import annotations

import uuid
from datetime import date
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
    StudentSubjectResultResponse,
    StudentSubjectResultStatusUpdate,
    StudentSubjectResultUpsert,
    TeacherAssignmentCreate,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
)
from app.modules.students.models import Student, StudentParentLinkStatus
from app.modules.students.repository import StudentParentLinkRepository, StudentRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import TeacherMembership, TeacherMembershipStatus
from app.modules.teachers.repository import (
    TeacherMembershipRepository,
    TeacherMembershipSubjectRepository,
)
from app.modules.tenant_admins.models import TenantAdmin


class StudentAcademicService:
    """Business rules for tenant academic setup and score ownership."""

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
        return ClassSubjectResponse(
            id=class_subject.id,
            tenant_id=class_subject.tenant_id,
            class_id=class_subject.class_id,
            subject_id=class_subject.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            is_core=class_subject.is_core,
            is_active=class_subject.is_active,
            created_at=class_subject.created_at,
            updated_at=class_subject.updated_at,
        )

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
        capability = (
            await TeacherMembershipSubjectRepository.get_by_membership_and_subject(
                db,
                tenant_id,
                membership.id,
                subject_id,
            )
        )
        if capability is None or not capability.is_active:
            raise ForbiddenException(
                "The teacher is not approved to teach this subject."
            )
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
        if classroom is None or not classroom.is_active:
            raise NotFoundException("Class not found or inactive.")
        subject = await SubjectRepository.get_subject_by_id(
            db,
            tenant_id,
            payload.subject_id,
        )
        if subject is None or not subject.is_active:
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
            if existing.is_active:
                raise ConflictException(
                    "This subject is already offered by the class."
                )
            existing.is_active = True
            existing.is_core = payload.is_core
            existing = await StudentAcademicRepository.save_class_subject(
                db,
                existing,
            )
            await db.commit()
            return await StudentAcademicService._build_class_subject_response(
                db,
                existing,
            )
        row = await StudentAcademicRepository.create_class_subject(
            db,
            ClassSubject(
                tenant_id=tenant_id,
                class_id=class_id,
                subject_id=payload.subject_id,
                is_core=payload.is_core,
                is_active=True,
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
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ClassSubjectResponse], int]:
        rows, total = await StudentAcademicRepository.list_class_subjects(
            db,
            tenant_id,
            class_id=class_id,
            active_only=active_only,
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
        if await StudentAcademicRepository.count_results_for_class_subject(
            db,
            tenant_id,
            row.id,
        ):
            raise ConflictException(
                "Class subject has score history and cannot be removed; deactivate its assignment instead."
            )
        row.is_active = False
        row = await StudentAcademicRepository.save_class_subject(db, row)
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db, row)

    @staticmethod
    async def create_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TeacherAssignmentCreate,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            payload.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise NotFoundException("Class subject not found or inactive.")
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
        assignment = await StudentAcademicRepository.create_teacher_assignment(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=date.today(),
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
    async def deactivate_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        if not assignment.is_active:
            return await StudentAcademicService._build_teacher_assignment_response(
                db,
                assignment,
            )
        assignment.is_active = False
        assignment.effective_to = date.today()
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
    async def activate_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db,
            tenant_id,
            assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            assignment.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise BadRequestException("Activate the class subject first.")
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=assignment.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        active = (
            await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db,
                tenant_id,
                class_subject.id,
                exclude_id=assignment.id,
            )
        )
        if active is not None:
            raise ConflictException(
                "Another active teacher assignment already exists."
            )
        assignment.is_active = True
        assignment.effective_to = None
        assignment.effective_from = date.today()
        assignment = await StudentAcademicRepository.save_teacher_assignment(
            db,
            assignment,
        )
        await StudentAcademicService._ensure_compatibility_assignment(
            db,
            tenant_id=tenant_id,
            class_subject=class_subject,
            teacher_membership_id=assignment.teacher_membership_id,
            is_active=True,
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
        )
        if current is None:
            raise NotFoundException("Teacher assignment not found.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            current.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise NotFoundException("Class subject not found or inactive.")
        await StudentAcademicService._validate_teacher_capability(
            db,
            tenant_id=tenant_id,
            teacher_membership_id=payload.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        if current.teacher_membership_id == payload.teacher_membership_id and current.is_active:
            raise ConflictException("This teacher is already assigned.")

        active = (
            await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db,
                tenant_id,
                class_subject.id,
            )
        )
        if active is not None:
            active.is_active = False
            active.effective_to = date.today()
            await StudentAcademicRepository.save_teacher_assignment(db, active)

        replacement = await StudentAcademicRepository.create_teacher_assignment(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=date.today(),
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
        class_subject = (
            await StudentAcademicRepository.get_class_subject_by_class_and_subject(
                db,
                tenant_id,
                payload.class_id,
                payload.subject_id,
            )
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
                is_active=True,
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
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db,
            tenant_id,
            payload.academic_session_id,
        )
        if session is None or session.status == AcademicSessionStatus.CLOSED:
            raise NotFoundException("Usable academic session not found.")
        if await StudentAcademicRepository.get_term_by_session_and_name(
            db,
            tenant_id,
            session.id,
            payload.name,
        ):
            raise ConflictException("Academic term already exists.")
        if payload.is_current:
            current = await StudentAcademicRepository.get_current_term(db, tenant_id)
            if current is not None:
                current.is_current = False
                await StudentAcademicRepository.save_academic_term(db, current)
        row = await StudentAcademicRepository.create_academic_term(
            db,
            AcademicTerm(
                tenant_id=tenant_id,
                academic_session_id=session.id,
                name=payload.name,
                start_date=payload.start_date,
                end_date=payload.end_date,
                is_current=payload.is_current,
                is_active=payload.is_active,
            ),
        )
        await db.commit()
        return row

    @staticmethod
    async def update_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        payload: AcademicTermUpdate,
    ) -> AcademicTerm:
        row = await StudentAcademicRepository.get_term_by_id(db, tenant_id, term_id)
        if row is None:
            raise NotFoundException("Academic term not found.")
        if payload.is_current is True:
            current = await StudentAcademicRepository.get_current_term(db, tenant_id)
            if current is not None and current.id != row.id:
                current.is_current = False
                await StudentAcademicRepository.save_academic_term(db, current)
        for field, value in payload.model_dump(
            exclude_unset=True,
            exclude_none=True,
        ).items():
            setattr(row, field, value)
        row = await StudentAcademicRepository.save_academic_term(db, row)
        await db.commit()
        return row

    @staticmethod
    async def list_academic_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        academic_session_id: uuid.UUID | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        if academic_session_id is None:
            return await StudentAcademicRepository.list_terms(
                db,
                tenant_id,
                skip,
                limit,
            )
        return await StudentAcademicRepository.list_terms_by_session(
            db,
            tenant_id,
            academic_session_id,
            skip,
            limit,
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
        if assignment is None or class_subject is None or not class_subject.is_active:
            raise NotFoundException("Active class-subject assignment not found.")
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
            created_at=result.created_at,
            updated_at=result.updated_at,
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
            and existing.status == AcademicResultStatus.SUBMITTED
            and isinstance(actor, TeacherMembership)
        ):
            raise ForbiddenException("Submitted scores are locked for teachers.")

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
        else:
            result = existing
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
        if payload.status == AcademicResultStatus.SUBMITTED and any(
            score is None
            for score in (
                result.test_score,
                result.assessment_score,
                result.exam_score,
            )
        ):
            raise BadRequestException("All scores are required before submission.")
        result.status = payload.status
        result.recorded_by_actor_type = "tenant_admin"
        result.recorded_by_actor_id = actor.id
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
        published_only = False
        if isinstance(actor, TeacherMembership):
            teacher_id = actor.id
        elif isinstance(actor, Student):
            student_id = actor.id
            published_only = True
        elif isinstance(actor, ParentMembership):
            if student_id is None:
                raise BadRequestException("student_id is required for parent result access.")
            await StudentAcademicService._ensure_parent_can_view_student(
                db,
                actor,
                student_id,
            )
            published_only = True
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
            published_only=published_only,
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
                and result.status == AcademicResultStatus.SUBMITTED
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
                    status="submitted" if submitted else "pending",
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
