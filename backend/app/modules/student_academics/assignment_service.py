"""Canonical teacher-membership assignment workflows."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.models import ClassSubject, TeacherAssignment
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.student_academics.schemas import (
    TeacherAssignmentCreate,
    TeacherAssignmentReassign,
    TeacherAssignmentResponse,
)
from app.modules.student_academics.teacher_assignment_repository import TeacherAssignmentRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.repository import (
    TeacherMembershipRepository,
    TeacherMembershipSubjectRepository,
)


class TeacherAssignmentService:
    """Assign active teacher memberships to tenant class-subjects."""

    @staticmethod
    async def _require_assignable_membership(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        subject_id: UUID,
    ):
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=tenant_id,
            load_account=True,
            load_subjects=True,
        )
        if membership is None:
            raise NotFoundException("Teacher membership not found.")
        if membership.status != TeacherMembershipStatus.ACTIVE:
            raise BadRequestException("Only active teacher memberships can be assigned.")
        capability = await TeacherMembershipSubjectRepository.get_by_membership_and_subject(
            db,
            tenant_id,
            membership_id,
            subject_id,
        )
        if capability is None or not capability.is_active:
            raise BadRequestException(
                "This teacher membership is not approved to teach the selected subject."
            )
        return membership

    @staticmethod
    async def _response(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        if class_subject is None:
            raise NotFoundException("Class subject not found.")
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
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            assignment.teacher_membership_id,
            tenant_id=assignment.tenant_id,
            load_account=True,
        )
        account = membership.teacher_account if membership else None
        return TeacherAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
            teacher_membership_id=assignment.teacher_membership_id,
            class_id=class_subject.class_id,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=class_subject.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_name=(
                " ".join(
                    part
                    for part in [
                        account.first_name if account else None,
                        account.last_name if account else None,
                    ]
                    if part
                ).strip()
                or None
            ),
            teacher_staff_id=membership.staff_id if membership else None,
            is_active=assignment.is_active,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        payload: TeacherAssignmentCreate,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=payload.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise NotFoundException("Active class subject not found.")
        await TeacherAssignmentService._require_assignable_membership(
            db,
            tenant_id=tenant_id,
            membership_id=payload.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        existing = await TeacherAssignmentRepository.get_active_for_class_subject(
            db,
            tenant_id,
            payload.class_subject_id,
            lock=True,
        )
        if existing is not None:
            raise ConflictException("An active teacher assignment already exists.")
        assignment = await TeacherAssignmentRepository.add(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=payload.class_subject_id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=date.today(),
            ),
        )
        await db.commit()
        return await TeacherAssignmentService._response(db, assignment)

    @staticmethod
    async def list(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        teacher_membership_id: UUID | None = None,
        class_id: UUID | None = None,
        active_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[TeacherAssignmentResponse], int]:
        filters = [TeacherAssignment.tenant_id == tenant_id]
        query = select(TeacherAssignment)
        count_query = select(func.count()).select_from(TeacherAssignment)
        if teacher_membership_id is not None:
            filters.append(
                TeacherAssignment.teacher_membership_id == teacher_membership_id
            )
        if active_only:
            filters.append(TeacherAssignment.is_active.is_(True))
        if class_id is not None:
            query = query.join(
                ClassSubject,
                ClassSubject.id == TeacherAssignment.class_subject_id,
            )
            count_query = count_query.join(
                ClassSubject,
                ClassSubject.id == TeacherAssignment.class_subject_id,
            )
            filters.extend(
                [
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                ]
            )
        total = int((await db.execute(count_query.where(*filters))).scalar_one() or 0)
        rows = list(
            (
                await db.execute(
                    query.where(*filters)
                    .order_by(
                        TeacherAssignment.is_active.desc(),
                        TeacherAssignment.created_at.desc(),
                    )
                    .offset(offset)
                    .limit(limit)
                )
            ).scalars().all()
        )
        return [
            await TeacherAssignmentService._response(db, item) for item in rows
        ], total

    @staticmethod
    async def deactivate(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        assignment.is_active = False
        assignment.effective_to = date.today()
        await TeacherAssignmentRepository.save(db, assignment)
        await db.commit()
        return await TeacherAssignmentService._response(db, assignment)

    @staticmethod
    async def activate(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise BadRequestException("Activate the class subject first.")
        await TeacherAssignmentService._require_assignable_membership(
            db,
            tenant_id=tenant_id,
            membership_id=assignment.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        existing = await TeacherAssignmentRepository.get_active_for_class_subject(
            db,
            tenant_id,
            assignment.class_subject_id,
            lock=True,
        )
        if existing is not None and existing.id != assignment.id:
            raise ConflictException("Another active teacher assignment already exists.")
        assignment.is_active = True
        assignment.effective_to = None
        assignment.effective_from = date.today()
        await TeacherAssignmentRepository.save(db, assignment)
        await db.commit()
        return await TeacherAssignmentService._response(db, assignment)

    @staticmethod
    async def reassign(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        assignment_id: UUID,
        payload: TeacherAssignmentReassign,
    ) -> TeacherAssignmentResponse:
        current = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )
        if current is None:
            raise NotFoundException("Teacher assignment not found.")
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=current.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise BadRequestException("The class subject is inactive.")
        await TeacherAssignmentService._require_assignable_membership(
            db,
            tenant_id=tenant_id,
            membership_id=payload.teacher_membership_id,
            subject_id=class_subject.subject_id,
        )
        if current.teacher_membership_id == payload.teacher_membership_id and current.is_active:
            return await TeacherAssignmentService._response(db, current)
        current.is_active = False
        current.effective_to = date.today()
        await TeacherAssignmentRepository.save(db, current)
        replacement = await TeacherAssignmentRepository.add(
            db,
            TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=current.class_subject_id,
                teacher_membership_id=payload.teacher_membership_id,
                is_active=True,
                effective_from=date.today(),
            ),
        )
        await db.commit()
        return await TeacherAssignmentService._response(db, replacement)
