"""Application service for level curricula and term-specific specialization."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.category_catalog import category_supports_departments
from app.modules.classes.models import AcademicLevelStatus
from app.modules.classes.repository import (
    AcademicLevelRepository,
    ClassRoomRepository,
    DepartmentRepository,
)
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.curriculum_v2_repository import CurriculumSubjectRepository
from app.modules.student_academics.curriculum_v2_schemas import (
    ClassTermDepartmentResponse,
    CurriculumOfferingCreate,
    CurriculumOfferingResponse,
    CurriculumResponse,
    CurriculumSubjectCreate,
    CurriculumSubjectResponse,
    CurriculumSubjectUpdate,
)
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    AcademicTerm,
    AcademicTermName,
    AcademicTermStatus,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.student_academics.write_guard import ensure_academic_write_window
from app.modules.subjects.models import Subject
from app.tenant_management.repository import TenantRepository


class AcademicCurriculumService:
    """Manage reusable level curricula and explicit term-specific specialization."""

    _TERM_POSITIONS = {
        AcademicTermName.FIRST_TERM: 1,
        AcademicTermName.SECOND_TERM: 2,
        AcademicTermName.THIRD_TERM: 3,
    }

    @staticmethod
    async def _curriculum(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
        *,
        require_active_level: bool = False,
    ) -> Curriculum:
        """Return the permanent curriculum container without creating state on reads."""

        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
        if level is None:
            raise NotFoundException("Academic level not found.")
        if require_active_level and level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException(
                "Academic level must be active before curriculum is configured."
            )

        row = (
            await db.execute(
                select(Curriculum).where(
                    Curriculum.tenant_id == tenant_id,
                    Curriculum.academic_level_id == level_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundException(
                "Curriculum not found. Activate the academic level before configuring curriculum."
            )
        return row

    @staticmethod
    async def _curriculum_subject_response(
        db: AsyncSession,
        row: CurriculumSubject,
    ) -> CurriculumSubjectResponse:
        subject = (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == row.tenant_id,
                    Subject.id == row.subject_id,
                )
            )
        ).scalar_one_or_none()
        if subject is None:
            raise NotFoundException("Subject not found.")
        return CurriculumSubjectResponse(
            id=row.id,
            tenant_id=row.tenant_id,
            curriculum_id=row.curriculum_id,
            subject_id=row.subject_id,
            subject_name=subject.name,
            subject_code=subject.code,
            is_elective=row.is_elective,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    async def _curriculum_subject_context(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        *,
        lock: bool = False,
        require_active_level: bool = False,
        require_active_subject: bool = False,
    ) -> tuple[CurriculumSubject, Curriculum, Subject]:
        context = await CurriculumSubjectRepository.get_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=lock,
        )
        if context is None:
            raise NotFoundException("Curriculum subject not found.")
        row, curriculum = context
        level = await AcademicLevelRepository.get_by_id(
            db,
            tenant_id,
            curriculum.academic_level_id,
        )
        if level is None:
            raise NotFoundException("Academic level not found.")
        if require_active_level and level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException(
                "Academic level must be active before curriculum membership is changed."
            )
        subject = (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.id == row.subject_id,
                )
            )
        ).scalar_one_or_none()
        if subject is None:
            raise NotFoundException("Subject not found.")
        if require_active_subject and (
            not subject.is_active or subject.archived_at is not None
        ):
            raise ConflictException(
                "Subject must be active before this curriculum membership can be activated."
            )
        return row, curriculum, subject

    @staticmethod
    def _live_curriculum_subject_dependencies(
        dependencies: dict[str, int],
    ) -> dict[str, int]:
        keys = ("offerings_live", "teacher_assignments_active", "results_live")
        return {
            key: dependencies.get(key, 0)
            for key in keys
            if dependencies.get(key, 0) > 0
        }

    @staticmethod
    def _has_any_curriculum_subject_usage(dependencies: dict[str, int]) -> bool:
        keys = (
            "offerings_total",
            "teacher_assignments_total",
            "teacher_assignment_audits_total",
            "results_total",
        )
        return any(dependencies.get(key, 0) > 0 for key in keys)

    @staticmethod
    def _elective_semantic_blockers(dependencies: dict[str, int]) -> dict[str, int]:
        """Lock elective meaning once the membership reaches published/history use."""

        keys = ("offerings_published", "results_total")
        return {
            key: dependencies.get(key, 0)
            for key in keys
            if dependencies.get(key, 0) > 0
        }

    @staticmethod
    async def _term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicTerm:
        query = select(AcademicTerm).where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.id == term_id,
        )
        if lock:
            query = query.with_for_update()
        term = (await db.execute(query)).scalar_one_or_none()
        if term is None:
            raise NotFoundException("Academic term not found.")
        return term

    @staticmethod
    async def _ensure_department_capability(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
    ):
        level = await AcademicLevelRepository.get_by_id(
            db,
            tenant_id,
            academic_level_id,
            lock=True,
        )
        tenant = await TenantRepository.get_by_id(db, tenant_id)
        if level is None:
            raise NotFoundException("Academic level not found.")
        if level.status != AcademicLevelStatus.ACTIVE:
            raise ConflictException(
                "Academic level must be active before specialization is configured."
            )
        if tenant is None or tenant.institution_type is None:
            raise ConflictException(
                "Institution type is required before department specialization can be configured."
            )
        if not category_supports_departments(
            tenant.institution_type,
            level.category,
        ):
            raise ConflictException(
                "Departments are not supported by this academic level category."
            )
        return level

    @staticmethod
    def _specialization_required_for_term(level, term: AcademicTerm) -> bool:
        threshold = level.specialization_required_from_term_position
        if threshold is None:
            return False
        position = AcademicCurriculumService._TERM_POSITIONS.get(term.name)
        return position is not None and position >= threshold

    @staticmethod
    async def _specialized_offering_subject_ids(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        term_id: uuid.UUID,
        department_id: uuid.UUID | None,
    ) -> set[uuid.UUID]:
        """Return currently visible specialized memberships for one department and term."""

        if department_id is None:
            return set()
        rows = (
            await db.execute(
                select(CurriculumOffering.curriculum_subject_id)
                .join(
                    CurriculumSubject,
                    CurriculumSubject.id == CurriculumOffering.curriculum_subject_id,
                )
                .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
                .join(Subject, Subject.id == CurriculumSubject.subject_id)
                .where(
                    CurriculumOffering.tenant_id == tenant_id,
                    CurriculumOffering.academic_term_id == term_id,
                    CurriculumOffering.department_id == department_id,
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.is_active.is_(True),
                    Curriculum.tenant_id == tenant_id,
                    Curriculum.academic_level_id == academic_level_id,
                    Subject.tenant_id == tenant_id,
                    Subject.is_active.is_(True),
                    Subject.archived_at.is_(None),
                )
            )
        ).scalars()
        return set(rows)

    @staticmethod
    async def _class_department_change_dependencies(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        term: AcademicTerm,
        affected_curriculum_subject_ids: set[uuid.UUID],
    ) -> dict[str, int]:
        if not affected_curriculum_subject_ids:
            return {"results": 0, "teacher_assignments": 0}

        results = int(
            (
                await db.execute(
                    select(func.count(StudentSubjectResult.id)).where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.class_id == class_id,
                        StudentSubjectResult.academic_term_id == term.id,
                        StudentSubjectResult.curriculum_subject_id.in_(
                            affected_curriculum_subject_ids
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )

        assignment_query = select(func.count(TeacherAssignment.id)).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.curriculum_subject_id.in_(affected_curriculum_subject_ids),
        )
        if term.start_date is not None:
            assignment_query = assignment_query.where(
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= term.start_date,
                )
            )
        if term.end_date is not None:
            assignment_query = assignment_query.where(
                TeacherAssignment.effective_from <= term.end_date
            )
        if term.start_date is None and term.end_date is None:
            assignment_query = assignment_query.where(TeacherAssignment.is_active.is_(True))

        teacher_assignments = int((await db.execute(assignment_query)).scalar_one() or 0)
        return {
            "results": results,
            "teacher_assignments": teacher_assignments,
        }

    @staticmethod
    async def _ensure_class_department_change_mutable(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        classroom,
        term: AcademicTerm,
        old_department_id: uuid.UUID | None,
        new_department_id: uuid.UUID | None,
    ) -> set[uuid.UUID]:
        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException(
                "Class specialization cannot be changed after term closing begins."
            )
        if term.status != AcademicTermStatus.OPEN or old_department_id == new_department_id:
            return set()

        old_subject_ids = await AcademicCurriculumService._specialized_offering_subject_ids(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
            term_id=term.id,
            department_id=old_department_id,
        )
        new_subject_ids = await AcademicCurriculumService._specialized_offering_subject_ids(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
            term_id=term.id,
            department_id=new_department_id,
        )
        affected_subject_ids = old_subject_ids.symmetric_difference(new_subject_ids)
        dependencies = await AcademicCurriculumService._class_department_change_dependencies(
            db,
            tenant_id=tenant_id,
            class_id=classroom.id,
            term=term,
            affected_curriculum_subject_ids=affected_subject_ids,
        )
        blockers = {key: value for key, value in dependencies.items() if value > 0}
        if blockers:
            raise ConflictException(
                "Class specialization cannot change because affected specialized subjects are already in operational use.",
                payload={
                    "dependency_counts": blockers,
                    "affected_curriculum_subject_ids": [
                        str(subject_id) for subject_id in sorted(affected_subject_ids, key=str)
                    ],
                },
            )
        return affected_subject_ids

    @staticmethod
    def _record_open_term_specialization_audit(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        old_department_id: uuid.UUID | None,
        new_department_id: uuid.UUID | None,
        admin_id: uuid.UUID,
        affected_subject_ids: set[uuid.UUID],
    ) -> None:
        action = (
            "department_assigned"
            if old_department_id is None and new_department_id is not None
            else "department_cleared"
            if new_department_id is None
            else "department_changed"
        )
        db.add(
            AcademicLifecycleAudit(
                tenant_id=tenant_id,
                entity_type="specialization",
                entity_id=assignment_id,
                action=action,
                previous_status=None,
                new_status=None,
                acting_admin_id=admin_id,
                reason="Open-term class specialization correction.",
                metadata_json={
                    "class_id": str(class_id),
                    "academic_term_id": str(term_id),
                    "previous_department_id": (
                        str(old_department_id) if old_department_id is not None else None
                    ),
                    "new_department_id": (
                        str(new_department_id) if new_department_id is not None else None
                    ),
                    "affected_curriculum_subject_ids": [
                        str(subject_id) for subject_id in sorted(affected_subject_ids, key=str)
                    ],
                },
            )
        )

    @staticmethod
    async def _offering_open_term_dependencies(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        term: AcademicTerm,
        curriculum_subject_id: uuid.UUID,
        department_id: uuid.UUID | None,
    ) -> dict[str, int]:
        """Count operational evidence that depends on one offering scope in an open term."""

        result_query = select(func.count(StudentSubjectResult.id)).where(
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.academic_term_id == term.id,
            StudentSubjectResult.curriculum_subject_id == curriculum_subject_id,
        )
        assignment_query = select(func.count(TeacherAssignment.id)).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.curriculum_subject_id == curriculum_subject_id,
        )

        if department_id is not None:
            result_query = result_query.join(
                ClassTermDepartmentAssignment,
                and_(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == StudentSubjectResult.class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term.id,
                    ClassTermDepartmentAssignment.department_id == department_id,
                ),
            )
            assignment_query = assignment_query.join(
                ClassTermDepartmentAssignment,
                and_(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == TeacherAssignment.class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term.id,
                    ClassTermDepartmentAssignment.department_id == department_id,
                ),
            )

        if term.start_date is not None:
            assignment_query = assignment_query.where(
                or_(
                    TeacherAssignment.effective_to.is_(None),
                    TeacherAssignment.effective_to >= term.start_date,
                )
            )
        if term.end_date is not None:
            assignment_query = assignment_query.where(
                TeacherAssignment.effective_from <= term.end_date
            )

        results = int((await db.execute(result_query)).scalar_one() or 0)
        teacher_assignments = int((await db.execute(assignment_query)).scalar_one() or 0)
        return {
            "results": results,
            "teacher_assignments": teacher_assignments,
        }

    @staticmethod
    async def _ensure_offering_change_mutable(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        term: AcademicTerm,
        curriculum_subject_id: uuid.UUID,
        department_id: uuid.UUID | None,
        removing: bool,
    ) -> None:
        """Protect a term offering without over-freezing legitimate open-term corrections."""

        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException(
                "Curriculum offerings cannot be changed after term closing begins."
            )
        if not removing or term.status != AcademicTermStatus.OPEN:
            return

        dependencies = await AcademicCurriculumService._offering_open_term_dependencies(
            db,
            tenant_id=tenant_id,
            term=term,
            curriculum_subject_id=curriculum_subject_id,
            department_id=department_id,
        )
        blockers = {key: value for key, value in dependencies.items() if value > 0}
        if blockers:
            raise ConflictException(
                "This curriculum offering is already in operational use and cannot be removed from the open term.",
                payload={"dependency_counts": blockers},
            )

    @staticmethod
    async def get_curriculum(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
    ) -> CurriculumResponse:
        curriculum = await AcademicCurriculumService._curriculum(db, tenant_id, level_id)
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
        rows = list(
            (
                await db.execute(
                    select(CurriculumSubject, Subject)
                    .join(Subject, Subject.id == CurriculumSubject.subject_id)
                    .where(
                        CurriculumSubject.tenant_id == tenant_id,
                        CurriculumSubject.curriculum_id == curriculum.id,
                    )
                    .order_by(Subject.name)
                )
            ).all()
        )
        return CurriculumResponse(
            id=curriculum.id,
            tenant_id=tenant_id,
            academic_level_id=level_id,
            level_name=level.name if level else None,
            subjects=[
                CurriculumSubjectResponse(
                    id=item.id,
                    tenant_id=item.tenant_id,
                    curriculum_id=item.curriculum_id,
                    subject_id=item.subject_id,
                    subject_name=subject.name,
                    subject_code=subject.code,
                    is_elective=item.is_elective,
                    is_active=item.is_active,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item, subject in rows
            ],
        )

    @staticmethod
    async def add_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
        payload: CurriculumSubjectCreate,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum = await AcademicCurriculumService._curriculum(
            db,
            tenant_id,
            level_id,
            require_active_level=True,
        )
        subject = (
            await db.execute(
                select(Subject).where(
                    Subject.tenant_id == tenant_id,
                    Subject.id == payload.subject_id,
                    Subject.is_active.is_(True),
                    Subject.archived_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if subject is None:
            raise NotFoundException("Active subject not found.")
        existing = await CurriculumSubjectRepository.get_for_curriculum_subject(
            db,
            tenant_id,
            curriculum.id,
            subject.id,
        )
        if existing:
            raise ConflictException("This subject is already in the level curriculum.")
        row = CurriculumSubject(
            tenant_id=tenant_id,
            curriculum_id=curriculum.id,
            subject_id=subject.id,
            is_elective=payload.is_elective,
            is_active=True,
        )
        try:
            await CurriculumSubjectRepository.add(db, row)
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("This subject is already in the level curriculum.") from exc
        return await AcademicCurriculumService._curriculum_subject_response(db, row)

    @staticmethod
    async def update_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        payload: CurriculumSubjectUpdate,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row, _curriculum, _subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
            require_active_level=True,
        )
        if not row.is_active:
            raise ConflictException(
                "Inactive curriculum subjects cannot be edited. Activate the membership first."
            )
        if payload.is_elective == row.is_elective:
            return await AcademicCurriculumService._curriculum_subject_response(db, row)

        dependencies = await CurriculumSubjectRepository.count_dependencies(
            db,
            tenant_id,
            row.id,
        )
        blockers = AcademicCurriculumService._elective_semantic_blockers(dependencies)
        if blockers:
            raise ConflictException(
                "Curriculum subject elective meaning is locked after operational use.",
                payload={"dependency_counts": blockers},
            )
        row.is_elective = payload.is_elective
        await CurriculumSubjectRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return await AcademicCurriculumService._curriculum_subject_response(db, row)

    @staticmethod
    async def activate_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row, _curriculum, _subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
            require_active_level=True,
            require_active_subject=True,
        )
        if row.is_active:
            return await AcademicCurriculumService._curriculum_subject_response(db, row)
        row.is_active = True
        await CurriculumSubjectRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return await AcademicCurriculumService._curriculum_subject_response(db, row)

    @staticmethod
    async def deactivate_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row, _curriculum, _subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
            require_active_level=True,
        )
        if not row.is_active:
            return await AcademicCurriculumService._curriculum_subject_response(db, row)
        dependencies = await CurriculumSubjectRepository.count_dependencies(
            db,
            tenant_id,
            row.id,
        )
        blockers = AcademicCurriculumService._live_curriculum_subject_dependencies(dependencies)
        if blockers:
            raise ConflictException(
                "This curriculum subject still has live academic dependencies and cannot be deactivated.",
                payload={"dependency_counts": blockers},
            )
        row.is_active = False
        await CurriculumSubjectRepository.save(db, row)
        await db.commit()
        await db.refresh(row)
        return await AcademicCurriculumService._curriculum_subject_response(db, row)

    @staticmethod
    async def hard_delete_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> CurriculumSubjectResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row, _curriculum, _subject = await AcademicCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
        )
        dependencies = await CurriculumSubjectRepository.count_dependencies(
            db,
            tenant_id,
            row.id,
        )
        if AcademicCurriculumService._has_any_curriculum_subject_usage(dependencies):
            counts = {
                key: value
                for key, value in dependencies.items()
                if key.endswith("_total") and value > 0
            }
            raise ConflictException(
                "This curriculum subject has already been used and cannot be permanently deleted.",
                payload={"dependency_counts": counts},
            )
        response = await AcademicCurriculumService._curriculum_subject_response(db, row)
        await CurriculumSubjectRepository.delete(db, row)
        await db.commit()
        return response

    @staticmethod
    async def add_offering(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        payload: CurriculumOfferingCreate,
    ) -> CurriculumOfferingResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum_subject, curriculum, _subject = (
            await AcademicCurriculumService._curriculum_subject_context(
                db,
                tenant_id,
                curriculum_subject_id,
                lock=True,
                require_active_level=True,
                require_active_subject=True,
            )
        )
        if not curriculum_subject.is_active:
            raise ConflictException(
                "Curriculum subject must be active before an offering can be configured."
            )

        term = await AcademicCurriculumService._term(
            db, tenant_id, payload.academic_term_id, lock=True
        )
        await AcademicCurriculumService._ensure_offering_change_mutable(
            db,
            tenant_id=tenant_id,
            term=term,
            curriculum_subject_id=curriculum_subject.id,
            department_id=payload.department_id,
            removing=False,
        )

        if payload.department_id is not None:
            await AcademicCurriculumService._ensure_department_capability(
                db,
                tenant_id=tenant_id,
                academic_level_id=curriculum.academic_level_id,
            )
            department = await DepartmentRepository.get_by_id(
                db, tenant_id, payload.department_id, lock=True
            )
            if (
                department is None
                or not department.is_active
                or department.archived_at is not None
                or department.academic_level_id != curriculum.academic_level_id
            ):
                raise ConflictException(
                    "Department must be active and belong to the curriculum's academic level."
                )

        existing = list(
            (
                await db.execute(
                    select(CurriculumOffering).where(
                        CurriculumOffering.tenant_id == tenant_id,
                        CurriculumOffering.curriculum_subject_id == curriculum_subject.id,
                        CurriculumOffering.academic_term_id == term.id,
                    )
                )
            ).scalars()
        )
        if payload.department_id is None:
            if existing:
                raise ConflictException(
                    "Remove this subject's department-specific offerings before making it general for the term."
                )
        else:
            if any(row.department_id is None for row in existing):
                raise ConflictException(
                    "This subject is already general for the term and therefore already reaches every department."
                )
            if any(row.department_id == payload.department_id for row in existing):
                raise ConflictException(
                    "This subject is already offered to that department for the term."
                )

        row = CurriculumOffering(
            tenant_id=tenant_id,
            curriculum_subject_id=curriculum_subject.id,
            academic_term_id=term.id,
            department_id=payload.department_id,
        )
        try:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException(
                "This curriculum offering already exists for the selected scope."
            ) from exc
        return CurriculumOfferingResponse.model_validate(row)

    @staticmethod
    async def list_offerings(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
    ) -> list[CurriculumOfferingResponse]:
        rows = list(
            (
                await db.execute(
                    select(CurriculumOffering)
                    .where(
                        CurriculumOffering.tenant_id == tenant_id,
                        CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
                    )
                    .order_by(CurriculumOffering.created_at)
                )
            ).scalars()
        )
        return [CurriculumOfferingResponse.model_validate(row) for row in rows]

    @staticmethod
    async def remove_offering(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        offering_id: uuid.UUID,
    ) -> None:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row = (
            await db.execute(
                select(CurriculumOffering).where(
                    CurriculumOffering.tenant_id == tenant_id,
                    CurriculumOffering.id == offering_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundException("Curriculum offering not found.")

        term = await AcademicCurriculumService._term(db, tenant_id, row.academic_term_id, lock=True)
        row = (
            await db.execute(
                select(CurriculumOffering)
                .where(
                    CurriculumOffering.tenant_id == tenant_id,
                    CurriculumOffering.id == offering_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundException("Curriculum offering not found.")

        await AcademicCurriculumService._ensure_offering_change_mutable(
            db,
            tenant_id=tenant_id,
            term=term,
            curriculum_subject_id=row.curriculum_subject_id,
            department_id=row.department_id,
            removing=True,
        )
        await db.delete(row)
        await db.commit()

    @staticmethod
    async def get_class_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> ClassTermDepartmentResponse | None:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        if classroom is None:
            raise NotFoundException("Class not found.")
        await AcademicCurriculumService._term(db, tenant_id, term_id)
        row = (
            await db.execute(
                select(ClassTermDepartmentAssignment).where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term_id,
                )
            )
        ).scalar_one_or_none()
        return ClassTermDepartmentResponse.model_validate(row) if row else None

    @staticmethod
    async def list_class_departments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> list[ClassTermDepartmentResponse]:
        await AcademicCurriculumService._term(db, tenant_id, term_id)
        rows = list(
            (
                await db.execute(
                    select(ClassTermDepartmentAssignment)
                    .where(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.academic_term_id == term_id,
                    )
                    .order_by(ClassTermDepartmentAssignment.class_id)
                )
            ).scalars()
        )
        return [ClassTermDepartmentResponse.model_validate(row) for row in rows]

    @staticmethod
    async def set_class_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        admin_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ClassTermDepartmentResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        term = await AcademicCurriculumService._term(db, tenant_id, term_id, lock=True)
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
        department = await DepartmentRepository.get_by_id(
            db, tenant_id, department_id, lock=True
        )
        if classroom is None or department is None:
            raise NotFoundException("Class or department not found.")
        if not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Class must be active before specialization is assigned.")
        if not department.is_active or department.archived_at is not None:
            raise ConflictException("Department must be active before it can be assigned.")
        if department.academic_level_id != classroom.academic_level_id:
            raise ConflictException("Department and class must belong to the same academic level.")
        await AcademicCurriculumService._ensure_department_capability(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
        )
        row = (
            await db.execute(
                select(ClassTermDepartmentAssignment)
                .where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        old_department_id = row.department_id if row is not None else None
        if old_department_id == department_id:
            return ClassTermDepartmentResponse.model_validate(row)

        affected_subject_ids = await AcademicCurriculumService._ensure_class_department_change_mutable(
            db,
            tenant_id=tenant_id,
            classroom=classroom,
            term=term,
            old_department_id=old_department_id,
            new_department_id=department_id,
        )
        if row is None:
            row = ClassTermDepartmentAssignment(
                tenant_id=tenant_id,
                class_id=class_id,
                academic_term_id=term_id,
                department_id=department_id,
                assigned_by_admin_id=admin_id,
            )
            db.add(row)
            await db.flush()
        else:
            row.department_id = department_id
            row.assigned_by_admin_id = admin_id
            await db.flush()

        if term.status == AcademicTermStatus.OPEN:
            AcademicCurriculumService._record_open_term_specialization_audit(
                db,
                tenant_id=tenant_id,
                assignment_id=row.id,
                class_id=class_id,
                term_id=term_id,
                old_department_id=old_department_id,
                new_department_id=department_id,
                admin_id=admin_id,
                affected_subject_ids=affected_subject_ids,
            )
        await db.commit()
        await db.refresh(row)
        return ClassTermDepartmentResponse.model_validate(row)

    @staticmethod
    async def clear_class_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        admin_id: uuid.UUID | None = None,
    ) -> None:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        term = await AcademicCurriculumService._term(db, tenant_id, term_id, lock=True)
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
        if classroom is None:
            raise NotFoundException("Class not found.")
        level = await AcademicCurriculumService._ensure_department_capability(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
        )
        row = (
            await db.execute(
                select(ClassTermDepartmentAssignment)
                .where(
                    ClassTermDepartmentAssignment.tenant_id == tenant_id,
                    ClassTermDepartmentAssignment.class_id == class_id,
                    ClassTermDepartmentAssignment.academic_term_id == term_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            return

        old_department_id = row.department_id
        affected_subject_ids = await AcademicCurriculumService._ensure_class_department_change_mutable(
            db,
            tenant_id=tenant_id,
            classroom=classroom,
            term=term,
            old_department_id=old_department_id,
            new_department_id=None,
        )
        if (
            term.status == AcademicTermStatus.OPEN
            and AcademicCurriculumService._specialization_required_for_term(level, term)
        ):
            raise ConflictException(
                "This academic level requires department specialization for this term, so the class assignment cannot be cleared."
            )
        if term.status == AcademicTermStatus.OPEN and admin_id is not None:
            AcademicCurriculumService._record_open_term_specialization_audit(
                db,
                tenant_id=tenant_id,
                assignment_id=row.id,
                class_id=class_id,
                term_id=term_id,
                old_department_id=old_department_id,
                new_department_id=None,
                admin_id=admin_id,
                affected_subject_ids=affected_subject_ids,
            )
        await db.delete(row)
        await db.commit()
