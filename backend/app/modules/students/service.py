import secrets
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.security import hash_password, verify_password
from app.config.settings import settings
from app.core.utils.validators import validate_password_strength
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.modules.auth_identity.models import ActorType, IdentifierType
from app.modules.auth_identity.schemas import AuthIdentityCreate
from app.modules.auth_identity.service import AuthIdentityService
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent
from app.modules.parents.repository import ParentRepository
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentLinkCode,
    StudentParentLink,
    StudentParentLinkRequest,
    StudentParentLinkRequestStatus,
    StudentProfileStatus,
)
from app.modules.students.repository import (
    StudentLinkCodeRepository,
    StudentParentLinkRepository,
    StudentParentLinkRequestRepository,
    StudentRepository,
)
from app.modules.students.schemas import (
    StudentChangePasswordRequest,
    StudentCreate,
    StudentLinkCodeCreate,
    StudentLinkCodeRedeem,
    StudentLinkCodeResponse,
    StudentOnboardingStatusResponse,
    StudentOnboardingUpdate,
    StudentParentLinkCreate,
    StudentParentLinkRequestCreate,
    StudentParentLinkRequestListResponse,
    StudentParentLinkRequestRespond,
    StudentParentLinkRequestResponse,
    StudentParentLinkResponse,
    StudentParentLinkUpdate,
    StudentProfileComplete,
    StudentResponse,
    StudentSelfUpdate,
    StudentUpdate,
)
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.repository import TenantRepository


class StudentService:
    """Business logic for student actors."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure actor is a tenant admin."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    def _ensure_student_actor(actor: Student) -> None:
        """Ensure actor is a student."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Student is not attached to a tenant")

    @staticmethod
    def _ensure_parent_actor(actor: Parent) -> None:
        """Ensure actor is a parent."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Parent is not attached to a tenant")

    @staticmethod
    def _ensure_teacher_actor(actor: Teacher) -> None:
        """Ensure actor is a teacher."""

        if not actor.tenant_id:
            raise ForbiddenException(detail="Teacher is not attached to a tenant")

    @staticmethod
    def _normalize_admission_number(admission_number: str) -> str:
        """Normalize admission number casing and whitespace."""

        return admission_number.strip().upper()

    @staticmethod
    def _get_default_admission_date() -> date:
        """Return the default admission date for new students."""

        return datetime.now(timezone.utc).date()

    @staticmethod
    def _resolve_profile_status(student: Student) -> StudentProfileStatus:
        """Resolve whether a student profile is complete."""

        required_fields = (
            student.first_name,
            student.last_name,
            student.date_of_birth,
            student.gender,
        )
        return (
            StudentProfileStatus.COMPLETE
            if all(value is not None for value in required_fields)
            else StudentProfileStatus.INCOMPLETE
        )

    @staticmethod
    async def _assert_parent_can_view_student(
        db: AsyncSession,
        *,
        parent: Parent,
        student_id: UUID,
    ) -> None:
        """Ensure the parent is linked to the target student."""

        link = await StudentParentLinkRepository.get_by_student_and_parent(
            db=db,
            tenant_id=parent.tenant_id,
            student_id=student_id,
            parent_id=parent.id,
        )
        if link is None:
            raise ForbiddenException(detail="You are not allowed to view this student profile")

    @staticmethod
    async def _assert_teacher_can_view_student(
        db: AsyncSession,
        *,
        teacher: Teacher,
        student: Student,
    ) -> None:
        """Ensure the teacher is assigned to the student's class."""

        if student.class_id is None:
            raise ForbiddenException(detail="You are not allowed to view this student profile")

        result = await db.execute(
            select(ClassRoom.id).where(
                ClassRoom.tenant_id == teacher.tenant_id,
                ClassRoom.id == student.class_id,
                ClassRoom.teacher_id == teacher.id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise ForbiddenException(detail="You are not allowed to view this student profile")

    @staticmethod
    async def create_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentCreate,
    ) -> StudentResponse:
        """Create a student actor and attach an AuthIdentity."""

        StudentService._ensure_tenant_admin(actor)

        admission_number = (
            StudentService._normalize_admission_number(payload.admission_number)
            if payload.admission_number
            else await StudentService.generate_admission_number(
                db=db,
                tenant_id=actor.tenant_id,
            )
        )

        if await StudentRepository.admission_number_exists(
            db=db,
            tenant_id=actor.tenant_id,
            admission_number=admission_number,
        ):
            raise ConflictException(detail="Admission number already exists")

        await AuthIdentityService.ensure_identifier_available(
            db=db,
            identifier=admission_number,
            identifier_type=IdentifierType.ADMISSION_NUMBER,
        )

        raw_password = settings.DEFAULT_STUDENT_PASSWORD

        student = Student(
            tenant_id=actor.tenant_id,
            admission_number=admission_number,
            password_hash=hash_password(raw_password),
            first_name=payload.first_name,
            last_name=payload.last_name,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            passport_photo_url=payload.passport_photo_url,
            admission_date=StudentService._get_default_admission_date(),
            graduation_date=payload.graduation_date,
            class_id=payload.class_id,
            arm=payload.arm,
            status=payload.status,
            account_status=StudentAccountStatus.ACTIVE,
            is_verified=True,
            is_active=True,
            password_reset_required=True,
            last_login_at=None,
            profile_status=StudentProfileStatus.INCOMPLETE,
        )
        student.profile_status = StudentService._resolve_profile_status(student)

        try:
            created_student = await StudentRepository.create_student(db=db, student=student)
            await AuthIdentityService.create_for_actor(
                db=db,
                tenant_id=actor.tenant_id,
                payload=AuthIdentityCreate(
                    identifier=admission_number,
                    identifier_type=IdentifierType.ADMISSION_NUMBER,
                    actor_type=ActorType.STUDENT,
                    actor_id=created_student.id,
                    is_active=True,
                ),
            )
            await db.commit()
            await db.refresh(created_student)
            return StudentResponse.model_validate(created_student).model_copy(
                update={
                    "temporary_password": raw_password,
                    "default_password": raw_password,
                }
            )
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Student creation failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def get_student_profile(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Student | Parent,
        student_id: UUID,
    ) -> StudentResponse:
        """Get a student profile by ID."""

        tenant_id = actor.tenant_id
        if not tenant_id:
            raise ForbiddenException(detail="Actor is not attached to a tenant")

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        if isinstance(actor, Student) and student.id != actor.id:
            raise ForbiddenException(detail="You are not allowed to view this student profile")

        if isinstance(actor, Parent):
            await StudentService._assert_parent_can_view_student(
                db=db,
                parent=actor,
                student_id=student.id,
            )

        if isinstance(actor, Teacher):
            await StudentService._assert_teacher_can_view_student(
                db=db,
                teacher=actor,
                student=student,
            )

        return StudentResponse.model_validate(student)

    @staticmethod
    async def get_my_student_profile(
        db: AsyncSession,
        actor: Student,
    ) -> StudentResponse:
        """Get the current student's profile."""

        StudentService._ensure_student_actor(actor)
        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")
        return StudentResponse.model_validate(student)

    @staticmethod
    async def update_my_student_profile(
        db: AsyncSession,
        actor: Student,
        payload: StudentOnboardingUpdate,
    ) -> StudentResponse:
        """Allow a student to update self-service profile fields."""

        StudentService._ensure_student_actor(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        for field, value in update_data.items():
            setattr(student, field, value)

        student.profile_status = StudentService._resolve_profile_status(student)
        updated_student = await StudentRepository.save(db=db, student=student)
        await db.commit()
        await db.refresh(updated_student)
        return StudentResponse.model_validate(updated_student)

    @staticmethod
    async def get_my_onboarding_status(
        db: AsyncSession,
        actor: Student,
    ) -> StudentOnboardingStatusResponse:
        """Return the current student onboarding status."""

        student = await StudentService.get_my_student_profile(
            db=db,
            actor=actor,
        )

        return StudentOnboardingStatusResponse(
            actor_type="student",
            student_id=student.id,
            onboarding_required=(
                student.password_reset_required
                or student.profile_status != StudentProfileStatus.COMPLETE
            ),
            profile_status=student.profile_status,
            completion_target="student",
            required_fields=["first_name", "last_name", "date_of_birth", "gender"],
            current_values={
                "admission_number": student.admission_number,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "date_of_birth": student.date_of_birth,
                "gender": student.gender,
                "passport_photo_url": student.passport_photo_url,
                "password_reset_required": student.password_reset_required,
            },
        )

    @staticmethod
    async def change_my_password(
        db: AsyncSession,
        actor: Student,
        payload: StudentChangePasswordRequest,
    ) -> StudentResponse:
        """Allow a student to change the default password."""

        StudentService._ensure_student_actor(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
        )
        if student is None or student.password_hash is None:
            raise NotFoundException(detail="Student profile not found")

        if payload.new_password != payload.confirm_password:
            raise BadRequestException(detail="New password and confirmation do not match")

        if not verify_password(payload.current_password, student.password_hash):
            raise BadRequestException(detail="Current password is incorrect")

        if verify_password(payload.new_password, student.password_hash):
            raise BadRequestException(
                detail="New password must be different from the current password"
            )

        try:
            validate_password_strength(payload.new_password)
        except ValueError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        student.password_hash = hash_password(payload.new_password)
        student.password_reset_required = False

        updated_student = await StudentRepository.save(db=db, student=student)
        await db.commit()
        await db.refresh(updated_student)
        return StudentResponse.model_validate(updated_student)

    @staticmethod
    async def list_students(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Parent,
        skip: int = 0,
        limit: int = 50,
        search: str | None = None,
        class_id: UUID | None = None,
        status: AcademicStatus | None = None,
    ) -> tuple[list[StudentResponse], int]:
        """List students visible to the current actor."""

        limit = min(limit, 100)

        if isinstance(actor, TenantAdmin):
            students, total = await StudentRepository.list_students(
                db=db,
                tenant_id=actor.tenant_id,
                skip=skip,
                limit=limit,
                search=search,
                class_id=class_id,
                status=status,
            )
            return [StudentResponse.model_validate(student) for student in students], total

        if isinstance(actor, Teacher):
            StudentService._ensure_teacher_actor(actor)
            filters = [
                Student.tenant_id == actor.tenant_id,
                ClassRoom.tenant_id == actor.tenant_id,
                ClassRoom.teacher_id == actor.id,
                Student.class_id == ClassRoom.id,
            ]
            if class_id is not None:
                filters.append(Student.class_id == class_id)
            if status is not None:
                filters.append(Student.status == status)
            if search:
                search_term = f"%{search.strip()}%"
                filters.append(
                    or_(
                        Student.first_name.ilike(search_term),
                        Student.last_name.ilike(search_term),
                        Student.admission_number.ilike(search_term),
                    )
                )

            total = (
                await db.execute(
                    select(func.count()).select_from(Student).join(
                        ClassRoom,
                        and_(
                            ClassRoom.id == Student.class_id,
                            ClassRoom.tenant_id == Student.tenant_id,
                        ),
                    ).where(*filters)
                )
            ).scalar_one()
            result = await db.execute(
                select(Student)
                .join(
                    ClassRoom,
                    and_(
                        ClassRoom.id == Student.class_id,
                        ClassRoom.tenant_id == Student.tenant_id,
                    ),
                )
                .where(*filters)
                .order_by(Student.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            students = list(result.scalars().all())
            return [StudentResponse.model_validate(student) for student in students], int(total)

        if not isinstance(actor, Parent):
            raise ForbiddenException(detail="You are not allowed to list students")

        StudentService._ensure_parent_actor(actor)
        links = await StudentParentLinkRepository.get_by_parent_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )
        students = [link.student for link in links if link.student is not None]

        if class_id is not None:
            students = [student for student in students if student.class_id == class_id]
        if status is not None:
            students = [student for student in students if student.status == status]
        if search:
            search_value = search.strip().lower()
            students = [
                student
                for student in students
                if search_value in (student.admission_number or "").lower()
                or search_value in (student.first_name or "").lower()
                or search_value in (student.last_name or "").lower()
            ]

        total = len(students)
        paginated_students = students[skip : skip + limit]
        return [StudentResponse.model_validate(student) for student in paginated_students], total

    @staticmethod
    async def update_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentUpdate,
    ) -> StudentResponse:
        """Update a student profile."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        if "admission_number" in update_data and update_data["admission_number"] is not None:
            normalized_admission_number = StudentService._normalize_admission_number(
                update_data["admission_number"]
            )
            if normalized_admission_number != student.admission_number:
                await AuthIdentityService.ensure_identifier_available(
                    db=db,
                    identifier=normalized_admission_number,
                    identifier_type=IdentifierType.ADMISSION_NUMBER,
                )
                if await StudentRepository.admission_number_exists(
                    db=db,
                    tenant_id=actor.tenant_id,
                    admission_number=normalized_admission_number,
                    exclude_student_id=student.id,
                ):
                    raise ConflictException(detail="Admission number already exists")

                await AuthIdentityService.update_identifier(
                    db=db,
                    actor_type=ActorType.STUDENT,
                    actor_id=student.id,
                    new_identifier=normalized_admission_number,
                    identifier_type=IdentifierType.ADMISSION_NUMBER,
                )
                update_data["admission_number"] = normalized_admission_number

        if "password" in update_data and update_data["password"] is not None:
            update_data["password_hash"] = hash_password(update_data.pop("password"))

        if "is_active" in update_data and update_data["is_active"] is False:
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
            )

        if (
            "account_status" in update_data
            and update_data["account_status"] == StudentAccountStatus.INACTIVE
        ):
            await AuthIdentityService.deactivate_for_actor(
                db=db,
                actor_type=ActorType.STUDENT,
                actor_id=student.id,
            )

        try:
            for field, value in update_data.items():
                setattr(student, field, value)

            student.profile_status = StudentService._resolve_profile_status(student)
            updated_student = await StudentRepository.save(db=db, student=student)
            await db.commit()
            await db.refresh(updated_student)
            return StudentResponse.model_validate(updated_student)
        except IntegrityError as exc:
            await db.rollback()
            raise BadRequestException(
                detail="Student update failed because of a duplicate or invalid value."
            ) from exc

    @staticmethod
    async def complete_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        student_id: UUID,
        payload: StudentProfileComplete,
    ) -> StudentResponse:
        """Complete an incomplete student profile."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        student.date_of_birth = payload.date_of_birth
        student.gender = payload.gender
        student.class_id = payload.class_id
        student.arm = payload.arm
        student.passport_photo_url = payload.passport_photo_url
        student.profile_status = StudentService._resolve_profile_status(student)

        updated_student = await StudentRepository.save(db=db, student=student)
        await db.commit()
        await db.refresh(updated_student)
        return StudentResponse.model_validate(updated_student)

    @staticmethod
    async def generate_admission_number(
        db: AsyncSession,
        tenant_id: UUID,
    ) -> str:
        """Generate a tenant-scoped admission number."""

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=tenant_id)
        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        prefix = tenant.admission_number_prefix
        if not prefix:
            raise BadRequestException(
                detail=(
                    "Admission number prefix has not been set for this school. "
                    "Complete school setup before creating students."
                )
            )

        current_year = datetime.now(timezone.utc).year

        for _ in range(50):
            random_digits = f"{secrets.randbelow(100000):05d}"
            admission_number = f"{prefix}{str(current_year)[-2:]}{random_digits}"
            existing_student = await StudentRepository.get_by_admission_number(
                db=db,
                tenant_id=tenant_id,
                admission_number=admission_number,
            )
            if existing_student is None:
                return admission_number

        raise BadRequestException(
            detail="Unable to generate a unique admission number right now. Please try again."
        )

    @staticmethod
    async def delete_student_profile(
        db: AsyncSession,
        actor: TenantAdmin,
        student_id: UUID,
    ) -> None:
        """Delete a student profile."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        await AuthIdentityService.deactivate_for_actor(
            db=db,
            actor_type=ActorType.STUDENT,
            actor_id=student.id,
        )
        await StudentRepository.delete_student(db=db, student=student)
        await db.commit()


class StudentParentLinkRequestService:
    """Business logic for parent-student link request approvals."""

    @staticmethod
    async def create_request(
        db: AsyncSession,
        actor: Parent,
        payload: StudentParentLinkRequestCreate,
    ) -> StudentParentLinkRequestResponse:
        """Create a pending link request from a parent to a student."""

        StudentService._ensure_parent_actor(actor)

        student = await StudentRepository.get_active_by_admission_number(
            db=db,
            tenant_id=actor.tenant_id,
            admission_number=payload.admission_number,
        )
        if student is None:
            raise NotFoundException(detail="Student not found for this admission number")

        existing_link = await StudentParentLinkRepository.get_by_student_and_parent(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student.id,
            parent_id=actor.id,
        )
        if existing_link is not None:
            raise ConflictException(detail="You are already linked to this student")

        existing_request = await StudentParentLinkRequestRepository.get_pending_by_parent_and_student(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
            student_id=student.id,
        )
        if existing_request is not None:
            raise ConflictException(detail="A pending request already exists for this student")

        link_request = StudentParentLinkRequest(
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
            student_id=student.id,
            admission_number_snapshot=student.admission_number,
            relationship_type=payload.relationship_type,
            status=StudentParentLinkRequestStatus.PENDING,
        )

        created_request = await StudentParentLinkRequestRepository.create(
            db=db,
            link_request=link_request,
        )
        await db.commit()

        refreshed_request = await StudentParentLinkRequestRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            request_id=created_request.id,
        )
        if refreshed_request is None:
            raise NotFoundException(detail="Parent link request not found after creation")

        return StudentParentLinkRequestResponse.model_validate(refreshed_request)

    @staticmethod
    async def list_parent_requests(
        db: AsyncSession,
        actor: Parent,
    ) -> tuple[list[StudentParentLinkRequestResponse], int]:
        """Return link requests created by the logged-in parent."""

        StudentService._ensure_parent_actor(actor)

        requests = await StudentParentLinkRequestRepository.list_by_parent_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )
        items = [StudentParentLinkRequestResponse.model_validate(item) for item in requests]
        return items, len(items)

    @staticmethod
    async def list_student_requests(
        db: AsyncSession,
        actor: Student,
    ) -> tuple[list[StudentParentLinkRequestResponse], int]:
        """Return pending parent link requests for the logged-in student."""

        StudentService._ensure_student_actor(actor)

        requests = await StudentParentLinkRequestRepository.list_by_student_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
            status=StudentParentLinkRequestStatus.PENDING,
        )
        items = [StudentParentLinkRequestResponse.model_validate(item) for item in requests]
        return items, len(items)

    @staticmethod
    async def respond_to_request(
        db: AsyncSession,
        actor: Student,
        request_id: UUID,
        payload: StudentParentLinkRequestRespond,
    ) -> StudentParentLinkRequestResponse:
        """Allow a student to approve or reject a pending parent request."""

        StudentService._ensure_student_actor(actor)

        link_request = await StudentParentLinkRequestRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            request_id=request_id,
            lock=True,
        )
        if link_request is None or link_request.student_id != actor.id:
            raise NotFoundException(detail="Parent link request not found")

        if link_request.status != StudentParentLinkRequestStatus.PENDING:
            raise BadRequestException(detail="This parent link request has already been processed")

        action = payload.action.strip().lower()
        link_request.responded_at = datetime.now(timezone.utc)

        if action == "approve":
            existing_link = await StudentParentLinkRepository.get_by_student_and_parent(
                db=db,
                tenant_id=actor.tenant_id,
                student_id=actor.id,
                parent_id=link_request.parent_id,
            )
            if existing_link is None:
                await StudentParentLinkRepository.create_student_parent_link(
                    db=db,
                    link=StudentParentLink(
                        tenant_id=actor.tenant_id,
                        student_id=actor.id,
                        parent_id=link_request.parent_id,
                        relationship_type=link_request.relationship_type,
                    ),
                )
            link_request.status = StudentParentLinkRequestStatus.APPROVED
        elif action == "reject":
            link_request.status = StudentParentLinkRequestStatus.REJECTED
        else:
            raise BadRequestException(detail="Unsupported parent link request action")

        await StudentParentLinkRequestRepository.save(db=db, link_request=link_request)
        await db.commit()

        refreshed_request = await StudentParentLinkRequestRepository.get_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            request_id=link_request.id,
        )
        if refreshed_request is None:
            raise NotFoundException(detail="Parent link request not found after update")

        return StudentParentLinkRequestResponse.model_validate(refreshed_request)


class StudentParentLinkService:
    """Business logic for student-parent relationships."""

    @staticmethod
    async def create_student_parent_link(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentParentLinkCreate,
    ) -> StudentParentLinkResponse:
        """Create a student-parent relationship."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=payload.student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=payload.parent_id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        existing_link = await StudentParentLinkRepository.get_by_student_and_parent(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=payload.student_id,
            parent_id=payload.parent_id,
        )
        if existing_link is not None:
            raise BadRequestException(detail="Parent is already linked to this student")

        link = StudentParentLink(
            tenant_id=actor.tenant_id,
            student_id=payload.student_id,
            parent_id=payload.parent_id,
            relationship_type=payload.relationship_type,
            is_primary_contact=payload.is_primary_contact,
            receives_academic_updates=payload.receives_academic_updates,
            receives_fee_updates=payload.receives_fee_updates,
        )
        created_link = await StudentParentLinkRepository.create_student_parent_link(
            db=db,
            link=link,
        )
        await db.commit()
        await db.refresh(created_link)
        return StudentParentLinkResponse.model_validate(created_link)

    @staticmethod
    async def update_student_parent_link(
        db: AsyncSession,
        actor: TenantAdmin,
        link_id: UUID,
        payload: StudentParentLinkUpdate,
    ) -> StudentParentLinkResponse:
        """Update a student-parent relationship."""

        StudentService._ensure_tenant_admin(actor)

        link = await StudentParentLinkRepository.get_parent_student_link_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            link_id=link_id,
        )
        if link is None:
            raise NotFoundException(detail="Student-parent link not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No update data provided")

        for field, value in update_data.items():
            setattr(link, field, value)

        updated_link = await StudentParentLinkRepository.update_student_parent_link(
            db=db,
            link=link,
        )
        await db.commit()
        await db.refresh(updated_link)
        return StudentParentLinkResponse.model_validate(updated_link)

    @staticmethod
    async def delete_student_parent_link(
        db: AsyncSession,
        actor: TenantAdmin,
        link_id: UUID,
    ) -> None:
        """Delete a student-parent relationship."""

        StudentService._ensure_tenant_admin(actor)

        link = await StudentParentLinkRepository.get_parent_student_link_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            link_id=link_id,
        )
        if link is None:
            raise NotFoundException(detail="Student-parent link not found")

        await StudentParentLinkRepository.delete_student_parent_link(db=db, link=link)
        await db.commit()

    @staticmethod
    async def list_my_parent_links(
        db: AsyncSession,
        actor: Student,
    ) -> tuple[list[StudentParentLinkResponse], int]:
        """List parent links for the logged-in student."""

        StudentService._ensure_student_actor(actor)

        links = await StudentParentLinkRepository.get_by_student_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=actor.id,
        )
        items = [StudentParentLinkResponse.model_validate(link) for link in links]
        return items, len(items)


class StudentLinkCodeService:
    """Business logic for student pairing codes."""

    @staticmethod
    async def create_student_link_code(
        db: AsyncSession,
        actor: TenantAdmin,
        payload: StudentLinkCodeCreate,
    ) -> StudentLinkCodeResponse:
        """Generate a pairing code for a student."""

        StudentService._ensure_tenant_admin(actor)

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=payload.student_id,
        )
        if student is None:
            raise NotFoundException(detail="Student profile not found")

        link_code = StudentLinkCode(
            tenant_id=actor.tenant_id,
            student_id=payload.student_id,
            code=StudentLinkCode.generate_code(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            max_use=payload.max_use,
        )
        created_code = await StudentLinkCodeRepository.create(db=db, link_code=link_code)
        await db.commit()
        await db.refresh(created_code)
        return StudentLinkCodeResponse.model_validate(created_code)

    @staticmethod
    async def redeem_student_link_code(
        db: AsyncSession,
        actor: Parent,
        payload: StudentLinkCodeRedeem,
    ) -> StudentParentLinkResponse:
        """Link the logged-in parent to a student by redeeming a pairing code."""

        StudentService._ensure_parent_actor(actor)

        parent = await ParentRepository.get_parent_by_id(
            db=db,
            tenant_id=actor.tenant_id,
            parent_id=actor.id,
        )
        if parent is None:
            raise NotFoundException(detail="Parent profile not found")

        link_code = await StudentLinkCodeRepository.get_code(
            db=db,
            tenant_id=actor.tenant_id,
            code=payload.code,
        )
        if link_code is None or not link_code.is_active:
            raise BadRequestException(detail="Student link code is invalid or expired")

        existing_link = await StudentParentLinkRepository.get_by_student_and_parent(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=link_code.student_id,
            parent_id=parent.id,
        )
        if existing_link is not None:
            raise BadRequestException(detail="You are already linked to this student")

        link = StudentParentLink(
            tenant_id=actor.tenant_id,
            student_id=link_code.student_id,
            parent_id=parent.id,
            relationship_type=payload.relationship_type,
            is_primary_contact=payload.is_primary_contact,
            receives_academic_updates=payload.receives_academic_updates,
            receives_fee_updates=payload.receives_fee_updates,
        )
        created_link = await StudentParentLinkRepository.create_student_parent_link(
            db=db,
            link=link,
        )

        link_code.use_count += 1
        if link_code.is_exhausted:
            link_code.used_at = datetime.now(timezone.utc)
        await StudentLinkCodeRepository.update(db=db, link_code=link_code)
        await db.commit()
        await db.refresh(created_link)

        return StudentParentLinkResponse.model_validate(created_link)
