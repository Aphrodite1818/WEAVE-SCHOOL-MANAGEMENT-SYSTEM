# ====================================== #
#      cbt/academics/service.py          #
# ====================================== #

"""Build the academic bootstrap projection consumed by local CBT servers."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.cbt.academics.schemas import (
    CBTAcademicBootstrapResponse,
    CBTAcademicContextSnapshot,
    CBTAcademicStructureSnapshot,
    CBTArmLabelSnapshot,
    CBTAssessmentComponentSnapshot,
    CBTAssessmentSchemeSnapshot,
    CBTAssessmentSnapshot,
    CBTClassSnapshot,
    CBTCurriculumSnapshot,
    CBTDepartmentSnapshot,
    CBTLevelSnapshot,
    CBTLevelSubjectSnapshot,
    CBTReadinessBlocker,
    CBTReadinessSnapshot,
    CBTServerSnapshot,
    CBTSchoolSnapshot,
    CBTSessionSnapshot,
    CBTStaffSnapshot,
    CBTStudentEnrollmentSnapshot,
    CBTStudentSnapshot,
    CBTSubjectOfferingSnapshot,
    CBTSubjectSnapshot,
    CBTSyncMetadata,
    CBTTeacherAssignmentSnapshot,
    CBTTeacherSnapshot,
    CBTTermSnapshot,
)
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.classes.repository import (
    AcademicLevelRepository,
    ArmLabelRepository,
    ClassRoomRepository,
    DepartmentRepository,
)
from app.modules.student_academics.assessment_repository import AssessmentRepository
from app.modules.student_academics.curriculum_service import (
    CurriculumResolutionService,
)
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    LevelSubject,
)
from app.modules.student_academics.repository import StudentAcademicRepository
from app.modules.students.models import (
    AcademicStatus,
    StudentEnrollment,
)
from app.modules.students.repository import StudentEnrollmentRepository
from app.modules.subjects.repository import SubjectRepository
from app.modules.teachers.models import TeacherMembershipStatus
from app.modules.teachers.repository import TeacherMembershipRepository
from app.tenant_management.repository import TenantRepository


class CBTAcademicSyncService:
    """Read-only façade exposing Cloud academic state to one CBT server."""

    SCHEMA_VERSION = 1
    PAGE_SIZE = 500

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    async def build_bootstrap(
        cls,
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTAcademicBootstrapResponse:
        """Build a complete current academic snapshot for one CBT server.

        Tenant scope comes exclusively from the authenticated machine context.
        The caller never supplies tenant_id.
        """

        tenant_id = current_server.tenant_id

        tenant = await TenantRepository.get_by_id(
            db,
            tenant_id,
        )
        if tenant is None:
            raise NotFoundException("Tenant not found.")

        session = await StudentAcademicRepository.get_current_academic_session(
            db,
            tenant_id,
        )

        term = await StudentAcademicRepository.get_current_term(
            db,
            tenant_id,
        )

        cls._validate_current_context(
            session=session,
            term=term,
        )

        structure = await cls._load_structure(
            db,
            tenant_id=tenant_id,
        )

        student_snapshot, enrollments = await cls._load_students(
            db,
            tenant_id=tenant_id,
            session=session,
            term=term,
        )

        curriculum = await cls._load_curriculum(
            db,
            tenant_id=tenant_id,
            term=term,
            enrollments=enrollments,
        )

        assessment = await cls._load_assessment(
            db,
            tenant_id=tenant_id,
        )

        staff = await cls._load_staff(
            db,
            tenant_id=tenant_id,
            valid_class_ids={classroom.id for classroom in structure.classes},
            valid_level_subject_ids={
                level_subject.id for level_subject in curriculum.level_subjects
            },
        )

        academic_context = cls._build_academic_context(
            session=session,
            term=term,
        )

        readiness = cls._build_readiness(
            institution_type=tenant.institution_type,
            session=session,
            term=term,
            structure=structure,
            curriculum=curriculum,
            assessment=assessment,
        )

        return CBTAcademicBootstrapResponse(
            sync=CBTSyncMetadata(
                schema_version=cls.SCHEMA_VERSION,
                snapshot_id=uuid4(),
                generated_at=datetime.now(timezone.utc),
                cursor=None,
            ),
            server=CBTServerSnapshot(
                id=current_server.server_id,
                name=current_server.server_name,
            ),
            school=CBTSchoolSnapshot(
                id=tenant.id,
                name=tenant.school_name,
                institution_type=(
                    tenant.institution_type.value if tenant.institution_type is not None else None
                ),
                timezone=tenant.timezone,
            ),
            academic_context=academic_context,
            structure=structure,
            curriculum=curriculum,
            assessment=assessment,
            staff=staff,
            students=student_snapshot,
            readiness=readiness,
        )

    # ------------------------------------------------------------------
    # Academic context
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_current_context(
        *,
        session: AcademicSession | None,
        term: AcademicTerm | None,
    ) -> None:
        """Reject internally inconsistent current-session/current-term state."""

        if term is None:
            return

        if session is None:
            raise ConflictException(
                "A current academic term exists without a current academic session."
            )

        if term.academic_session_id != session.id:
            raise ConflictException(
                "The current academic term does not belong to the current academic session."
            )

    @staticmethod
    def _build_academic_context(
        *,
        session: AcademicSession | None,
        term: AcademicTerm | None,
    ) -> CBTAcademicContextSnapshot:

        session_snapshot = None
        if session is not None:
            session_snapshot = CBTSessionSnapshot(
                id=session.id,
                name=session.name,
                status=session.status.value,
                start_date=session.start_date,
                end_date=session.end_date,
            )

        term_snapshot = None
        if term is not None:
            term_snapshot = CBTTermSnapshot(
                id=term.id,
                academic_session_id=term.academic_session_id,
                name=term.name.value,
                status=term.status.value,
                start_date=term.start_date,
                end_date=term.end_date,
            )

        return CBTAcademicContextSnapshot(
            session=session_snapshot,
            term=term_snapshot,
        )

    # ------------------------------------------------------------------
    # Structure
    # ------------------------------------------------------------------

    @classmethod
    async def _load_structure(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> CBTAcademicStructureSnapshot:

        levels = await AcademicLevelRepository.list_for_tenant(
            db,
            tenant_id,
            active_only=True,
        )

        departments = await DepartmentRepository.list_for_tenant(
            db,
            tenant_id,
            active_only=True,
        )

        arm_labels = await ArmLabelRepository.list_for_tenant(
            db,
            tenant_id,
            active_only=True,
        )

        classrooms = await cls._load_all_classes(
            db,
            tenant_id=tenant_id,
        )

        return CBTAcademicStructureSnapshot(
            levels=[
                CBTLevelSnapshot(
                    id=level.id,
                    name=level.name,
                    category=level.category.value,
                    position=level.position,
                )
                for level in levels
            ],
            departments=[
                CBTDepartmentSnapshot(
                    id=department.id,
                    name=department.name,
                )
                for department in departments
            ],
            arm_labels=[
                CBTArmLabelSnapshot(
                    id=arm.id,
                    label=arm.label,
                    position=arm.position,
                )
                for arm in arm_labels
            ],
            classes=[
                CBTClassSnapshot(
                    id=classroom.id,
                    academic_level_id=classroom.academic_level_id,
                    department_id=classroom.department_id,
                    arm_label_id=classroom.arm_label_id,
                    display_name=classroom.display_name,
                )
                for classroom in classrooms
            ],
        )

    @classmethod
    async def _load_all_classes(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> list:
        """Page through classes so bootstrap never silently truncates them."""

        rows = []
        offset = 0

        while True:
            batch = await ClassRoomRepository.list_for_tenant(
                db,
                tenant_id,
                active_only=True,
                include_archived=False,
                offset=offset,
                limit=cls.PAGE_SIZE,
            )

            rows.extend(batch)

            if len(batch) < cls.PAGE_SIZE:
                break

            offset += len(batch)

        return rows

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------

    @classmethod
    async def _load_students(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        session: AcademicSession | None,
        term: AcademicTerm | None,
    ) -> tuple[CBTStudentSnapshot, list[StudentEnrollment]]:

        if session is None:
            return (
                CBTStudentSnapshot(enrollments=[]),
                [],
            )

        enrollments = await cls._load_all_current_enrollments(
            db,
            tenant_id=tenant_id,
            academic_session_id=session.id,
        )

        if term is not None:
            effective_departments = (
                await CurriculumResolutionService.resolve_departments_for_enrollments(
                    db,
                    tenant_id=tenant_id,
                    enrollments=enrollments,
                    academic_term=term,
                )
            )
        else:
            effective_departments = {enrollment.id: None for enrollment in enrollments}

        snapshots: list[CBTStudentEnrollmentSnapshot] = []

        for enrollment in enrollments:
            student = enrollment.student

            display_name = " ".join(
                part
                for part in (
                    student.first_name,
                    student.last_name,
                )
                if part
            ).strip()

            if not display_name:
                display_name = student.admission_number

            snapshots.append(
                CBTStudentEnrollmentSnapshot(
                    enrollment_id=enrollment.id,
                    student_id=student.id,
                    admission_number=student.admission_number,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    display_name=display_name,
                    academic_session_id=enrollment.academic_session_id,
                    academic_level_id=enrollment.academic_level_id,
                    class_id=enrollment.class_id,
                    department_id=effective_departments.get(enrollment.id),
                    student_status=student.status.value,
                    started_on=enrollment.started_on,
                )
            )

        return (
            CBTStudentSnapshot(
                enrollments=snapshots,
            ),
            enrollments,
        )

    @classmethod
    async def _load_all_current_enrollments(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        academic_session_id: UUID,
    ) -> list[StudentEnrollment]:

        rows: list[StudentEnrollment] = []
        offset = 0

        while True:
            batch = await StudentEnrollmentRepository.list_current_for_session(
                db,
                tenant_id,
                academic_session_id,
                offset=offset,
                limit=cls.PAGE_SIZE,
            )

            rows.extend(batch)

            if len(batch) < cls.PAGE_SIZE:
                break

            offset += len(batch)

        return rows

    # ------------------------------------------------------------------
    # Curriculum
    # ------------------------------------------------------------------

    @classmethod
    async def _load_curriculum(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        term: AcademicTerm | None,
        enrollments: list[StudentEnrollment],
    ) -> CBTCurriculumSnapshot:

        if term is None:
            return CBTCurriculumSnapshot(
                subjects=[],
                level_subjects=[],
                subject_offerings=[],
            )

        # Only academically ACTIVE students become part of the automatic
        # eligible candidate pools.
        #
        # Other current enrollment records may still be present in the student
        # projection with their status so local CBT has accurate identity state.
        academically_eligible_enrollments = [
            enrollment
            for enrollment in enrollments
            if enrollment.student.status == AcademicStatus.ACTIVE
        ]

        resolved_offerings = await CurriculumResolutionService.resolve_term_offering_eligibility(
            db,
            tenant_id=tenant_id,
            academic_term=term,
            enrollments=academically_eligible_enrollments,
        )

        if not resolved_offerings:
            return CBTCurriculumSnapshot(
                subjects=[],
                level_subjects=[],
                subject_offerings=[],
            )

        required_level_subject_ids = {offering.level_subject_id for offering in resolved_offerings}

        all_level_subjects = await cls._load_all_level_subjects(
            db,
            tenant_id=tenant_id,
        )

        level_subjects: list[LevelSubject] = [
            level_subject
            for level_subject in all_level_subjects
            if level_subject.id in required_level_subject_ids
        ]

        required_subject_ids = {level_subject.subject_id for level_subject in level_subjects}

        subjects = await cls._load_subjects_by_ids(
            db,
            tenant_id=tenant_id,
            subject_ids=required_subject_ids,
        )

        return CBTCurriculumSnapshot(
            subjects=[
                CBTSubjectSnapshot(
                    id=subject.id,
                    name=subject.name,
                    code=subject.code,
                )
                for subject in subjects
            ],
            level_subjects=[
                CBTLevelSubjectSnapshot(
                    id=level_subject.id,
                    academic_level_id=level_subject.academic_level_id,
                    subject_id=level_subject.subject_id,
                )
                for level_subject in level_subjects
            ],
            subject_offerings=[
                CBTSubjectOfferingSnapshot(
                    id=offering.offering_id,
                    level_subject_id=offering.level_subject_id,
                    academic_term_id=offering.academic_term_id,
                    department_id=offering.department_id,
                    is_elective=offering.is_elective,
                    eligible_enrollment_ids=list(offering.eligible_enrollment_ids),
                )
                for offering in resolved_offerings
            ],
        )

    @classmethod
    async def _load_all_level_subjects(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> list[LevelSubject]:

        rows: list[LevelSubject] = []
        offset = 0

        while True:
            batch, total = await StudentAcademicRepository.list_level_subjects(
                db,
                tenant_id,
                active_only=True,
                include_archived=False,
                skip=offset,
                limit=cls.PAGE_SIZE,
            )

            rows.extend(batch)

            if len(rows) >= total or not batch:
                break

            offset += len(batch)

        return rows

    @classmethod
    async def _load_subjects_by_ids(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        subject_ids: set[UUID],
    ) -> list:

        if not subject_ids:
            return []

        ids = list(subject_ids)
        subjects = []

        for start in range(0, len(ids), cls.PAGE_SIZE):
            chunk = ids[start : start + cls.PAGE_SIZE]

            batch = await SubjectRepository.get_subjects_by_id(
                db,
                tenant_id,
                chunk,
            )

            subjects.extend(batch)

        return subjects

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_assessment(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> CBTAssessmentSnapshot:

        scheme = await AssessmentRepository.get_active_scheme(
            db,
            tenant_id,
        )

        if scheme is None:
            return CBTAssessmentSnapshot(
                scheme=None,
                components=[],
            )

        components = await AssessmentRepository.list_components(
            db,
            tenant_id,
            scheme.id,
        )

        return CBTAssessmentSnapshot(
            scheme=CBTAssessmentSchemeSnapshot(
                id=scheme.id,
                name=scheme.name,
                status=scheme.status.value,
            ),
            components=[
                CBTAssessmentComponentSnapshot(
                    id=component.id,
                    assessment_scheme_id=component.assessment_scheme_id,
                    name=component.name,
                    code=component.code,
                    maximum_score=component.maximum_score,
                    position=component.position,
                )
                for component in components
            ],
        )

    # ------------------------------------------------------------------
    # Staff
    # ------------------------------------------------------------------

    @classmethod
    async def _load_staff(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
        valid_class_ids: set[UUID],
        valid_level_subject_ids: set[UUID],
    ) -> CBTStaffSnapshot:

        teachers = await cls._load_all_active_teachers(
            db,
            tenant_id=tenant_id,
        )

        teacher_snapshots: list[CBTTeacherSnapshot] = []

        for membership in teachers:
            account = membership.teacher_account

            if account is None:
                # Broken membership/account relationship should not produce
                # a malformed CBT contract.
                continue

            display_name = " ".join(
                part
                for part in (
                    account.first_name,
                    account.last_name,
                )
                if part
            ).strip()

            if not display_name:
                display_name = account.email

            teacher_snapshots.append(
                CBTTeacherSnapshot(
                    account_id=account.id,
                    membership_id=membership.id,
                    display_name=display_name,
                    email=account.email,
                    staff_id=membership.staff_id,
                )
            )

        valid_teacher_membership_ids = {teacher.membership_id for teacher in teacher_snapshots}

        assignment_rows = await cls._load_all_active_teacher_assignments(
            db,
            tenant_id=tenant_id,
        )

        assignments: list[CBTTeacherAssignmentSnapshot] = []

        for row in assignment_rows:
            assignment = row["assignment"]

            # Keep the projection referentially complete.
            #
            # If an assignment points to an inactive/missing object that is
            # not present elsewhere in this bootstrap, don't produce a
            # dangling local foreign key.
            if assignment.teacher_membership_id not in valid_teacher_membership_ids:
                continue

            if assignment.class_id not in valid_class_ids:
                continue

            if assignment.level_subject_id not in valid_level_subject_ids:
                continue

            assignments.append(
                CBTTeacherAssignmentSnapshot(
                    id=assignment.id,
                    teacher_membership_id=assignment.teacher_membership_id,
                    class_id=assignment.class_id,
                    level_subject_id=assignment.level_subject_id,
                    effective_from=assignment.effective_from,
                    effective_to=assignment.effective_to,
                )
            )

        return CBTStaffSnapshot(
            teachers=teacher_snapshots,
            teacher_assignments=assignments,
        )

    @classmethod
    async def _load_all_active_teachers(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> list:

        rows = []
        offset = 0

        while True:
            batch, total = await TeacherMembershipRepository.list_for_tenant(
                db,
                tenant_id,
                status=TeacherMembershipStatus.ACTIVE,
                offset=offset,
                limit=cls.PAGE_SIZE,
            )

            rows.extend(batch)

            if len(rows) >= total or not batch:
                break

            offset += len(batch)

        return rows

    @classmethod
    async def _load_all_active_teacher_assignments(
        cls,
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> list[dict]:

        rows: list[dict] = []
        offset = 0

        while True:
            batch, total = await StudentAcademicRepository.list_teacher_assignment_rows(
                db,
                tenant_id,
                status="active",
                skip=offset,
                limit=cls.PAGE_SIZE,
            )

            rows.extend(batch)

            if len(rows) >= total or not batch:
                break

            offset += len(batch)

        return rows

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    @staticmethod
    def _build_readiness(
        *,
        institution_type,
        session: AcademicSession | None,
        term: AcademicTerm | None,
        structure: CBTAcademicStructureSnapshot,
        curriculum: CBTCurriculumSnapshot,
        assessment: CBTAssessmentSnapshot,
    ) -> CBTReadinessSnapshot:

        blockers: list[CBTReadinessBlocker] = []

        if institution_type is None:
            blockers.append(
                CBTReadinessBlocker(
                    code="INSTITUTION_TYPE_NOT_CONFIGURED",
                    message="The school's institution type has not been configured.",
                )
            )

        if session is None:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_CURRENT_ACADEMIC_SESSION",
                    message="No current academic session is available.",
                )
            )
        elif session.status != AcademicSessionStatus.OPEN:
            blockers.append(
                CBTReadinessBlocker(
                    code="ACADEMIC_SESSION_NOT_OPEN",
                    message="The current academic session is not open.",
                )
            )

        if term is None:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_CURRENT_ACADEMIC_TERM",
                    message="No current academic term is available.",
                )
            )
        elif term.status != AcademicTermStatus.OPEN:
            blockers.append(
                CBTReadinessBlocker(
                    code="ACADEMIC_TERM_NOT_OPEN",
                    message="The current academic term is not open.",
                )
            )

        if not structure.levels:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_ACADEMIC_LEVELS",
                    message="No active academic levels are configured.",
                )
            )

        if term is not None and not curriculum.subject_offerings:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_SUBJECT_OFFERINGS",
                    message="No subjects are configured for the current term.",
                )
            )

        if assessment.scheme is None:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_ACTIVE_ASSESSMENT_SCHEME",
                    message="No active assessment scheme is configured.",
                )
            )
        elif not assessment.components:
            blockers.append(
                CBTReadinessBlocker(
                    code="NO_ASSESSMENT_COMPONENTS",
                    message="The active assessment scheme has no active components.",
                )
            )

        return CBTReadinessSnapshot(
            can_conduct_exam=not blockers,
            blockers=blockers,
        )
