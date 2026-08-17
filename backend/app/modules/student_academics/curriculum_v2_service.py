"""Application service for level curricula and term-specific specialization."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.classes.models import ClassRoom, Department
from app.modules.classes.repository import AcademicLevelRepository, ClassRoomRepository, DepartmentRepository
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment, Curriculum, CurriculumOffering, CurriculumSubject
from app.modules.student_academics.curriculum_v2_schemas import ClassTermDepartmentResponse, CurriculumOfferingCreate, CurriculumOfferingResponse, CurriculumResponse, CurriculumSubjectCreate, CurriculumSubjectResponse, CurriculumSubjectUpdate
from app.modules.student_academics.models import AcademicTerm
from app.modules.subjects.models import Subject


class AcademicCurriculumService:
    @staticmethod
    async def _curriculum(db: AsyncSession, tenant_id: uuid.UUID, level_id: uuid.UUID, *, create: bool = True) -> Curriculum:
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
        if level is None: raise NotFoundException("Academic level not found.")
        row = (await db.execute(select(Curriculum).where(Curriculum.tenant_id == tenant_id, Curriculum.academic_level_id == level_id))).scalar_one_or_none()
        if row is None and create:
            row = Curriculum(tenant_id=tenant_id, academic_level_id=level_id); db.add(row); await db.flush()
        if row is None: raise NotFoundException("Curriculum not found.")
        return row

    @staticmethod
    async def get_curriculum(db: AsyncSession, tenant_id: uuid.UUID, level_id: uuid.UUID) -> CurriculumResponse:
        curriculum = await AcademicCurriculumService._curriculum(db, tenant_id, level_id)
        level = await AcademicLevelRepository.get_by_id(db, tenant_id, level_id)
        rows = list((await db.execute(select(CurriculumSubject, Subject).join(Subject, Subject.id == CurriculumSubject.subject_id).where(CurriculumSubject.tenant_id == tenant_id, CurriculumSubject.curriculum_id == curriculum.id).order_by(Subject.name))).all())
        return CurriculumResponse(id=curriculum.id, tenant_id=tenant_id, academic_level_id=level_id, level_name=level.name if level else None, subjects=[CurriculumSubjectResponse(id=item.id, tenant_id=item.tenant_id, curriculum_id=item.curriculum_id, subject_id=item.subject_id, subject_name=subject.name, subject_code=subject.code, is_elective=item.is_elective, is_active=item.is_active, created_at=item.created_at, updated_at=item.updated_at) for item, subject in rows])

    @staticmethod
    async def add_subject(db: AsyncSession, tenant_id: uuid.UUID, level_id: uuid.UUID, payload: CurriculumSubjectCreate) -> CurriculumSubjectResponse:
        curriculum = await AcademicCurriculumService._curriculum(db, tenant_id, level_id)
        subject = (await db.execute(select(Subject).where(Subject.tenant_id == tenant_id, Subject.id == payload.subject_id, Subject.is_active.is_(True)))).scalar_one_or_none()
        if subject is None: raise NotFoundException("Active subject not found.")
        existing = (await db.execute(select(CurriculumSubject).where(CurriculumSubject.tenant_id == tenant_id, CurriculumSubject.curriculum_id == curriculum.id, CurriculumSubject.subject_id == subject.id))).scalar_one_or_none()
        if existing: raise ConflictException("This subject is already in the level curriculum.")
        row = CurriculumSubject(tenant_id=tenant_id, curriculum_id=curriculum.id, subject_id=subject.id, is_elective=payload.is_elective, is_active=True)
        db.add(row); await db.commit(); await db.refresh(row)
        return CurriculumSubjectResponse(id=row.id, tenant_id=row.tenant_id, curriculum_id=row.curriculum_id, subject_id=row.subject_id, subject_name=subject.name, subject_code=subject.code, is_elective=row.is_elective, is_active=row.is_active, created_at=row.created_at, updated_at=row.updated_at)

    @staticmethod
    async def update_subject(db: AsyncSession, tenant_id: uuid.UUID, curriculum_subject_id: uuid.UUID, payload: CurriculumSubjectUpdate) -> CurriculumSubjectResponse:
        row = (await db.execute(select(CurriculumSubject).where(CurriculumSubject.tenant_id == tenant_id, CurriculumSubject.id == curriculum_subject_id).with_for_update())).scalar_one_or_none()
        if row is None: raise NotFoundException("Curriculum subject not found.")
        for key, value in payload.model_dump(exclude_unset=True).items(): setattr(row, key, value)
        subject = (await db.execute(select(Subject).where(Subject.id == row.subject_id))).scalar_one()
        await db.commit(); await db.refresh(row)
        return CurriculumSubjectResponse(id=row.id, tenant_id=row.tenant_id, curriculum_id=row.curriculum_id, subject_id=row.subject_id, subject_name=subject.name, subject_code=subject.code, is_elective=row.is_elective, is_active=row.is_active, created_at=row.created_at, updated_at=row.updated_at)

    @staticmethod
    async def add_offering(db: AsyncSession, tenant_id: uuid.UUID, curriculum_subject_id: uuid.UUID, payload: CurriculumOfferingCreate) -> CurriculumOfferingResponse:
        subject = (await db.execute(select(CurriculumSubject, Curriculum).join(Curriculum, Curriculum.id == CurriculumSubject.curriculum_id).where(CurriculumSubject.tenant_id == tenant_id, CurriculumSubject.id == curriculum_subject_id))).first()
        if subject is None: raise NotFoundException("Curriculum subject not found.")
        curriculum_subject, curriculum = subject
        term = (await db.execute(select(AcademicTerm).where(AcademicTerm.tenant_id == tenant_id, AcademicTerm.id == payload.academic_term_id))).scalar_one_or_none()
        if term is None: raise NotFoundException("Academic term not found.")
        if payload.department_id is not None:
            department = await DepartmentRepository.get_by_id(db, tenant_id, payload.department_id)
            if department is None or department.academic_level_id != curriculum.academic_level_id: raise ConflictException("Department must belong to the curriculum's academic level.")
        # One subject cannot be both general and department-specific in the same term.
        existing = list((await db.execute(select(CurriculumOffering).where(CurriculumOffering.tenant_id == tenant_id, CurriculumOffering.curriculum_subject_id == curriculum_subject_id, CurriculumOffering.academic_term_id == term.id))).scalars().all())
        if existing: raise ConflictException("This curriculum subject already has a term offering. Remove it before changing its scope.")
        row = CurriculumOffering(tenant_id=tenant_id, curriculum_subject_id=curriculum_subject_id, academic_term_id=term.id, department_id=payload.department_id)
        db.add(row); await db.commit(); await db.refresh(row); return CurriculumOfferingResponse.model_validate(row)

    @staticmethod
    async def list_offerings(db: AsyncSession, tenant_id: uuid.UUID, curriculum_subject_id: uuid.UUID):
        rows = list((await db.execute(select(CurriculumOffering).where(CurriculumOffering.tenant_id == tenant_id, CurriculumOffering.curriculum_subject_id == curriculum_subject_id).order_by(CurriculumOffering.created_at))).scalars().all())
        return [CurriculumOfferingResponse.model_validate(row) for row in rows]

    @staticmethod
    async def set_class_department(db: AsyncSession, tenant_id: uuid.UUID, admin_id: uuid.UUID, class_id: uuid.UUID, term_id: uuid.UUID, department_id: uuid.UUID) -> ClassTermDepartmentResponse:
        classroom = await ClassRoomRepository.get_by_id(db, tenant_id, class_id)
        term = (await db.execute(select(AcademicTerm).where(AcademicTerm.tenant_id == tenant_id, AcademicTerm.id == term_id))).scalar_one_or_none()
        department = await DepartmentRepository.get_by_id(db, tenant_id, department_id)
        if classroom is None or term is None or department is None: raise NotFoundException("Class, term or department not found.")
        if department.academic_level_id != classroom.academic_level_id: raise ConflictException("Department and class must belong to the same academic level.")
        row = (await db.execute(select(ClassTermDepartmentAssignment).where(ClassTermDepartmentAssignment.tenant_id == tenant_id, ClassTermDepartmentAssignment.class_id == class_id, ClassTermDepartmentAssignment.academic_term_id == term_id).with_for_update())).scalar_one_or_none()
        if row is None:
            row = ClassTermDepartmentAssignment(tenant_id=tenant_id, class_id=class_id, academic_term_id=term_id, department_id=department_id, assigned_by_admin_id=admin_id); db.add(row)
        else:
            row.department_id = department_id; row.assigned_by_admin_id = admin_id
        await db.commit(); await db.refresh(row); return ClassTermDepartmentResponse.model_validate(row)

    @staticmethod
    async def clear_class_department(db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, term_id: uuid.UUID) -> None:
        row = (await db.execute(select(ClassTermDepartmentAssignment).where(ClassTermDepartmentAssignment.tenant_id == tenant_id, ClassTermDepartmentAssignment.class_id == class_id, ClassTermDepartmentAssignment.academic_term_id == term_id).with_for_update())).scalar_one_or_none()
        if row is not None: await db.delete(row); await db.commit()
