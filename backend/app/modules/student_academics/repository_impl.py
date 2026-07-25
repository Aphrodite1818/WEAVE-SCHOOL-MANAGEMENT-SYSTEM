"""Canonical repositories for academic setup, assignments, and results."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    StudentSubjectResult,
    TeacherAssignment,
)


class StudentAcademicRepository:
    @staticmethod
    async def _save(db: AsyncSession, entity):
        db.add(entity)
        await db.flush()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def create_academic_session(db: AsyncSession, academic_session: AcademicSession) -> AcademicSession:
        return await StudentAcademicRepository._save(db, academic_session)

    @staticmethod
    async def get_academic_session_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> AcademicSession | None:
        return (
            await db.execute(
                select(AcademicSession).where(
                    AcademicSession.tenant_id == tenant_id,
                    AcademicSession.id == academic_session_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_academic_session_by_name(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        name: str,
    ) -> AcademicSession | None:
        return (
            await db.execute(
                select(AcademicSession).where(
                    AcademicSession.tenant_id == tenant_id,
                    AcademicSession.name == name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_current_academic_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> AcademicSession | None:
        return (
            await db.execute(
                select(AcademicSession).where(
                    AcademicSession.tenant_id == tenant_id,
                    AcademicSession.is_current.is_(True),
                    AcademicSession.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_academic_sessions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicSession], int]:
        filters = [AcademicSession.tenant_id == tenant_id]
        total = (
            await db.execute(
                select(func.count()).select_from(AcademicSession).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(AcademicSession)
                .where(*filters)
                .order_by(
                    AcademicSession.is_current.desc(),
                    AcademicSession.created_at.desc(),
                )
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def save_academic_session(db: AsyncSession, academic_session: AcademicSession) -> AcademicSession:
        return await StudentAcademicRepository._save(db, academic_session)

    @staticmethod
    async def create_academic_term(db: AsyncSession, academic_term: AcademicTerm) -> AcademicTerm:
        return await StudentAcademicRepository._save(db, academic_term)

    @staticmethod
    async def get_term_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
    ) -> AcademicTerm | None:
        return (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.id == term_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_term_by_session_and_name(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        name,
    ) -> AcademicTerm | None:
        return (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.academic_session_id == academic_session_id,
                    AcademicTerm.name == name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_current_term(db: AsyncSession, tenant_id: uuid.UUID) -> AcademicTerm | None:
        return (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.is_current.is_(True),
                    AcademicTerm.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicTerm], int]:
        return await StudentAcademicRepository._list_terms(
            db,
            tenant_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def list_terms_by_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicTerm], int]:
        return await StudentAcademicRepository._list_terms(
            db,
            tenant_id,
            academic_session_id=academic_session_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def _list_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicTerm], int]:
        filters = [AcademicTerm.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(AcademicTerm.academic_session_id == academic_session_id)
        total = (
            await db.execute(
                select(func.count()).select_from(AcademicTerm).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(AcademicTerm)
                .where(*filters)
                .order_by(AcademicTerm.is_current.desc(), AcademicTerm.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def save_academic_term(db: AsyncSession, academic_term: AcademicTerm) -> AcademicTerm:
        return await StudentAcademicRepository._save(db, academic_term)

    @staticmethod
    async def create_grading_scale(db: AsyncSession, grading_scale: GradingScale) -> GradingScale:
        return await StudentAcademicRepository._save(db, grading_scale)

    @staticmethod
    async def get_grading_scale_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        grading_scale_id: uuid.UUID,
    ) -> GradingScale | None:
        return (
            await db.execute(
                select(GradingScale).where(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.id == grading_scale_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_grading_scale_by_grade(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        grade: str,
    ) -> GradingScale | None:
        return (
            await db.execute(
                select(GradingScale).where(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.grade == grade,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_grading_scales(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = False,
    ) -> tuple[list[GradingScale], int]:
        filters = [GradingScale.tenant_id == tenant_id]
        if active_only:
            filters.append(GradingScale.is_active.is_(True))
        total = (
            await db.execute(
                select(func.count()).select_from(GradingScale).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(GradingScale)
                .where(*filters)
                .order_by(GradingScale.min_score.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def find_grade_for_score(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        score: Decimal,
    ) -> GradingScale | None:
        return (
            await db.execute(
                select(GradingScale).where(
                    GradingScale.tenant_id == tenant_id,
                    GradingScale.is_active.is_(True),
                    GradingScale.min_score <= score,
                    GradingScale.max_score >= score,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def save_grading_scale(db: AsyncSession, grading_scale: GradingScale) -> GradingScale:
        return await StudentAcademicRepository._save(db, grading_scale)

    @staticmethod
    async def create_class_subject_teacher(
        db: AsyncSession,
        assignment: ClassSubjectTeacher,
    ) -> ClassSubjectTeacher:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def get_class_subject_teacher_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> ClassSubjectTeacher | None:
        return (
            await db.execute(
                select(ClassSubjectTeacher).where(
                    ClassSubjectTeacher.tenant_id == tenant_id,
                    ClassSubjectTeacher.id == assignment_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_class_subject_teacher_by_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> ClassSubjectTeacher | None:
        return (
            await db.execute(
                select(ClassSubjectTeacher).where(
                    ClassSubjectTeacher.tenant_id == tenant_id,
                    ClassSubjectTeacher.class_id == class_id,
                    ClassSubjectTeacher.subject_id == subject_id,
                )
            )
        ).scalar_one_or_none()

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
        filters = [ClassSubjectTeacher.tenant_id == tenant_id]
        if class_id is not None:
            filters.append(ClassSubjectTeacher.class_id == class_id)
        if subject_id is not None:
            filters.append(ClassSubjectTeacher.subject_id == subject_id)
        if teacher_id is not None:
            filters.append(ClassSubjectTeacher.teacher_membership_id == teacher_id)
        if active_only:
            filters.append(ClassSubjectTeacher.is_active.is_(True))
        total = (
            await db.execute(
                select(func.count()).select_from(ClassSubjectTeacher).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(ClassSubjectTeacher)
                .where(*filters)
                .order_by(ClassSubjectTeacher.is_active.desc(), ClassSubjectTeacher.sort_order.asc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def list_teacher_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[ClassSubjectTeacher]:
        rows, _ = await StudentAcademicRepository.list_class_subject_teachers(
            db,
            tenant_id,
            teacher_id=teacher_id,
            active_only=active_only,
            limit=500,
        )
        return rows

    @staticmethod
    async def list_class_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        active_only: bool = True,
    ) -> list[ClassSubjectTeacher]:
        rows, _ = await StudentAcademicRepository.list_class_subject_teachers(
            db,
            tenant_id,
            class_id=class_id,
            active_only=active_only,
            limit=500,
        )
        return rows

    @staticmethod
    async def save_class_subject_teacher(
        db: AsyncSession,
        assignment: ClassSubjectTeacher,
    ) -> ClassSubjectTeacher:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def upsert_result(db: AsyncSession, result: StudentSubjectResult) -> StudentSubjectResult:
        return await StudentAcademicRepository._save(db, result)

    @staticmethod
    async def get_result_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        result_id: uuid.UUID,
    ) -> StudentSubjectResult | None:
        return (
            await db.execute(
                select(StudentSubjectResult).where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.id == result_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_result_by_scope(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        class_subject_teacher_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> StudentSubjectResult | None:
        return (
            await db.execute(
                select(StudentSubjectResult).where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                    StudentSubjectResult.class_subject_teacher_id == class_subject_teacher_id,
                    StudentSubjectResult.academic_session_id == academic_session_id,
                    StudentSubjectResult.academic_term_id == academic_term_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_results(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        student_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        teacher_id: uuid.UUID | None = None,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        published_only: bool = False,
    ) -> tuple[list[StudentSubjectResult], int]:
        filters = [StudentSubjectResult.tenant_id == tenant_id]
        if student_id is not None:
            filters.append(StudentSubjectResult.student_id == student_id)
        if class_id is not None:
            filters.append(StudentSubjectResult.class_id == class_id)
        if teacher_id is not None:
            filters.append(StudentSubjectResult.teacher_membership_id == teacher_id)
        if academic_session_id is not None:
            filters.append(StudentSubjectResult.academic_session_id == academic_session_id)
        if academic_term_id is not None:
            filters.append(StudentSubjectResult.academic_term_id == academic_term_id)
        if published_only:
            filters.append(StudentSubjectResult.status == "submitted")
        total = (
            await db.execute(
                select(func.count()).select_from(StudentSubjectResult).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(StudentSubjectResult)
                .where(*filters)
                .order_by(StudentSubjectResult.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def create_class_subject(db: AsyncSession, class_subject: ClassSubject) -> ClassSubject:
        return await StudentAcademicRepository._save(db, class_subject)

    @staticmethod
    async def get_class_subject_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> ClassSubject | None:
        return (
            await db.execute(
                select(ClassSubject).where(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.id == class_subject_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_class_subject_by_class_and_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        subject_id: uuid.UUID,
    ) -> ClassSubject | None:
        return (
            await db.execute(
                select(ClassSubject).where(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.subject_id == subject_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_class_subjects(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        class_id: uuid.UUID | None = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ClassSubject], int]:
        filters = [ClassSubject.tenant_id == tenant_id]
        if class_id is not None:
            filters.append(ClassSubject.class_id == class_id)
        if active_only:
            filters.append(ClassSubject.is_active.is_(True))
        total = (
            await db.execute(
                select(func.count()).select_from(ClassSubject).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(ClassSubject)
                .where(*filters)
                .order_by(ClassSubject.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def save_class_subject(db: AsyncSession, class_subject: ClassSubject) -> ClassSubject:
        return await StudentAcademicRepository._save(db, class_subject)

    @staticmethod
    async def count_results_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> int:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if class_subject is None:
            return 0
        result = await db.execute(
            select(func.count())
            .select_from(StudentSubjectResult)
            .join(
                TeacherAssignment,
                TeacherAssignment.id == StudentSubjectResult.teacher_assignment_id,
                isouter=True,
            )
            .join(
                ClassSubjectTeacher,
                ClassSubjectTeacher.id == StudentSubjectResult.class_subject_teacher_id,
                isouter=True,
            )
            .where(
                StudentSubjectResult.tenant_id == tenant_id,
                or_(
                    TeacherAssignment.class_subject_id == class_subject_id,
                    and_(
                        ClassSubjectTeacher.class_id == class_subject.class_id,
                        ClassSubjectTeacher.subject_id == class_subject.subject_id,
                    ),
                ),
            )
        )
        return int(result.scalar_one())

    @staticmethod
    async def create_teacher_assignment(db: AsyncSession, assignment: TeacherAssignment) -> TeacherAssignment:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def get_teacher_assignment_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
    ) -> TeacherAssignment | None:
        return (
            await db.execute(
                select(TeacherAssignment).where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.id == assignment_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_active_teacher_assignment_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        exclude_id: uuid.UUID | None = None,
    ) -> TeacherAssignment | None:
        filters = [
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
            TeacherAssignment.is_active.is_(True),
        ]
        if exclude_id is not None:
            filters.append(TeacherAssignment.id != exclude_id)
        return (
            await db.execute(
                select(TeacherAssignment)
                .where(*filters)
                .order_by(TeacherAssignment.created_at.desc())
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_teacher_assignment_rows(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        class_subject_id: uuid.UUID | None = None,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TeacherAssignment], int]:
        filters = [TeacherAssignment.tenant_id == tenant_id]
        if teacher_id is not None:
            filters.append(TeacherAssignment.teacher_membership_id == teacher_id)
        if class_subject_id is not None:
            filters.append(TeacherAssignment.class_subject_id == class_subject_id)
        if class_id is not None:
            filters.append(
                TeacherAssignment.class_subject_id.in_(
                    select(ClassSubject.id).where(
                        ClassSubject.tenant_id == tenant_id,
                        ClassSubject.class_id == class_id,
                    )
                )
            )
        if active_only:
            filters.append(TeacherAssignment.is_active.is_(True))
        total = (
            await db.execute(
                select(func.count()).select_from(TeacherAssignment).where(*filters)
            )
        ).scalar_one()
        rows = (
            await db.execute(
                select(TeacherAssignment)
                .where(*filters)
                .order_by(TeacherAssignment.is_active.desc(), TeacherAssignment.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), int(total)

    @staticmethod
    async def save_teacher_assignment(db: AsyncSession, assignment: TeacherAssignment) -> TeacherAssignment:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def count_scores_for_teacher_assignment(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_assignment_id: uuid.UUID,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentSubjectResult)
                    .where(
                        StudentSubjectResult.tenant_id == tenant_id,
                        StudentSubjectResult.teacher_assignment_id == teacher_assignment_id,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def get_result_by_teacher_assignment_scope(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
        teacher_assignment_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        academic_term_id: uuid.UUID,
    ) -> StudentSubjectResult | None:
        return (
            await db.execute(
                select(StudentSubjectResult).where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                    StudentSubjectResult.teacher_assignment_id == teacher_assignment_id,
                    StudentSubjectResult.academic_session_id == academic_session_id,
                    StudentSubjectResult.academic_term_id == academic_term_id,
                )
            )
        ).scalar_one_or_none()
