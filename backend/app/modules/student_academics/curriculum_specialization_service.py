"""Level-department aware specialization operations for the curriculum service."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.department_repository import AcademicLevelDepartmentRepository
from app.modules.classes.models import AcademicLevelDepartment, Department
from app.modules.classes.repository import ClassRoomRepository
from app.modules.student_academics.curriculum_models import (
    ClassTermDepartmentAssignment,
    Curriculum,
    CurriculumOffering,
    CurriculumSubject,
)
from app.modules.student_academics.curriculum_v2_schemas import (
    ClassTermDepartmentResponse,
    CurriculumOfferingCreate,
    CurriculumOfferingResponse,
)
from app.modules.student_academics.curriculum_v2_service import AcademicCurriculumService as BaseCurriculumService
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    AcademicTermStatus,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.student_academics.write_guard import ensure_academic_write_window


class AcademicCurriculumService(BaseCurriculumService):
    """Canonical curriculum service with level-scoped specialization identities."""

    @staticmethod
    def _offering_response(row: CurriculumOffering, link: AcademicLevelDepartment | None = None):
        return CurriculumOfferingResponse(
            id=row.id,
            tenant_id=row.tenant_id,
            curriculum_subject_id=row.curriculum_subject_id,
            academic_term_id=row.academic_term_id,
            academic_level_department_id=row.academic_level_department_id,
            department_id=link.department_id if link else None,
            department_name=link.department.name if link and link.department else None,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _class_department_response(row: ClassTermDepartmentAssignment, link: AcademicLevelDepartment):
        return ClassTermDepartmentResponse(
            id=row.id,
            tenant_id=row.tenant_id,
            class_id=row.class_id,
            academic_term_id=row.academic_term_id,
            academic_level_department_id=row.academic_level_department_id,
            department_id=link.department_id,
            department_name=link.department.name if link.department else None,
            assigned_by_admin_id=row.assigned_by_admin_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    async def _active_level_department(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        link_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        lock: bool = False,
    ) -> AcademicLevelDepartment:
        link = await AcademicLevelDepartmentRepository.get_by_id(
            db, tenant_id, link_id, lock=lock
        )
        if link is None:
            raise NotFoundException("Academic level department not found")
        if link.academic_level_id != academic_level_id:
            raise ConflictException("The selected department is not enabled for this academic level")
        if (
            not link.is_active
            or link.archived_at is not None
            or not link.department.is_active
            or link.department.archived_at is not None
        ):
            raise ConflictException("The selected level department must be active")
        return link

    @staticmethod
    async def _specialized_offering_subject_ids(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        term_id: uuid.UUID,
        academic_level_department_id: uuid.UUID | None,
    ) -> set[uuid.UUID]:
        if academic_level_department_id is None:
            return set()
        rows = (
            await db.execute(
                select(CurriculumOffering.curriculum_subject_id)
                .join(CurriculumSubject, CurriculumSubject.id == CurriculumOffering.curriculum_subject_id)
                .join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id)
                .where(
                    CurriculumOffering.tenant_id == tenant_id,
                    CurriculumOffering.academic_term_id == term_id,
                    CurriculumOffering.academic_level_department_id == academic_level_department_id,
                    CurriculumSubject.tenant_id == tenant_id,
                    CurriculumSubject.is_active.is_(True),
                    Curriculum.tenant_id == tenant_id,
                    Curriculum.academic_level_id == academic_level_id,
                )
            )
        ).scalars()
        return set(rows)

    @staticmethod
    async def _change_dependencies(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        term,
        affected_ids: set[uuid.UUID],
    ) -> dict[str, int]:
        if not affected_ids:
            return {"results": 0, "teacher_assignments": 0}
        results = int((await db.execute(select(func.count(StudentSubjectResult.id)).where(
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.class_id == class_id,
            StudentSubjectResult.academic_term_id == term.id,
            StudentSubjectResult.curriculum_subject_id.in_(affected_ids),
        ))).scalar_one() or 0)
        query = select(func.count(TeacherAssignment.id)).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.curriculum_subject_id.in_(affected_ids),
        )
        if term.start_date is not None:
            query = query.where(or_(TeacherAssignment.effective_to.is_(None), TeacherAssignment.effective_to >= term.start_date))
        if term.end_date is not None:
            query = query.where(TeacherAssignment.effective_from <= term.end_date)
        assignments = int((await db.execute(query)).scalar_one() or 0)
        return {"results": results, "teacher_assignments": assignments}

    @staticmethod
    async def add_offering(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        curriculum_subject_id: uuid.UUID,
        payload: CurriculumOfferingCreate,
    ) -> CurriculumOfferingResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        curriculum_subject, curriculum, _subject = await BaseCurriculumService._curriculum_subject_context(
            db,
            tenant_id,
            curriculum_subject_id,
            lock=True,
            require_active_level=True,
            require_active_subject=True,
        )
        if not curriculum_subject.is_active:
            raise ConflictException("Curriculum subject must be active before an offering can be configured")
        term = await BaseCurriculumService._term(db, tenant_id, payload.academic_term_id, lock=True)
        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException("Curriculum offerings cannot be changed after term closing begins")

        link = None
        if payload.academic_level_department_id is not None:
            link = await AcademicCurriculumService._active_level_department(
                db,
                tenant_id=tenant_id,
                link_id=payload.academic_level_department_id,
                academic_level_id=curriculum.academic_level_id,
                lock=True,
            )

        existing = list((await db.execute(select(CurriculumOffering).where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.curriculum_subject_id == curriculum_subject.id,
            CurriculumOffering.academic_term_id == term.id,
        ))).scalars())
        if link is None:
            if existing:
                raise ConflictException("Remove department-specific offerings before making this subject general")
        else:
            if any(row.academic_level_department_id is None for row in existing):
                raise ConflictException("This subject is already general for the term")
            if any(row.academic_level_department_id == link.id for row in existing):
                raise ConflictException("This subject is already offered to that level department")

        row = CurriculumOffering(
            tenant_id=tenant_id,
            curriculum_subject_id=curriculum_subject.id,
            academic_term_id=term.id,
            academic_level_department_id=link.id if link else None,
        )
        try:
            db.add(row)
            await db.commit()
            await db.refresh(row)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictException("This curriculum offering already exists for the selected scope") from exc
        return AcademicCurriculumService._offering_response(row, link)

    @staticmethod
    async def list_offerings(
        db: AsyncSession, tenant_id: uuid.UUID, curriculum_subject_id: uuid.UUID
    ) -> list[CurriculumOfferingResponse]:
        rows = list((await db.execute(select(CurriculumOffering).where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.curriculum_subject_id == curriculum_subject_id,
        ).order_by(CurriculumOffering.created_at))).scalars())
        responses = []
        for row in rows:
            link = None
            if row.academic_level_department_id is not None:
                link = await AcademicLevelDepartmentRepository.get_by_id(
                    db, tenant_id, row.academic_level_department_id
                )
            responses.append(AcademicCurriculumService._offering_response(row, link))
        return responses

    @staticmethod
    async def remove_offering(
        db: AsyncSession, tenant_id: uuid.UUID, offering_id: uuid.UUID
    ) -> None:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        row = (await db.execute(select(CurriculumOffering).where(
            CurriculumOffering.tenant_id == tenant_id,
            CurriculumOffering.id == offering_id,
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            raise NotFoundException("Curriculum offering not found")
        term = await BaseCurriculumService._term(db, tenant_id, row.academic_term_id, lock=True)
        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException("Curriculum offerings cannot be changed after term closing begins")
        if term.status == AcademicTermStatus.OPEN:
            result_query = select(func.count(StudentSubjectResult.id)).where(
                StudentSubjectResult.tenant_id == tenant_id,
                StudentSubjectResult.academic_term_id == term.id,
                StudentSubjectResult.curriculum_subject_id == row.curriculum_subject_id,
            )
            assignment_query = select(func.count(TeacherAssignment.id)).where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.curriculum_subject_id == row.curriculum_subject_id,
            )
            if row.academic_level_department_id is not None:
                result_query = result_query.join(
                    ClassTermDepartmentAssignment,
                    and_(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.class_id == StudentSubjectResult.class_id,
                        ClassTermDepartmentAssignment.academic_term_id == term.id,
                        ClassTermDepartmentAssignment.academic_level_department_id == row.academic_level_department_id,
                    ),
                )
                assignment_query = assignment_query.join(
                    ClassTermDepartmentAssignment,
                    and_(
                        ClassTermDepartmentAssignment.tenant_id == tenant_id,
                        ClassTermDepartmentAssignment.class_id == TeacherAssignment.class_id,
                        ClassTermDepartmentAssignment.academic_term_id == term.id,
                        ClassTermDepartmentAssignment.academic_level_department_id == row.academic_level_department_id,
                    ),
                )
            blockers = {
                "results": int((await db.execute(result_query)).scalar_one() or 0),
                "teacher_assignments": int((await db.execute(assignment_query)).scalar_one() or 0),
            }
            blockers = {k: v for k, v in blockers.items() if v > 0}
            if blockers:
                raise ConflictException(
                    "This curriculum offering is already in operational use and cannot be removed",
                    payload={"dependency_counts": blockers},
                )
        await db.delete(row)
        await db.commit()

    @staticmethod
    async def get_class_department(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, term_id: uuid.UUID
    ) -> ClassTermDepartmentResponse | None:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        if classroom is None:
            raise NotFoundException("Class not found")
        await BaseCurriculumService._term(db, tenant_id, term_id)
        row = (await db.execute(select(ClassTermDepartmentAssignment).where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.class_id == class_id,
            ClassTermDepartmentAssignment.academic_term_id == term_id,
        ))).scalar_one_or_none()
        if row is None:
            return None
        link = await AcademicLevelDepartmentRepository.get_by_id(
            db, tenant_id, row.academic_level_department_id
        )
        if link is None:
            raise ConflictException("Class specialization references a missing level department")
        return AcademicCurriculumService._class_department_response(row, link)

    @staticmethod
    async def list_class_departments(
        db: AsyncSession, tenant_id: uuid.UUID, term_id: uuid.UUID
    ) -> list[ClassTermDepartmentResponse]:
        await BaseCurriculumService._term(db, tenant_id, term_id)
        rows = list((await db.execute(select(ClassTermDepartmentAssignment).where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.academic_term_id == term_id,
        ).order_by(ClassTermDepartmentAssignment.class_id))).scalars())
        result = []
        for row in rows:
            link = await AcademicLevelDepartmentRepository.get_by_id(
                db, tenant_id, row.academic_level_department_id
            )
            if link is None:
                raise ConflictException("Class specialization references a missing level department")
            result.append(AcademicCurriculumService._class_department_response(row, link))
        return result

    @staticmethod
    async def set_class_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        admin_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        academic_level_department_id: uuid.UUID,
    ) -> ClassTermDepartmentResponse:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        term = await BaseCurriculumService._term(db, tenant_id, term_id, lock=True)
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
        if classroom is None:
            raise NotFoundException("Class not found")
        if not classroom.is_active or classroom.archived_at is not None:
            raise ConflictException("Class must be active before specialization is assigned")
        link = await AcademicCurriculumService._active_level_department(
            db,
            tenant_id=tenant_id,
            link_id=academic_level_department_id,
            academic_level_id=classroom.academic_level_id,
            lock=True,
        )
        row = (await db.execute(select(ClassTermDepartmentAssignment).where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.class_id == class_id,
            ClassTermDepartmentAssignment.academic_term_id == term_id,
        ).with_for_update())).scalar_one_or_none()
        old_id = row.academic_level_department_id if row else None
        if old_id == link.id:
            return AcademicCurriculumService._class_department_response(row, link)
        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException("Class specialization cannot be changed after term closing begins")
        affected = set()
        if term.status == AcademicTermStatus.OPEN:
            old_subjects = await AcademicCurriculumService._specialized_offering_subject_ids(
                db,
                tenant_id=tenant_id,
                academic_level_id=classroom.academic_level_id,
                term_id=term.id,
                academic_level_department_id=old_id,
            )
            new_subjects = await AcademicCurriculumService._specialized_offering_subject_ids(
                db,
                tenant_id=tenant_id,
                academic_level_id=classroom.academic_level_id,
                term_id=term.id,
                academic_level_department_id=link.id,
            )
            affected = old_subjects.symmetric_difference(new_subjects)
            dependencies = await AcademicCurriculumService._change_dependencies(
                db,
                tenant_id=tenant_id,
                class_id=class_id,
                term=term,
                affected_ids=affected,
            )
            blockers = {k: v for k, v in dependencies.items() if v > 0}
            if blockers:
                raise ConflictException(
                    "Class specialization cannot change because affected subjects are already in operational use",
                    payload={"dependency_counts": blockers},
                )
        if row is None:
            row = ClassTermDepartmentAssignment(
                tenant_id=tenant_id,
                class_id=class_id,
                academic_term_id=term_id,
                academic_level_department_id=link.id,
                assigned_by_admin_id=admin_id,
            )
            db.add(row)
        else:
            row.academic_level_department_id = link.id
            row.assigned_by_admin_id = admin_id
        await db.flush()
        if term.status == AcademicTermStatus.OPEN:
            db.add(AcademicLifecycleAudit(
                tenant_id=tenant_id,
                entity_type="specialization",
                entity_id=row.id,
                action="department_assigned" if old_id is None else "department_changed",
                previous_status=None,
                new_status=None,
                acting_admin_id=admin_id,
                reason="Open-term class specialization correction.",
                metadata_json={
                    "class_id": str(class_id),
                    "academic_term_id": str(term_id),
                    "previous_academic_level_department_id": str(old_id) if old_id else None,
                    "new_academic_level_department_id": str(link.id),
                    "affected_curriculum_subject_ids": [str(value) for value in sorted(affected, key=str)],
                },
            ))
        await db.commit()
        await db.refresh(row)
        return AcademicCurriculumService._class_department_response(row, link)

    @staticmethod
    async def clear_class_department(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        term_id: uuid.UUID,
        admin_id: uuid.UUID | None = None,
    ) -> None:
        await ensure_academic_write_window(db, tenant_id=tenant_id)
        term = await BaseCurriculumService._term(db, tenant_id, term_id, lock=True)
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id, lock=True)
        if classroom is None:
            raise NotFoundException("Class not found")
        row = (await db.execute(select(ClassTermDepartmentAssignment).where(
            ClassTermDepartmentAssignment.tenant_id == tenant_id,
            ClassTermDepartmentAssignment.class_id == class_id,
            ClassTermDepartmentAssignment.academic_term_id == term_id,
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            return
        if term.status in {AcademicTermStatus.CLOSING, AcademicTermStatus.CLOSED}:
            raise ConflictException("Class specialization cannot be changed after term closing begins")
        if term.status == AcademicTermStatus.OPEN:
            subjects = await AcademicCurriculumService._specialized_offering_subject_ids(
                db,
                tenant_id=tenant_id,
                academic_level_id=classroom.academic_level_id,
                term_id=term.id,
                academic_level_department_id=row.academic_level_department_id,
            )
            dependencies = await AcademicCurriculumService._change_dependencies(
                db,
                tenant_id=tenant_id,
                class_id=class_id,
                term=term,
                affected_ids=subjects,
            )
            blockers = {k: v for k, v in dependencies.items() if v > 0}
            if blockers:
                raise ConflictException(
                    "Class specialization cannot be cleared because specialized subjects are already in use",
                    payload={"dependency_counts": blockers},
                )
            if admin_id is not None:
                db.add(AcademicLifecycleAudit(
                    tenant_id=tenant_id,
                    entity_type="specialization",
                    entity_id=row.id,
                    action="department_cleared",
                    previous_status=None,
                    new_status=None,
                    acting_admin_id=admin_id,
                    reason="Open-term class specialization correction.",
                    metadata_json={
                        "class_id": str(class_id),
                        "academic_term_id": str(term_id),
                        "previous_academic_level_department_id": str(row.academic_level_department_id),
                        "new_academic_level_department_id": None,
                    },
                ))
        # Preserve the existing level threshold invariant from the base service.
        level = await BaseCurriculumService._ensure_department_capability(
            db,
            tenant_id=tenant_id,
            academic_level_id=classroom.academic_level_id,
        )
        if term.status == AcademicTermStatus.OPEN and BaseCurriculumService._specialization_required_for_term(level, term):
            raise ConflictException(
                "This academic level requires department specialization for this term, so the class assignment cannot be cleared"
            )
        await db.delete(row)
        await db.commit()
