"""Canonical repositories for academic setup, assignments, and results."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.classes.models import ClassRoom
from app.modules.report_cards.models import ReportCard, ReportCardStatus
from app.modules.subjects.models import Subject
from app.modules.student_academics.models import (
    AcademicLifecycleAudit,
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    ClassSubject,
    ClassSubjectTeacher,
    GradingScale,
    StudentProgressionRun,
    StudentSubjectResult,
    TeacherAssignment,
    TeacherAssignmentLifecycleAudit,
)
from app.modules.students.models import Student, StudentEnrollment
from app.modules.teachers.models import TeacherAccount, TeacherMembership

FINALIZED_RESULT_STATUSES = (AcademicResultStatus.LOCKED,)


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class StudentAcademicRepository:
    @staticmethod
    async def _save(db: AsyncSession, entity):
        db.add(entity)
        await db.flush()
        await db.refresh(entity)
        return entity

    @staticmethod
    async def create_academic_session(
        db: AsyncSession, academic_session: AcademicSession
    ) -> AcademicSession:
        return await StudentAcademicRepository._save(db, academic_session)

    @staticmethod
    async def get_academic_session_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicSession | None:
        query = select(AcademicSession).where(
            AcademicSession.tenant_id == tenant_id,
            AcademicSession.id == academic_session_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

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
                    AcademicSession.status == AcademicSessionStatus.OPEN,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_academic_sessions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        *,
        search: str | None = None,
        status: AcademicSessionStatus | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
    ) -> tuple[list[AcademicSession], int]:
        filters = [AcademicSession.tenant_id == tenant_id]
        if search:
            filters.append(
                AcademicSession.name.ilike(
                    f"%{escape_like(search.strip())}%", escape="\\"
                )
            )
        if status is not None:
            filters.append(AcademicSession.status == status)
        if is_current is not None:
            filters.append(AcademicSession.is_current.is_(is_current))
        if start_date_from is not None:
            filters.append(AcademicSession.start_date >= start_date_from)
        if start_date_to is not None:
            filters.append(AcademicSession.start_date <= start_date_to)
        total = (
            await db.execute(
                select(func.count()).select_from(AcademicSession).where(*filters)
            )
        ).scalar_one()
        rows = (
            (
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
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def save_academic_session(
        db: AsyncSession, academic_session: AcademicSession
    ) -> AcademicSession:
        return await StudentAcademicRepository._save(db, academic_session)

    @staticmethod
    async def create_academic_term(
        db: AsyncSession, academic_term: AcademicTerm
    ) -> AcademicTerm:
        return await StudentAcademicRepository._save(db, academic_term)

    @staticmethod
    async def get_term_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> AcademicTerm | None:
        query = select(AcademicTerm).where(
            AcademicTerm.tenant_id == tenant_id,
            AcademicTerm.id == term_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

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
    async def get_current_term(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> AcademicTerm | None:
        return (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.is_current.is_(True),
                    AcademicTerm.status == AcademicTermStatus.OPEN,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        statuses: set[AcademicTermStatus] | None = None,
        *,
        name: str | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        return await StudentAcademicRepository._list_terms(
            db,
            tenant_id,
            skip=skip,
            limit=limit,
            statuses=statuses,
            name=name,
            is_current=is_current,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )

    @staticmethod
    async def list_terms_by_session(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        statuses: set[AcademicTermStatus] | None = None,
        *,
        name: str | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
    ) -> tuple[list[AcademicTerm], int]:
        return await StudentAcademicRepository._list_terms(
            db,
            tenant_id,
            academic_session_id=academic_session_id,
            skip=skip,
            limit=limit,
            statuses=statuses,
            name=name,
            is_current=is_current,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
        )

    @staticmethod
    async def _list_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        statuses: set[AcademicTermStatus] | None = None,
        name: str | None = None,
        is_current: bool | None = None,
        start_date_from: date | None = None,
        start_date_to: date | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AcademicTerm], int]:
        filters = [
            AcademicTerm.tenant_id == tenant_id,
        ]

        if academic_session_id is not None:
            filters.append(AcademicTerm.academic_session_id == academic_session_id)

        if statuses is None:
            filters.append(AcademicTerm.status != AcademicTermStatus.CLOSED)
        elif statuses:
            filters.append(AcademicTerm.status.in_(statuses))
        if name is not None:
            filters.append(AcademicTerm.name == name)
        if is_current is not None:
            filters.append(AcademicTerm.is_current.is_(is_current))
        if start_date_from is not None:
            filters.append(AcademicTerm.start_date >= start_date_from)
        if start_date_to is not None:
            filters.append(AcademicTerm.start_date <= start_date_to)

        total = (
            await db.execute(
                select(func.count()).select_from(AcademicTerm).where(*filters)
            )
        ).scalar_one()

        rows = (
            (
                await db.execute(
                    select(AcademicTerm)
                    .where(*filters)
                    .order_by(
                        AcademicTerm.is_current.desc(),
                        AcademicTerm.created_at.desc(),
                    )
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

        return list(rows), int(total)

    @staticmethod
    async def save_academic_term(
        db: AsyncSession, academic_term: AcademicTerm
    ) -> AcademicTerm:
        return await StudentAcademicRepository._save(db, academic_term)

    @staticmethod
    async def count_academic_terms(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        statuses: set[AcademicTermStatus] | None = None,
    ) -> int:
        filters = [AcademicTerm.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(AcademicTerm.academic_session_id == academic_session_id)
        if statuses is not None:
            filters.append(AcademicTerm.status.in_(statuses))
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(AcademicTerm).where(*filters)
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_results(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        statuses: set[AcademicResultStatus] | None = None,
    ) -> int:
        filters = [StudentSubjectResult.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(
                StudentSubjectResult.academic_session_id == academic_session_id
            )
        if academic_term_id is not None:
            filters.append(StudentSubjectResult.academic_term_id == academic_term_id)
        if statuses is not None:
            filters.append(StudentSubjectResult.status.in_(statuses))
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentSubjectResult)
                    .where(*filters)
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_report_cards(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        statuses: set[ReportCardStatus] | None = None,
    ) -> int:
        filters = [ReportCard.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(ReportCard.academic_session_id == academic_session_id)
        if academic_term_id is not None:
            filters.append(ReportCard.academic_term_id == academic_term_id)
        if statuses is not None:
            filters.append(ReportCard.status.in_(statuses))
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(ReportCard).where(*filters)
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_enrollments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentEnrollment)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.academic_session_id == academic_session_id,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_progression_runs(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        academic_session_id: uuid.UUID | None = None,
        statuses: set | None = None,
    ) -> int:
        filters = [StudentProgressionRun.tenant_id == tenant_id]
        if academic_session_id is not None:
            filters.append(
                StudentProgressionRun.academic_session_id == academic_session_id
            )
        if statuses is not None:
            filters.append(StudentProgressionRun.status.in_(statuses))
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentProgressionRun)
                    .where(*filters)
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_inbound_next_sessions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_session_id: uuid.UUID,
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(AcademicSession)
                    .where(
                        AcademicSession.tenant_id == tenant_id,
                        AcademicSession.next_academic_session_id == academic_session_id,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def add_academic_lifecycle_audit(
        db: AsyncSession,
        audit: AcademicLifecycleAudit,
    ) -> AcademicLifecycleAudit:
        db.add(audit)
        await db.flush()
        return audit

    @staticmethod
    async def delete_academic_session(
        db: AsyncSession, session: AcademicSession
    ) -> None:
        await db.delete(session)

    @staticmethod
    async def delete_academic_term(db: AsyncSession, term: AcademicTerm) -> None:
        await db.delete(term)

    @staticmethod
    async def create_grading_scale(
        db: AsyncSession, grading_scale: GradingScale
    ) -> GradingScale:
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
            (
                await db.execute(
                    select(GradingScale)
                    .where(*filters)
                    .order_by(GradingScale.min_score.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
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
    async def save_grading_scale(
        db: AsyncSession, grading_scale: GradingScale
    ) -> GradingScale:
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
            (
                await db.execute(
                    select(ClassSubjectTeacher)
                    .where(*filters)
                    .order_by(
                        ClassSubjectTeacher.is_active.desc(),
                        ClassSubjectTeacher.sort_order.asc(),
                    )
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
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
    async def delete_class_subject_teacher(
        db: AsyncSession,
        assignment: ClassSubjectTeacher,
    ) -> None:
        await db.delete(assignment)
        await db.flush()

    @staticmethod
    async def upsert_result(
        db: AsyncSession, result: StudentSubjectResult
    ) -> StudentSubjectResult:
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
        *,
        lock: bool = False,
    ) -> StudentSubjectResult | None:
        query = select(StudentSubjectResult).where(
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.student_id == student_id,
            StudentSubjectResult.class_subject_teacher_id == class_subject_teacher_id,
            StudentSubjectResult.academic_session_id == academic_session_id,
            StudentSubjectResult.academic_term_id == academic_term_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

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
        subject_id: uuid.UUID | None = None,
        teacher_assignment_id: uuid.UUID | None = None,
        academic_session_id: uuid.UUID | None = None,
        academic_term_id: uuid.UUID | None = None,
        status: AcademicResultStatus | None = None,
        search: str | None = None,
        is_complete: bool | None = None,
        has_grade: bool | None = None,
        finalized_only: bool = False,
    ) -> tuple[list[StudentSubjectResult], int]:
        filters = [StudentSubjectResult.tenant_id == tenant_id]
        if student_id is not None:
            filters.append(StudentSubjectResult.student_id == student_id)
        if class_id is not None:
            filters.append(StudentSubjectResult.class_id == class_id)
        if teacher_id is not None:
            filters.append(StudentSubjectResult.teacher_membership_id == teacher_id)
        if subject_id is not None:
            filters.append(StudentSubjectResult.subject_id == subject_id)
        if teacher_assignment_id is not None:
            filters.append(
                StudentSubjectResult.teacher_assignment_id == teacher_assignment_id
            )
        if academic_session_id is not None:
            filters.append(
                StudentSubjectResult.academic_session_id == academic_session_id
            )
        if academic_term_id is not None:
            filters.append(StudentSubjectResult.academic_term_id == academic_term_id)
        if status is not None:
            filters.append(StudentSubjectResult.status == status)
        if finalized_only:
            filters.append(StudentSubjectResult.status.in_(FINALIZED_RESULT_STATUSES))
        search_term = search.strip() if search else ""
        if search_term:
            pattern = f"%{escape_like(search_term)}%"
            student_name = func.concat(
                func.coalesce(Student.first_name, ""),
                " ",
                func.coalesce(Student.last_name, ""),
            )
            filters.append(
                or_(
                    student_name.ilike(pattern, escape="\\"),
                    Student.admission_number.ilike(pattern, escape="\\"),
                    Subject.name.ilike(pattern, escape="\\"),
                    Subject.code.ilike(pattern, escape="\\"),
                )
            )
        if is_complete is not None:
            if is_complete:
                filters.append(
                    and_(
                        StudentSubjectResult.test_score.is_not(None),
                        StudentSubjectResult.assessment_score.is_not(None),
                        StudentSubjectResult.exam_score.is_not(None),
                        StudentSubjectResult.grade.is_not(None),
                    )
                )
            else:
                filters.append(
                    or_(
                        StudentSubjectResult.test_score.is_(None),
                        StudentSubjectResult.assessment_score.is_(None),
                        StudentSubjectResult.exam_score.is_(None),
                        StudentSubjectResult.grade.is_(None),
                    )
                )
        if has_grade is not None:
            if has_grade:
                filters.append(StudentSubjectResult.grade.is_not(None))
            else:
                filters.append(StudentSubjectResult.grade.is_(None))
        count_query = select(func.count()).select_from(StudentSubjectResult)
        rows_query = select(StudentSubjectResult)
        if search_term:
            count_query = count_query.join(
                Student, Student.id == StudentSubjectResult.student_id
            ).join(
                Subject,
                Subject.id == StudentSubjectResult.subject_id,
            )
            rows_query = rows_query.join(
                Student, Student.id == StudentSubjectResult.student_id
            ).join(
                Subject,
                Subject.id == StudentSubjectResult.subject_id,
            )
        total = (await db.execute(count_query.where(*filters))).scalar_one()
        rows = (
            (
                await db.execute(
                    rows_query.where(*filters)
                    .order_by(StudentSubjectResult.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def create_class_subject(
        db: AsyncSession, class_subject: ClassSubject
    ) -> ClassSubject:
        return await StudentAcademicRepository._save(db, class_subject)

    @staticmethod
    async def get_class_subject_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> ClassSubject | None:
        query = select(ClassSubject).where(
            ClassSubject.tenant_id == tenant_id,
            ClassSubject.id == class_subject_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

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
        include_archived: bool = False,
        lifecycle_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ClassSubject], int]:
        filters = [ClassSubject.tenant_id == tenant_id]
        if class_id is not None:
            filters.append(ClassSubject.class_id == class_id)
        if lifecycle_status == "active":
            filters.append(ClassSubject.is_active.is_(True))
            filters.append(ClassSubject.archived_at.is_(None))
        elif lifecycle_status == "inactive":
            filters.append(ClassSubject.is_active.is_(False))
            filters.append(ClassSubject.archived_at.is_(None))
        elif lifecycle_status == "archived":
            filters.append(ClassSubject.archived_at.is_not(None))
        if active_only:
            filters.append(ClassSubject.is_active.is_(True))
            filters.append(ClassSubject.archived_at.is_(None))
        if not include_archived and lifecycle_status != "archived":
            filters.append(ClassSubject.archived_at.is_(None))
        total = (
            await db.execute(
                select(func.count()).select_from(ClassSubject).where(*filters)
            )
        ).scalar_one()
        rows = (
            (
                await db.execute(
                    select(ClassSubject)
                    .where(*filters)
                    .order_by(ClassSubject.created_at.desc())
                    .offset(skip)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total)

    @staticmethod
    async def save_class_subject(
        db: AsyncSession, class_subject: ClassSubject
    ) -> ClassSubject:
        return await StudentAcademicRepository._save(db, class_subject)

    @staticmethod
    async def delete_class_subject(
        db: AsyncSession, class_subject: ClassSubject
    ) -> None:
        await db.delete(class_subject)
        await db.flush()

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
    async def count_teacher_assignments_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        *,
        active_only: bool = False,
    ) -> int:
        filters = [
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
        ]
        if active_only:
            filters.append(TeacherAssignment.is_active.is_(True))
        result = await db.execute(
            select(func.count()).select_from(TeacherAssignment).where(*filters)
        )
        return int(result.scalar_one())

    @staticmethod
    async def count_class_subject_teachers_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        *,
        active_only: bool = False,
    ) -> int:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if class_subject is None:
            return 0
        filters = [
            ClassSubjectTeacher.tenant_id == tenant_id,
            ClassSubjectTeacher.class_id == class_subject.class_id,
            ClassSubjectTeacher.subject_id == class_subject.subject_id,
        ]
        if active_only:
            filters.append(ClassSubjectTeacher.is_active.is_(True))
        result = await db.execute(
            select(func.count()).select_from(ClassSubjectTeacher).where(*filters)
        )
        return int(result.scalar_one())

    @staticmethod
    async def list_class_subject_teachers_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> list[ClassSubjectTeacher]:
        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if class_subject is None:
            return []
        rows = (
            (
                await db.execute(
                    select(ClassSubjectTeacher).where(
                        ClassSubjectTeacher.tenant_id == tenant_id,
                        ClassSubjectTeacher.class_id == class_subject.class_id,
                        ClassSubjectTeacher.subject_id == class_subject.subject_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    @staticmethod
    async def count_report_card_lines_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
    ) -> int:
        from app.modules.report_cards.models import ReportCard, ReportCardSubjectLine

        class_subject = await StudentAcademicRepository.get_class_subject_by_id(
            db,
            tenant_id,
            class_subject_id,
        )
        if class_subject is None:
            return 0
        result = await db.execute(
            select(func.count())
            .select_from(ReportCardSubjectLine)
            .join(ReportCard, ReportCard.id == ReportCardSubjectLine.report_card_id)
            .where(
                ReportCardSubjectLine.tenant_id == tenant_id,
                ReportCard.tenant_id == tenant_id,
                ReportCard.class_id == class_subject.class_id,
                ReportCardSubjectLine.subject_id == class_subject.subject_id,
            )
        )
        return int(result.scalar_one())

    @staticmethod
    async def create_teacher_assignment(
        db: AsyncSession, assignment: TeacherAssignment
    ) -> TeacherAssignment:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def get_teacher_assignment_by_id(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        query = select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.id == assignment_id,
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_active_teacher_assignment_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        exclude_id: uuid.UUID | None = None,
        lock: bool = False,
    ) -> TeacherAssignment | None:
        filters = [
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
            TeacherAssignment.is_active.is_(True),
            TeacherAssignment.effective_to.is_(None),
        ]
        if exclude_id is not None:
            filters.append(TeacherAssignment.id != exclude_id)
        query = (
            select(TeacherAssignment)
            .where(*filters)
            .order_by(TeacherAssignment.created_at.desc())
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_teacher_assignments_for_class_subject(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        *,
        lock: bool = False,
    ) -> list[TeacherAssignment]:
        query = (
            select(TeacherAssignment)
            .where(
                TeacherAssignment.tenant_id == tenant_id,
                TeacherAssignment.class_subject_id == class_subject_id,
            )
            .order_by(
                TeacherAssignment.effective_from.asc(),
                TeacherAssignment.created_at.asc(),
            )
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def get_later_teacher_assignments(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_subject_id: uuid.UUID,
        effective_from: date,
        *,
        exclude_id: uuid.UUID | None = None,
        lock: bool = False,
    ) -> list[TeacherAssignment]:
        filters = [
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.class_subject_id == class_subject_id,
            TeacherAssignment.effective_from > effective_from,
        ]
        if exclude_id is not None:
            filters.append(TeacherAssignment.id != exclude_id)
        query = (
            select(TeacherAssignment)
            .where(*filters)
            .order_by(TeacherAssignment.effective_from.asc())
        )
        if lock:
            query = query.with_for_update()
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def list_teacher_assignment_rows(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        teacher_id: uuid.UUID | None = None,
        class_id: uuid.UUID | None = None,
        class_subject_id: uuid.UUID | None = None,
        subject_id: uuid.UUID | None = None,
        status: str | None = None,
        effective_from_from: date | None = None,
        effective_from_to: date | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[dict], int]:
        filters = [
            TeacherAssignment.tenant_id == tenant_id,
            ClassSubject.tenant_id == tenant_id,
        ]
        if teacher_id is not None:
            filters.append(TeacherAssignment.teacher_membership_id == teacher_id)
        if class_subject_id is not None:
            filters.append(TeacherAssignment.class_subject_id == class_subject_id)
        if class_id is not None:
            filters.append(ClassSubject.class_id == class_id)
        if subject_id is not None:
            filters.append(ClassSubject.subject_id == subject_id)
        if status == "active":
            filters.append(TeacherAssignment.is_active.is_(True))
            filters.append(TeacherAssignment.effective_to.is_(None))
        elif status == "ended":
            filters.append(
                or_(
                    TeacherAssignment.is_active.is_(False),
                    TeacherAssignment.effective_to.is_not(None),
                )
            )
        if effective_from_from is not None:
            filters.append(TeacherAssignment.effective_from >= effective_from_from)
        if effective_from_to is not None:
            filters.append(TeacherAssignment.effective_from <= effective_from_to)
        if search:
            pattern = f"%{search.strip()}%"
            teacher_name = func.concat(
                func.coalesce(TeacherAccount.first_name, ""),
                " ",
                func.coalesce(TeacherAccount.last_name, ""),
            )
            filters.append(
                or_(
                    teacher_name.ilike(pattern),
                    TeacherMembership.staff_id.ilike(pattern),
                    ClassRoom.name.ilike(pattern),
                    ClassRoom.arm.ilike(pattern),
                    Subject.name.ilike(pattern),
                    Subject.code.ilike(pattern),
                )
            )
        base_query = (
            select(TeacherAssignment)
            .join(ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id)
            .join(ClassRoom, ClassRoom.id == ClassSubject.class_id, isouter=True)
            .join(Subject, Subject.id == ClassSubject.subject_id, isouter=True)
            .join(
                TeacherMembership,
                TeacherMembership.id == TeacherAssignment.teacher_membership_id,
                isouter=True,
            )
            .join(
                TeacherAccount,
                TeacherAccount.id == TeacherMembership.teacher_account_id,
                isouter=True,
            )
            .where(*filters)
        )
        total = (
            await db.execute(select(func.count()).select_from(base_query.subquery()))
        ).scalar_one()
        rows = (
            await db.execute(
                select(
                    TeacherAssignment,
                    ClassSubject.class_id.label("class_id"),
                    ClassSubject.subject_id.label("subject_id"),
                    ClassRoom.name.label("class_name"),
                    ClassRoom.arm.label("class_arm"),
                    Subject.name.label("subject_name"),
                    Subject.code.label("subject_code"),
                    TeacherMembership.staff_id.label("teacher_staff_id"),
                    TeacherAccount.first_name.label("teacher_first_name"),
                    TeacherAccount.last_name.label("teacher_last_name"),
                )
                .join(
                    ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id
                )
                .join(ClassRoom, ClassRoom.id == ClassSubject.class_id, isouter=True)
                .join(Subject, Subject.id == ClassSubject.subject_id, isouter=True)
                .join(
                    TeacherMembership,
                    TeacherMembership.id == TeacherAssignment.teacher_membership_id,
                    isouter=True,
                )
                .join(
                    TeacherAccount,
                    TeacherAccount.id == TeacherMembership.teacher_account_id,
                    isouter=True,
                )
                .where(*filters)
                .order_by(
                    TeacherAssignment.is_active.desc(),
                    TeacherAssignment.created_at.desc(),
                )
                .offset(skip)
                .limit(limit)
            )
        ).all()
        return [
            {
                "assignment": row[0],
                "class_id": row.class_id,
                "subject_id": row.subject_id,
                "class_name": row.class_name,
                "class_arm": row.class_arm,
                "subject_name": row.subject_name,
                "subject_code": row.subject_code,
                "teacher_staff_id": row.teacher_staff_id,
                "teacher_name": " ".join(
                    part
                    for part in [row.teacher_first_name, row.teacher_last_name]
                    if part
                )
                or None,
            }
            for row in rows
        ], int(total)

    @staticmethod
    async def save_teacher_assignment(
        db: AsyncSession, assignment: TeacherAssignment
    ) -> TeacherAssignment:
        return await StudentAcademicRepository._save(db, assignment)

    @staticmethod
    async def has_teacher_assignment_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_assignment_id: uuid.UUID,
    ) -> bool:
        result_count = (
            await StudentAcademicRepository.count_scores_for_teacher_assignment(
                db,
                tenant_id,
                teacher_assignment_id,
            )
        )
        return result_count > 0

    @staticmethod
    async def count_teacher_assignment_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_assignment_id: uuid.UUID,
    ) -> dict[str, int]:
        from app.modules.report_cards.models import ReportCardSubjectLine

        student_results = (
            await StudentAcademicRepository.count_scores_for_teacher_assignment(
                db,
                tenant_id,
                teacher_assignment_id,
            )
        )
        report_card_references = (
            await db.execute(
                select(func.count())
                .select_from(ReportCardSubjectLine)
                .join(
                    StudentSubjectResult,
                    StudentSubjectResult.id
                    == ReportCardSubjectLine.student_subject_result_id,
                )
                .where(
                    ReportCardSubjectLine.tenant_id == tenant_id,
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.teacher_assignment_id == teacher_assignment_id,
                )
            )
        ).scalar_one()
        return {
            "student_results": int(student_results),
            "report_card_references": int(report_card_references),
            "other_academic_records": 0,
        }

    @staticmethod
    async def delete_teacher_assignment(
        db: AsyncSession, assignment: TeacherAssignment
    ) -> None:
        await db.delete(assignment)
        await db.flush()

    @staticmethod
    async def create_teacher_assignment_lifecycle_audit(
        db: AsyncSession,
        audit: TeacherAssignmentLifecycleAudit,
    ) -> TeacherAssignmentLifecycleAudit:
        audit_table = (
            await db.execute(
                select(func.to_regclass("public.teacher_assignment_lifecycle_audits"))
            )
        ).scalar_one()
        if audit_table is None:
            return audit
        return await StudentAcademicRepository._save(db, audit)

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
                        StudentSubjectResult.teacher_assignment_id
                        == teacher_assignment_id,
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
