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

from app.modules.auth_identity.models import ActorType
from app.modules.students.models import Student
from app.modules.students.repository import StudentParentLinkRepository, StudentRepository
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSession,
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

from app.modules.classes.repository import ClassRoomRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.repository import TeacherRepository
from app.modules.parents.models import Parent
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


class StudentAcademicService:
    DEPRECATED_SUBJECT_ASSIGNMENTS_HEADER = "X-Deprecated-Endpoint: subject-assignments"

    @staticmethod
    async def _build_class_subject_response(
        db: AsyncSession,
        class_subject: ClassSubject,
    ) -> ClassSubjectResponse:
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=class_subject.tenant_id,
            subject_id=class_subject.subject_id,
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
    async def _build_teacher_assignment_response(
        db: AsyncSession,
        assignment: TeacherAssignment,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        classroom = None
        subject = None
        if class_subject is not None:
            classroom = await ClassRoomRepository.get_classroom_by_id(
                db=db,
                tenant_id=assignment.tenant_id,
                class_id=class_subject.class_id,
            )
            subject = await SubjectRepository.get_subject_by_id(
                db=db,
                tenant_id=assignment.tenant_id,
                subject_id=class_subject.subject_id,
            )
        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=assignment.tenant_id,
            teacher_id=assignment.teacher_id,
        )
        return TeacherAssignmentResponse(
            id=assignment.id,
            tenant_id=assignment.tenant_id,
            class_subject_id=assignment.class_subject_id,
            teacher_id=assignment.teacher_id,
            class_id=class_subject.class_id if class_subject else None,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=class_subject.subject_id if class_subject else None,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_name=(
                " ".join(part for part in [teacher.first_name, teacher.last_name] if part).strip()
                if teacher
                else None
            ),
            teacher_staff_id=teacher.staff_id if teacher else None,
            is_active=assignment.is_active,
            effective_from=assignment.effective_from,
            effective_to=assignment.effective_to,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    @staticmethod
    async def _sync_legacy_class_subject_teacher(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
        teacher_id: uuid.UUID,
        *,
        is_core: bool = True,
        is_active: bool = True,
    ) -> ClassSubjectTeacher:
        existing = await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=subject_id,
        )
        if existing is None:
            legacy = ClassSubjectTeacher(
                tenant_id=tenant_id,
                class_id=class_id,
                subject_id=subject_id,
                teacher_id=teacher_id,
                is_core=is_core,
                is_active=is_active,
            )
            return await StudentAcademicRepository.create_class_subject_teacher(db=db, assignment=legacy)

        existing.teacher_id = teacher_id
        existing.is_core = is_core
        existing.is_active = is_active
        return await StudentAcademicRepository.save_class_subject_teacher(db=db, assignment=existing)

    @staticmethod
    async def _deactivate_active_teacher_assignments_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        *,
        exclude_assignment_id: uuid.UUID | None = None,
    ) -> None:
        active_assignments, _ = await StudentAcademicRepository.list_teacher_assignment_rows(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject_id,
            active_only=True,
            skip=0,
            limit=500,
        )
        for active_assignment in active_assignments:
            if exclude_assignment_id is not None and active_assignment.id == exclude_assignment_id:
                continue
            active_assignment.is_active = False
            active_assignment.effective_to = date.today()
            await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=active_assignment)

    @staticmethod
    async def create_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        payload: ClassSubjectCreate,
    ) -> ClassSubjectResponse:
        classroom = await ClassRoomRepository.get_classroom_by_id(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
        )
        if classroom is None:
            raise NotFoundException("Class not found.")

        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            subject_id=payload.subject_id,
        )
        if subject is None:
            raise NotFoundException("Subject not found.")

        existing = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=payload.subject_id,
        )
        if existing is not None:
            raise ConflictException("This subject is already offered by this class.")

        class_subject = ClassSubject(
            tenant_id=tenant_id,
            class_id=class_id,
            subject_id=payload.subject_id,
            is_core=payload.is_core,
            is_active=True,
        )
        created = await StudentAcademicRepository.create_class_subject(db=db, class_subject=class_subject)
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db=db, class_subject=created)

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
        items, total = await StudentAcademicRepository.list_class_subjects(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )
        return [
            await StudentAcademicService._build_class_subject_response(db=db, class_subject=item)
            for item in items
        ], total

    @staticmethod
    async def deactivate_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubjectResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject_id,
        )
        if class_subject is None:
            raise NotFoundException("Class subject not found.")

        score_count = await StudentAcademicRepository.count_results_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject_id,
        )
        if score_count > 0:
            raise BadRequestException("Cannot deactivate a class subject that has score records.")

        class_subject.is_active = False
        saved = await StudentAcademicRepository.save_class_subject(db=db, class_subject=class_subject)
        await db.commit()
        return await StudentAcademicService._build_class_subject_response(db=db, class_subject=saved)

    @staticmethod
    async def create_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: TeacherAssignmentCreate,
    ) -> TeacherAssignmentResponse:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=payload.class_subject_id,
        )
        if class_subject is None or not class_subject.is_active:
            raise NotFoundException("Class subject not found.")

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            teacher_id=payload.teacher_id,
        )
        if teacher is None:
            raise NotFoundException("Teacher not found.")

        active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=payload.class_subject_id,
        )
        if active is not None:
            raise ConflictException("An active teacher assignment already exists for this class subject.")

        assignment = TeacherAssignment(
            tenant_id=tenant_id,
            class_subject_id=payload.class_subject_id,
            teacher_id=payload.teacher_id,
            is_active=True,
            effective_from=date.today(),
        )
        created = await StudentAcademicRepository.create_teacher_assignment(db=db, assignment=assignment)

        await StudentAcademicService._sync_legacy_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            class_id=class_subject.class_id,
            subject_id=class_subject.subject_id,
            teacher_id=payload.teacher_id,
            is_core=class_subject.is_core,
            is_active=True,
        )

        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=created)

    @staticmethod
    async def deactivate_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
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
        saved = await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=assignment)

        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        if class_subject is not None:
            await StudentAcademicService._sync_legacy_class_subject_teacher(
                db=db,
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_id=assignment.teacher_id,
                is_core=class_subject.is_core,
                is_active=False,
            )

        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=saved)

    @staticmethod
    async def activate_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
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
        if class_subject is None:
            raise NotFoundException("Class subject not found.")
        if not class_subject.is_active:
            raise BadRequestException("Activate this class-subject before reactivating its teacher assignment.")

        active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
            exclude_id=assignment.id,
        )
        if active is not None:
            raise ConflictException("An active teacher assignment already exists for this class subject.")

        assignment.is_active = True
        assignment.effective_to = None
        # A reactivated assignment starts a new active interval.
        assignment.effective_from = date.today()
        saved = await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=assignment)

        await StudentAcademicService._sync_legacy_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            class_id=class_subject.class_id,
            subject_id=class_subject.subject_id,
            teacher_id=assignment.teacher_id,
            is_core=class_subject.is_core,
            is_active=True,
        )

        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=saved)

    @staticmethod
    async def reassign_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: TeacherAssignmentReassign,
    ) -> TeacherAssignmentResponse:
        assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )
        if assignment is None:
            raise NotFoundException("Teacher assignment not found.")

        score_count = await StudentAcademicRepository.count_scores_for_teacher_assignment(
            db=db,
            tenant_id=tenant_id,
            teacher_assignment_id=assignment_id,
        )
        if score_count > 0 and payload.teacher_id != assignment.teacher_id:
            assignment.is_active = False
            assignment.effective_to = date.today()
            await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=assignment)
            await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=assignment.class_subject_id,
                exclude_assignment_id=assignment.id,
            )
            class_subject = await StudentAcademicRepository.get_class_subject_by_id(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=assignment.class_subject_id,
            )
            if class_subject is not None:
                await StudentAcademicService._sync_legacy_class_subject_teacher(
                    db=db,
                    tenant_id=tenant_id,
                    class_id=class_subject.class_id,
                    subject_id=class_subject.subject_id,
                    teacher_id=assignment.teacher_id,
                    is_core=class_subject.is_core,
                    is_active=False,
                )
        elif payload.teacher_id == assignment.teacher_id:
            return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=assignment)
        else:
            assignment.teacher_id = payload.teacher_id
            saved = await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=assignment)
            await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=assignment.class_subject_id,
                exclude_assignment_id=assignment.id,
            )
            class_subject = await StudentAcademicRepository.get_class_subject_by_id(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=assignment.class_subject_id,
            )
            if class_subject is not None:
                await StudentAcademicService._sync_legacy_class_subject_teacher(
                    db=db,
                    tenant_id=tenant_id,
                    class_id=class_subject.class_id,
                    subject_id=class_subject.subject_id,
                    teacher_id=payload.teacher_id,
                    is_core=class_subject.is_core,
                    is_active=True,
                )
            await db.commit()
            return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=saved)

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            teacher_id=payload.teacher_id,
        )
        if teacher is None:
            raise NotFoundException("Teacher not found.")

        active = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        if active is not None:
            raise ConflictException("An active teacher assignment already exists for this class subject.")

        new_assignment = TeacherAssignment(
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
            teacher_id=payload.teacher_id,
            is_active=True,
            effective_from=date.today(),
        )
        created = await StudentAcademicRepository.create_teacher_assignment(
            db=db,
            assignment=new_assignment,
        )
        await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
            exclude_assignment_id=created.id,
        )
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=assignment.class_subject_id,
        )
        if class_subject is not None:
            await StudentAcademicService._sync_legacy_class_subject_teacher(
                db=db,
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_id=payload.teacher_id,
                is_core=class_subject.is_core,
                is_active=True,
            )
        await db.commit()
        return await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=created)

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
        items, total = await StudentAcademicRepository.list_teacher_assignment_rows(
            db=db,
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            class_id=class_id,
            active_only=active_only,
            skip=skip,
            limit=limit,
        )
        return [
            await StudentAcademicService._build_teacher_assignment_response(db=db, assignment=item)
            for item in items
        ], total

    @staticmethod
    async def _resolve_assignment_context(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: StudentSubjectResultUpsert,
    ) -> tuple[TeacherAssignment, ClassSubjectTeacher | None]:
        if payload.teacher_assignment_id is not None:
            teacher_assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
                db=db,
                tenant_id=tenant_id,
                assignment_id=payload.teacher_assignment_id,
            )
            if teacher_assignment is None or not teacher_assignment.is_active:
                raise NotFoundException("Teacher assignment not found.")
            class_subject = await StudentAcademicRepository.get_class_subject_by_id(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=teacher_assignment.class_subject_id,
            )
            if class_subject is None or not class_subject.is_active:
                raise NotFoundException("Class subject not found.")
            legacy = await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
            )
            return teacher_assignment, legacy

        legacy = await StudentAcademicRepository.get_class_subject_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=payload.class_subject_teacher_id,
        )
        if legacy is None or not legacy.is_active:
            raise NotFoundException("Class-subject teacher assignment not found.")

        class_subject = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=legacy.class_id,
            subject_id=legacy.subject_id,
        )
        teacher_assignment = None
        if class_subject is not None:
            teacher_assignment = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
            )
        if teacher_assignment is None:
            if class_subject is None:
                class_subject = ClassSubject(
                    tenant_id=tenant_id,
                    class_id=legacy.class_id,
                    subject_id=legacy.subject_id,
                    is_core=legacy.is_core,
                    is_active=legacy.is_active,
                )
                class_subject = await StudentAcademicRepository.create_class_subject(
                    db=db,
                    class_subject=class_subject,
                )
            teacher_assignment = TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_id=legacy.teacher_id,
                is_active=legacy.is_active,
                effective_from=date.today(),
            )
            teacher_assignment = await StudentAcademicRepository.create_teacher_assignment(
                db=db,
                assignment=teacher_assignment,
            )
        return teacher_assignment, legacy

    @staticmethod
    def _ensure_session_not_future_when_current(session_name: str) -> None:
        start_year = int(session_name.split("/")[0])
        current_year = date.today().year

        if start_year > current_year:
            raise BadRequestException(
                "You cannot set a future academic session as current."
            )

    @staticmethod
    async def create_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicSessionCreate,
    ) -> AcademicSession:
        existing_session = await StudentAcademicRepository.get_academic_session_by_name(
            db=db,
            tenant_id=tenant_id,
            name=payload.name,
        )

        if existing_session is not None:
            raise ConflictException(
                "Academic session already exists for this tenant."
            )

        if payload.is_current:
            StudentAcademicService._ensure_session_not_future_when_current(
                payload.name
            )

            current_session = (
                await StudentAcademicRepository.get_current_academic_session(
                    db=db,
                    tenant_id=tenant_id,
                )
            )

            if current_session is not None:
                current_session.is_current = False
                await StudentAcademicRepository.save_academic_session(
                    db=db,
                    academic_session=current_session,
                )

        academic_session = AcademicSession(
            tenant_id=tenant_id,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_current=payload.is_current,
            is_active=payload.is_active,
        )

        created_session = await StudentAcademicRepository.create_academic_session(
            db=db,
            academic_session=academic_session,
        )

        await db.commit()
        return created_session

    @staticmethod
    async def update_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        payload: AcademicSessionUpdate,
    ) -> AcademicSession:
        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=academic_session_id,
        )

        if academic_session is None:
            raise NotFoundException("Academic session not found.")

        update_data = payload.model_dump(exclude_unset=True)

        new_name = update_data.get("name")

        if new_name is not None and new_name != academic_session.name:
            existing_session = (
                await StudentAcademicRepository.get_academic_session_by_name(
                    db=db,
                    tenant_id=tenant_id,
                    name=new_name,
                )
            )

            if existing_session is not None:
                raise ConflictException(
                    "Academic session already exists for this tenant."
                )

        wants_current = update_data.get("is_current") is True

        if wants_current:
            session_name_to_validate = update_data.get(
                "name",
                academic_session.name,
            )

            StudentAcademicService._ensure_session_not_future_when_current(
                session_name_to_validate
            )

            current_session = (
                await StudentAcademicRepository.get_current_academic_session(
                    db=db,
                    tenant_id=tenant_id,
                )
            )

            if current_session is not None and current_session.id != academic_session.id:
                current_session.is_current = False
                await StudentAcademicRepository.save_academic_session(
                    db=db,
                    academic_session=current_session,
                )

        for field, value in update_data.items():
            setattr(academic_session, field, value)

        updated_session = await StudentAcademicRepository.save_academic_session(
            db=db,
            academic_session=academic_session,
        )

        await db.commit()
        return updated_session

    @staticmethod
    async def list_academic_sessions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicSession], int]:
        return await StudentAcademicRepository.list_academic_sessions(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def create_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: AcademicTermCreate,
    ) -> AcademicTerm:
        academic_session = await StudentAcademicRepository.get_academic_session_by_id(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=payload.academic_session_id,
        )

        if academic_session is None:
            raise NotFoundException("Academic session not found.")

        existing_term = await StudentAcademicRepository.get_term_by_session_and_name(
            db=db,
            tenant_id=tenant_id,
            academic_session_id=payload.academic_session_id,
            name=payload.name,
        )

        if existing_term is not None:
            raise ConflictException(
                "Academic term already exists for this academic session."
            )

        if payload.is_current:
            current_term = await StudentAcademicRepository.get_current_term(
                db=db,
                tenant_id=tenant_id,
            )

            if current_term is not None:
                current_term.is_current = False
                await StudentAcademicRepository.save_academic_term(
                    db=db,
                    academic_term=current_term,
                )

        academic_term = AcademicTerm(
            tenant_id=tenant_id,
            academic_session_id=payload.academic_session_id,
            name=payload.name,
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_current=payload.is_current,
            is_active=payload.is_active,
        )

        created_term = await StudentAcademicRepository.create_academic_term(
            db=db,
            academic_term=academic_term,
        )

        await db.commit()
        return created_term

    @staticmethod
    async def update_academic_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        payload: AcademicTermUpdate,
    ) -> AcademicTerm:
        academic_term = await StudentAcademicRepository.get_term_by_id(
            db=db,
            tenant_id=tenant_id,
            term_id=term_id,
        )

        if academic_term is None:
            raise NotFoundException("Academic term not found.")

        update_data = payload.model_dump(exclude_unset=True)
        new_name = update_data.get("name")

        if new_name is not None and new_name != academic_term.name:
            existing_term = await StudentAcademicRepository.get_term_by_session_and_name(
                db=db,
                tenant_id=tenant_id,
                academic_session_id=academic_term.academic_session_id,
                name=new_name,
            )

            if existing_term is not None:
                raise ConflictException(
                    "Academic term already exists for this academic session."
                )

        wants_current = update_data.get("is_current") is True

        if wants_current:
            current_term = await StudentAcademicRepository.get_current_term(
                db=db,
                tenant_id=tenant_id,
            )

            if current_term is not None and current_term.id != academic_term.id:
                current_term.is_current = False
                await StudentAcademicRepository.save_academic_term(
                    db=db,
                    academic_term=current_term,
                )

        for field, value in update_data.items():
            setattr(academic_term, field, value)

        updated_term = await StudentAcademicRepository.save_academic_term(
            db=db,
            academic_term=academic_term,
        )

        await db.commit()
        return updated_term

    @staticmethod
    async def list_academic_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        academic_session_id: uuid.UUID | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        if academic_session_id is not None:
            return await StudentAcademicRepository.list_terms_by_session(
                db=db,
                tenant_id=tenant_id,
                academic_session_id=academic_session_id,
                skip=skip,
                limit=limit,
            )

        return await StudentAcademicRepository.list_terms(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def create_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: GradingScaleCreate,
    ) -> GradingScale:
        existing_grade = await StudentAcademicRepository.get_grading_scale_by_grade(
            db=db,
            tenant_id=tenant_id,
            grade=payload.grade,
        )

        if existing_grade is not None:
            raise ConflictException("A grading scale with this grade already exists.")

        active_scales, _ = await StudentAcademicRepository.list_grading_scales(
            db=db,
            tenant_id=tenant_id,
            active_only=True,
            limit=100,
        )

        for scale in active_scales:
            overlaps = (
                payload.min_score <= scale.max_score
                and payload.max_score >= scale.min_score
            )

            if overlaps:
                raise ConflictException(
                    "Grading scale range overlaps with an existing active range."
                )

        grading_scale = GradingScale(
            tenant_id=tenant_id,
            min_score=payload.min_score,
            max_score=payload.max_score,
            grade=payload.grade,
            remark=payload.remark,
            is_active=payload.is_active,
        )

        created_scale = await StudentAcademicRepository.create_grading_scale(
            db=db,
            grading_scale=grading_scale,
        )

        await db.commit()
        return created_scale

    @staticmethod
    async def update_grading_scale(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        grading_scale_id: uuid.UUID,
        payload: GradingScaleUpdate,
    ) -> GradingScale:
        grading_scale = await StudentAcademicRepository.get_grading_scale_by_id(
            db=db,
            tenant_id=tenant_id,
            grading_scale_id=grading_scale_id,
        )

        if grading_scale is None:
            raise NotFoundException("Grading scale not found.")

        update_data = payload.model_dump(exclude_unset=True)

        new_grade = update_data.get("grade")

        if new_grade is not None and new_grade != grading_scale.grade:
            existing_grade = await StudentAcademicRepository.get_grading_scale_by_grade(
                db=db,
                tenant_id=tenant_id,
                grade=new_grade,
            )

            if existing_grade is not None:
                raise ConflictException(
                    "A grading scale with this grade already exists."
                )

        final_min_score = update_data.get("min_score", grading_scale.min_score)
        final_max_score = update_data.get("max_score", grading_scale.max_score)

        if final_min_score > final_max_score:
            raise BadRequestException(
                "Minimum score cannot be greater than maximum score."
            )

        active_scales, _ = await StudentAcademicRepository.list_grading_scales(
            db=db,
            tenant_id=tenant_id,
            active_only=True,
            limit=100,
        )

        for scale in active_scales:
            if scale.id == grading_scale.id:
                continue

            overlaps = (
                final_min_score <= scale.max_score
                and final_max_score >= scale.min_score
            )

            if overlaps:
                raise ConflictException(
                    "Grading scale range overlaps with an existing active range."
                )

        for field, value in update_data.items():
            setattr(grading_scale, field, value)

        updated_scale = await StudentAcademicRepository.save_grading_scale(
            db=db,
            grading_scale=grading_scale,
        )

        await db.commit()
        return updated_scale

    @staticmethod
    async def list_grading_scales(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> tuple[list[GradingScale], int]:
        return await StudentAcademicRepository.list_grading_scales(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            active_only=active_only,
        )

    @staticmethod
    async def resolve_grade_for_score(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        score: Decimal,
    ) -> GradingScale:
        grading_scale = await StudentAcademicRepository.find_grade_for_score(
            db=db,
            tenant_id=tenant_id,
            score=score,
        )

        if grading_scale is None:
            raise NotFoundException("No grading scale found for the supplied score.")

        return grading_scale

    @staticmethod
    async def assign_subject_to_class(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        payload: ClassSubjectTeacherCreate,
    ) -> ClassSubjectTeacher:
        # Adjust method names below if your repositories use different names.
        classroom = await ClassRoomRepository.get_classroom_by_id(
            db=db,
            tenant_id=tenant_id,
            class_id=payload.class_id,
        )

        if classroom is None:
            raise NotFoundException("Class not found.")

        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            subject_id=payload.subject_id,
        )

        if subject is None:
            raise NotFoundException("Subject not found.")

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            teacher_id=payload.teacher_id,
        )

        if teacher is None:
            raise NotFoundException("Teacher not found.")

        class_subject = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=payload.class_id,
            subject_id=payload.subject_id,
        )
        if class_subject is None:
            class_subject = ClassSubject(
                tenant_id=tenant_id,
                class_id=payload.class_id,
                subject_id=payload.subject_id,
                is_core=payload.is_core,
                is_active=payload.is_active,
            )
            class_subject = await StudentAcademicRepository.create_class_subject(
                db=db,
                class_subject=class_subject,
            )

        active_ta = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject.id,
        )
        if active_ta is not None:
            raise ConflictException("This subject is already assigned to this class.")

        teacher_assignment = TeacherAssignment(
            tenant_id=tenant_id,
            class_subject_id=class_subject.id,
            teacher_id=payload.teacher_id,
            is_active=payload.is_active,
            effective_from=date.today(),
        )
        await StudentAcademicRepository.create_teacher_assignment(
            db=db,
            assignment=teacher_assignment,
        )

        created_assignment = await StudentAcademicService._sync_legacy_class_subject_teacher(
            db=db,
            tenant_id=tenant_id,
            class_id=payload.class_id,
            subject_id=payload.subject_id,
            teacher_id=payload.teacher_id,
            is_core=payload.is_core,
            is_active=payload.is_active,
        )

        await db.commit()
        return created_assignment

    @staticmethod
    async def update_class_subject_teacher(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        payload: ClassSubjectTeacherUpdate,
    ) -> ClassSubjectTeacher:
        assignment = await StudentAcademicRepository.get_class_subject_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )

        if assignment is None:
            raise NotFoundException("Class subject teacher assignment not found.")

        update_data = payload.model_dump(exclude_unset=True)

        new_teacher_id = update_data.get("teacher_id")

        if new_teacher_id is not None and new_teacher_id != assignment.teacher_id:
            teacher = await TeacherRepository.get_teacher_by_id(
                db=db,
                tenant_id=tenant_id,
                teacher_id=new_teacher_id,
            )

            if teacher is None:
                raise NotFoundException("Teacher not found.")

        for field, value in update_data.items():
            setattr(assignment, field, value)

        updated_assignment = await StudentAcademicRepository.save_class_subject_teacher(
            db=db,
            assignment=assignment,
        )

        class_subject = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=assignment.class_id,
            subject_id=assignment.subject_id,
        )
        if class_subject is None:
            class_subject = ClassSubject(
                tenant_id=tenant_id,
                class_id=assignment.class_id,
                subject_id=assignment.subject_id,
                is_core=assignment.is_core,
                is_active=assignment.is_active,
            )
            class_subject = await StudentAcademicRepository.create_class_subject(
                db=db,
                class_subject=class_subject,
            )
        else:
            class_subject.is_core = assignment.is_core
            class_subject.is_active = assignment.is_active
            await StudentAcademicRepository.save_class_subject(db=db, class_subject=class_subject)

        active_ta = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=class_subject.id,
        )

        if new_teacher_id is not None and (active_ta is None or new_teacher_id != active_ta.teacher_id):
            if active_ta is not None:
                active_ta.is_active = False
                active_ta.effective_to = date.today()
                await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=active_ta)
            new_ta = TeacherAssignment(
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                teacher_id=new_teacher_id,
                is_active=assignment.is_active,
                effective_from=date.today(),
            )
            new_ta = await StudentAcademicRepository.create_teacher_assignment(db=db, assignment=new_ta)
            await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                exclude_assignment_id=new_ta.id,
            )
        elif active_ta is not None:
            active_ta.is_active = assignment.is_active
            if not assignment.is_active:
                active_ta.effective_to = date.today()
            await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=active_ta)
            await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                exclude_assignment_id=active_ta.id if active_ta.is_active else None,
            )
        elif assignment.is_active:
            new_ta = await StudentAcademicRepository.create_teacher_assignment(
                db=db,
                assignment=TeacherAssignment(
                    tenant_id=tenant_id,
                    class_subject_id=class_subject.id,
                    teacher_id=assignment.teacher_id,
                    is_active=True,
                    effective_from=date.today(),
                ),
            )
            await StudentAcademicService._deactivate_active_teacher_assignments_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
                exclude_assignment_id=new_ta.id,
            )

        await db.commit()
        return updated_assignment

    @staticmethod
    async def list_class_subject_teachers(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        class_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        active_only: bool = False,
    ) -> tuple[list[ClassSubjectTeacher], int]:
        return await StudentAcademicRepository.list_class_subject_teachers(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit,
            class_id=class_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            active_only=active_only,
        )

    @staticmethod
    async def deactivate_class_subject_teacher(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> ClassSubjectTeacher:
        assignment = await StudentAcademicRepository.get_class_subject_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            assignment_id=assignment_id,
        )

        if assignment is None:
            raise NotFoundException("Class subject teacher assignment not found.")

        assignment.is_active = False

        deactivated_assignment = (
            await StudentAcademicRepository.save_class_subject_teacher(
                db=db,
                assignment=assignment,
            )
        )

        class_subject = await StudentAcademicRepository.get_class_subject_by_class_and_subject(
            db=db,
            tenant_id=tenant_id,
            class_id=assignment.class_id,
            subject_id=assignment.subject_id,
        )
        if class_subject is not None:
            active_ta = await StudentAcademicRepository.get_active_teacher_assignment_for_class_subject(
                db=db,
                tenant_id=tenant_id,
                class_subject_id=class_subject.id,
            )
            if active_ta is not None:
                active_ta.is_active = False
                active_ta.effective_to = date.today()
                await StudentAcademicRepository.save_teacher_assignment(db=db, assignment=active_ta)

        await db.commit()
        return deactivated_assignment

    @staticmethod
    async def list_teacher_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[ClassSubjectTeacher]:
        return await StudentAcademicRepository.list_teacher_assignments(
            db=db,
            tenant_id=tenant_id,
            teacher_id=teacher_id,
            active_only=active_only,
        )

    @staticmethod
    async def list_class_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[ClassSubjectTeacher]:
        return await StudentAcademicRepository.list_class_assignments(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            active_only=active_only,
        )

    @staticmethod
    async def list_student_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID | None,
    ) -> list[ClassSubjectTeacher]:
        if class_id is None:
            return []

        return await StudentAcademicRepository.list_class_assignments(
            db=db,
            tenant_id=tenant_id,
            class_id=class_id,
            active_only=True,
        )

    @staticmethod
    async def list_student_subject_cards(
        db: AsyncSession,
        actor: Student,
    ) -> StudentSubjectCardListResponse:
        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
        )
        if student is None:
            raise NotFoundException("Student profile not found.")

        classroom = None
        if student.class_id is not None:
            classroom = await ClassRoomRepository.get_classroom_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=student.class_id,
            )

        session, term = await StudentAcademicService._resolve_student_dashboard_period(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student.id,
        )

        class_subjects: list[ClassSubject] = []
        if student.class_id is not None:
            class_subjects, _ = await StudentAcademicRepository.list_class_subjects(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=student.class_id,
                active_only=True,
                skip=0,
                limit=500,
            )

        result_filters = {
            "tenant_id": actor.tenant_id,
            "student_id": student.id,
            "skip": 0,
            "limit": 500,
        }
        if session is not None:
            result_filters["academic_session_id"] = session.id
        if term is not None:
            result_filters["academic_term_id"] = term.id
        results, _ = await StudentAcademicRepository.list_results(
            db=db,
            **result_filters,
        )
        results_by_subject_id = {result.subject_id: result for result in results}

        active_assignments: list[TeacherAssignment] = []
        if student.class_id is not None:
            active_assignments, _ = await StudentAcademicRepository.list_teacher_assignment_rows(
                db=db,
                tenant_id=actor.tenant_id,
                class_id=student.class_id,
                active_only=True,
                limit=500,
            )
        assignment_by_class_subject_id = {
            assignment.class_subject_id: assignment for assignment in active_assignments
        }

        items: list[StudentSubjectCardResponse] = []
        for class_subject in class_subjects:
            result = results_by_subject_id.get(class_subject.subject_id)
            assignment = assignment_by_class_subject_id.get(class_subject.id)
            teacher = None
            teacher_name = None
            teacher_id = None
            if assignment is not None:
                teacher_id = assignment.teacher_id
                teacher = await TeacherRepository.get_teacher_by_id(
                    db=db,
                    tenant_id=actor.tenant_id,
                    teacher_id=assignment.teacher_id,
                )
            if teacher is None:
                legacy_assignment = await StudentAcademicRepository.get_class_subject_teacher_by_class_subject(
                    db=db,
                    tenant_id=actor.tenant_id,
                    class_id=class_subject.class_id,
                    subject_id=class_subject.subject_id,
                )
                if legacy_assignment is not None:
                    teacher_id = legacy_assignment.teacher_id
                    teacher = await TeacherRepository.get_teacher_by_id(
                        db=db,
                        tenant_id=actor.tenant_id,
                        teacher_id=legacy_assignment.teacher_id,
                    )
            if teacher is not None:
                teacher_name = " ".join(
                    part for part in [teacher.first_name, teacher.last_name] if part
                ).strip() or None
            subject = await SubjectRepository.get_subject_by_id(
                db=db,
                tenant_id=actor.tenant_id,
                subject_id=class_subject.subject_id,
            )
            items.append(
                await StudentAcademicService._build_student_subject_card_response(
                    db=db,
                    class_subject=class_subject,
                    classroom=classroom,
                    subject=subject,
                    result=result,
                    session=session,
                    term=term,
                    teacher_id=teacher_id,
                    teacher_name=teacher_name,
                )
            )

        items.sort(key=lambda item: ((item.subject_name or item.subject_code or "").lower(), str(item.subject_id)))
        return StudentSubjectCardListResponse(
            items=items,
            total=len(items),
            context=StudentSubjectCardContextResponse(
                class_id=student.class_id,
                class_name=classroom.name if classroom else None,
                class_arm=classroom.arm if classroom else None,
                academic_session_id=session.id if session else None,
                academic_session_name=session.name if session else None,
                academic_term_id=term.id if term else None,
                academic_term_name=term.name.value if term else None,
            ),
        )

    @staticmethod
    def _is_result_complete(result: StudentSubjectResult) -> bool:
        return all(
            value is not None
            for value in (
                result.test_score,
                result.assessment_score,
                result.exam_score,
            )
        )

    @staticmethod
    def _score_or_zero(value: Decimal | None) -> Decimal:
        return value if value is not None else Decimal("0")

    @staticmethod
    async def _compute_grade(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        total_score: Decimal,
    ) -> tuple[str, str | None]:
        grading_scale = await StudentAcademicRepository.find_grade_for_score(
            db=db,
            tenant_id=tenant_id,
            score=total_score,
        )
        if grading_scale is None:
            raise NotFoundException("No grading scale found for the computed total score.")
        return grading_scale.grade, grading_scale.remark

    @staticmethod
    async def _resolve_result_grade(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        result: StudentSubjectResult,
    ) -> tuple[str | None, str | None]:
        if not StudentAcademicService._is_result_complete(result):
            return None, None

        if result.grade is not None:
            return result.grade, result.remark

        total_score = sum(
            (
                StudentAcademicService._score_or_zero(score)
                for score in (result.test_score, result.assessment_score, result.exam_score)
            ),
            Decimal("0"),
        )
        grade, remark = await StudentAcademicService._compute_grade(
            db=db,
            tenant_id=tenant_id,
            total_score=total_score,
        )
        return grade, remark

    @staticmethod
    async def _resolve_student_dashboard_period(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> tuple[AcademicSession | None, AcademicTerm | None]:
        session = await StudentAcademicRepository.get_current_academic_session(
            db=db,
            tenant_id=tenant_id,
        )
        if session is None:
            sessions, _ = await StudentAcademicRepository.list_academic_sessions(
                db=db,
                tenant_id=tenant_id,
                skip=0,
                limit=1,
            )
            session = sessions[0] if sessions else None

        term = await StudentAcademicRepository.get_current_term(
            db=db,
            tenant_id=tenant_id,
        )
        if term is None and session is not None:
            terms, _ = await StudentAcademicRepository.list_terms_by_session(
                db=db,
                tenant_id=tenant_id,
                academic_session_id=session.id,
                skip=0,
                limit=1,
            )
            term = terms[0] if terms else None

        if session is None or term is None:
            latest_results, _ = await StudentAcademicRepository.list_results(
                db=db,
                tenant_id=tenant_id,
                student_id=student_id,
                skip=0,
                limit=1,
            )
            latest_result = latest_results[0] if latest_results else None
            if latest_result is not None:
                if session is None:
                    session = await StudentAcademicRepository.get_academic_session_by_id(
                        db=db,
                        tenant_id=tenant_id,
                        academic_session_id=latest_result.academic_session_id,
                    )
                if term is None:
                    term = await StudentAcademicRepository.get_term_by_id(
                        db=db,
                        tenant_id=tenant_id,
                        term_id=latest_result.academic_term_id,
                    )

        return session, term

    @staticmethod
    async def _build_student_subject_card_response(
        db: AsyncSession,
        *,
        class_subject: ClassSubject,
        classroom,
        subject,
        result: StudentSubjectResult | None,
        session: AcademicSession | None,
        term: AcademicTerm | None,
        teacher_id: uuid.UUID | None,
        teacher_name: str | None,
    ) -> StudentSubjectCardResponse:
        grade = None
        remark = None
        if result is not None:
            grade, remark = await StudentAcademicService._resolve_result_grade(
                db=db,
                tenant_id=class_subject.tenant_id,
                result=result,
            )

        return StudentSubjectCardResponse(
            id=class_subject.id,
            result_id=result.id if result is not None else None,
            class_id=class_subject.class_id,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=class_subject.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_id=teacher_id,
            teacher_name=teacher_name,
            academic_session_id=session.id if session else None,
            academic_session_name=session.name if session else None,
            academic_term_id=term.id if term else None,
            academic_term_name=term.name.value if term else None,
            test_score=StudentAcademicService._score_or_zero(result.test_score) if result else Decimal("0"),
            assessment_score=StudentAcademicService._score_or_zero(result.assessment_score) if result else Decimal("0"),
            exam_score=StudentAcademicService._score_or_zero(result.exam_score) if result else Decimal("0"),
            total_score=result.total_score if result is not None else Decimal("0"),
            grade=grade,
            remark=remark if remark is not None else (result.remark if result else None),
            status=(result.status.value if hasattr(result.status, "value") else str(result.status)) if result else "pending",
            is_complete=StudentAcademicService._is_result_complete(result) if result else False,
        )

    @staticmethod
    async def _build_result_response(
        db: AsyncSession,
        result: StudentSubjectResult,
    ) -> StudentSubjectResultResponse:
        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=result.tenant_id,
            student_id=result.student_id,
        )
        classroom = await ClassRoomRepository.get_classroom_by_id(
            db=db,
            tenant_id=result.tenant_id,
            class_id=result.class_id,
        )
        subject = await SubjectRepository.get_subject_by_id(
            db=db,
            tenant_id=result.tenant_id,
            subject_id=result.subject_id,
        )
        teacher = None
        if result.teacher_assignment_id is not None:
            teacher_assignment = await StudentAcademicRepository.get_teacher_assignment_by_id(
                db=db,
                tenant_id=result.tenant_id,
                assignment_id=result.teacher_assignment_id,
            )
            if teacher_assignment is not None:
                teacher = await TeacherRepository.get_teacher_by_id(
                    db=db,
                    tenant_id=result.tenant_id,
                    teacher_id=teacher_assignment.teacher_id,
                )
        if teacher is None:
            teacher = await TeacherRepository.get_teacher_by_id(
                db=db,
                tenant_id=result.tenant_id,
                teacher_id=result.teacher_id,
            )
        session = await StudentAcademicRepository.get_academic_session_by_id(
            db=db,
            tenant_id=result.tenant_id,
            academic_session_id=result.academic_session_id,
        )
        term = await StudentAcademicRepository.get_term_by_id(
            db=db,
            tenant_id=result.tenant_id,
            term_id=result.academic_term_id,
        )
        grade, remark = await StudentAcademicService._resolve_result_grade(
            db=db,
            tenant_id=result.tenant_id,
            result=result,
        )

        return StudentSubjectResultResponse(
            id=result.id,
            tenant_id=result.tenant_id,
            student_id=result.student_id,
            student_name=(
                " ".join(part for part in [student.first_name, student.last_name] if part).strip()
                if student
                else None
            ),
            admission_number=student.admission_number if student else None,
            class_id=result.class_id,
            class_name=classroom.name if classroom else None,
            class_arm=classroom.arm if classroom else None,
            subject_id=result.subject_id,
            subject_name=subject.name if subject else None,
            subject_code=subject.code if subject else None,
            teacher_id=result.teacher_id,
            teacher_name=(
                " ".join(part for part in [teacher.first_name, teacher.last_name] if part).strip()
                if teacher
                else None
            ),
            class_subject_teacher_id=result.class_subject_teacher_id,
            teacher_assignment_id=result.teacher_assignment_id,
            academic_session_id=result.academic_session_id,
            academic_session_name=session.name if session else None,
            academic_term_id=result.academic_term_id,
            academic_term_name=term.name.value if term else None,
            test_score=result.test_score,
            assessment_score=result.assessment_score,
            exam_score=result.exam_score,
            total_score=result.total_score,
            grade=grade,
            remark=remark,
            status=result.status,
            recorded_by_actor_type=result.recorded_by_actor_type,
            recorded_by_actor_id=result.recorded_by_actor_id,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    @staticmethod
    async def upsert_student_result(
        db: AsyncSession,
        actor: TenantAdmin | Teacher,
        payload: StudentSubjectResultUpsert,
    ) -> StudentSubjectResultResponse:
        tenant_id = actor.tenant_id
        teacher_assignment, legacy = await StudentAcademicService._resolve_assignment_context(
            db=db,
            tenant_id=tenant_id,
            payload=payload,
        )

        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db=db,
            tenant_id=tenant_id,
            class_subject_id=teacher_assignment.class_subject_id,
        )
        if class_subject is None:
            raise NotFoundException("Class subject not found.")

        if isinstance(actor, Teacher) and teacher_assignment.teacher_id != actor.id:
            raise ForbiddenException("You can only edit class-subjects assigned to you.")

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=tenant_id,
            student_id=payload.student_id,
        )
        if student is None:
            raise NotFoundException("Student not found.")
        if student.class_id != class_subject.class_id:
            raise BadRequestException("Student does not belong to the selected class.")

        score_values = {
            "test_score": payload.test_score,
            "assessment_score": payload.assessment_score,
            "exam_score": payload.exam_score,
        }
        has_all_scores = all(value is not None for value in score_values.values())
        total_score = sum(
            (StudentAcademicService._score_or_zero(value) for value in score_values.values()),
            Decimal("0"),
        )
        if str(payload.status) == AcademicResultStatus.SUBMITTED.value and not has_all_scores:
            raise BadRequestException("All three scores must be recorded before submitting a result.")

        grade = None
        remark = None
        if has_all_scores:
            grade, remark = await StudentAcademicService._compute_grade(
                db=db,
                tenant_id=tenant_id,
                total_score=total_score,
            )

        legacy_id = legacy.id if legacy is not None else payload.class_subject_teacher_id
        if legacy_id is None:
            synced_legacy = await StudentAcademicService._sync_legacy_class_subject_teacher(
                db=db,
                tenant_id=tenant_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_id=teacher_assignment.teacher_id,
                is_core=class_subject.is_core,
                is_active=class_subject.is_active,
            )
            legacy_id = synced_legacy.id

        existing = await StudentAcademicRepository.get_result_by_teacher_assignment_scope(
            db=db,
            tenant_id=tenant_id,
            student_id=payload.student_id,
            teacher_assignment_id=teacher_assignment.id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
        )
        if existing is None:
            existing = await StudentAcademicRepository.get_result_by_scope(
                db=db,
                tenant_id=tenant_id,
                student_id=payload.student_id,
                class_subject_teacher_id=legacy_id,
                academic_session_id=payload.academic_session_id,
                academic_term_id=payload.academic_term_id,
            )

        if existing is not None:
            result = existing
        else:
            actor_type = (
                ActorType.TEACHER.value
                if isinstance(actor, Teacher)
                else ActorType.TENANT_ADMIN.value
            )
            result = StudentSubjectResult(
                tenant_id=tenant_id,
                student_id=payload.student_id,
                class_id=class_subject.class_id,
                subject_id=class_subject.subject_id,
                teacher_id=teacher_assignment.teacher_id,
                class_subject_teacher_id=legacy_id,
                teacher_assignment_id=teacher_assignment.id,
                academic_session_id=payload.academic_session_id,
                academic_term_id=payload.academic_term_id,
                recorded_by_actor_type=actor_type,
                recorded_by_actor_id=actor.id,
                test_score=payload.test_score,
                assessment_score=payload.assessment_score,
                exam_score=payload.exam_score,
                total_score=total_score,
                grade=grade,
                remark=remark,
                status=payload.status,
            )

        result.test_score = payload.test_score
        result.assessment_score = payload.assessment_score
        result.exam_score = payload.exam_score
        result.total_score = total_score
        result.grade = grade
        result.remark = remark
        result.status = payload.status
        result.teacher_assignment_id = teacher_assignment.id
        result.teacher_id = teacher_assignment.teacher_id

        saved = await StudentAcademicRepository.upsert_result(db=db, result=result)

        from app.modules.report_cards.service import ReportCardService

        await ReportCardService.mark_outdated_for_score_change(
            db=db,
            tenant_id=tenant_id,
            student_id=payload.student_id,
            academic_session_id=payload.academic_session_id,
            academic_term_id=payload.academic_term_id,
        )

        await db.commit()
        return await StudentAcademicService._build_result_response(db=db, result=saved)

    @staticmethod
    async def update_result_status(
        db: AsyncSession,
        actor: TenantAdmin,
        result_id: uuid.UUID,
        payload: StudentSubjectResultStatusUpdate,
    ) -> StudentSubjectResultResponse:
        result = await StudentAcademicRepository.get_result_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            result_id=result_id,
        )
        if result is None:
            raise NotFoundException("Result not found.")
        if str(payload.status) == AcademicResultStatus.SUBMITTED.value and not StudentAcademicService._is_result_complete(result):
            raise BadRequestException("All three scores must be recorded before a result can be submitted.")
        if StudentAcademicService._is_result_complete(result):
            grade, remark = await StudentAcademicService._resolve_result_grade(
                db=db,
                tenant_id=actor.tenant_id,
                result=result,
            )
            result.grade = grade
            result.remark = remark
        result.status = payload.status
        saved = await StudentAcademicRepository.upsert_result(db=db, result=result)
        await db.commit()
        return await StudentAcademicService._build_result_response(db=db, result=saved)

    @staticmethod
    async def list_results(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
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

        if isinstance(actor, Teacher):
            teacher_id = actor.id
        elif isinstance(actor, Student):
            student_id = actor.id
        elif isinstance(actor, Parent):
            if student_id is None:
                raise BadRequestException("student_id is required for parent academic results.")
            link = await StudentParentLinkRepository.get_by_student_and_parent(
                db=db,
                tenant_id=tenant_id,
                student_id=student_id,
                parent_id=actor.id,
            )
            if link is None:
                raise ForbiddenException("You cannot view academic records for this student.")

        results, total = await StudentAcademicRepository.list_results(
            db=db,
            tenant_id=tenant_id,
            skip=skip,
            limit=min(limit, 100),
            student_id=student_id,
            class_id=class_id,
            teacher_id=teacher_id,
            academic_session_id=academic_session_id,
            academic_term_id=academic_term_id,
            published_only=published_only,
        )
        return [
            await StudentAcademicService._build_result_response(db=db, result=result)
            for result in results
        ], total
