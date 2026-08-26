import uuid

from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom
from app.modules.parents.models import Parent, ParentAccount
from app.modules.search.schemas import TenantSearchResult
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.student_academics.curriculum_models import CurriculumSubject
from app.modules.students.models import Student
from app.modules.subjects.models import Subject
from app.modules.teachers.models import Teacher, TeacherAccount
from app.modules.superadmin.models import SuperAdmin
from app.tenant_management.models import Tenant


class TenantSearchService:
    @staticmethod
    def _name(*parts: str | None) -> str:
        return " ".join(part for part in parts if part).strip() or "Unnamed"

    @staticmethod
    def _matches(query: str, *values: object | None) -> bool:
        needle = query.strip().lower()
        if not needle:
            return False
        normalized_values = []
        for value in values:
            if value in (None, ""):
                continue
            normalized_values.append(getattr(value, "value", value))
        return any(needle in str(value).lower() for value in normalized_values)

    @staticmethod
    def _result(
        *,
        label: str,
        role: str,
        href: str,
        metadata: str | None = None,
        admission_number: str | None = None,
        staff_id: str | None = None,
        class_name: str | None = None,
        subject_name: str | None = None,
        email: str | None = None,
    ) -> TenantSearchResult:
        return TenantSearchResult(
            label=label,
            role=role,
            metadata=metadata,
            admission_number=admission_number,
            staff_id=staff_id,
            class_name=class_name,
            subject_name=subject_name,
            email=email,
            href=href,
        )

    @staticmethod
    async def search(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        limit: int = 20,
    ) -> list[TenantSearchResult]:
        return await TenantSearchService.search_tenant(db, tenant_id, query, limit)

    @staticmethod
    async def search_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        limit: int = 20,
    ) -> list[TenantSearchResult]:
        term = f"%{query.strip()}%"
        per_type_limit = max(1, min(limit, 50))
        items: list[TenantSearchResult] = []

        students = (
            await db.execute(
                select(Student, ClassRoom)
                .options(
                    selectinload(ClassRoom.academic_level),
                    selectinload(ClassRoom.arm_label_ref),
                )
                .outerjoin(ClassRoom, ClassRoom.id == Student.class_id)
                .outerjoin(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
                .outerjoin(ArmLabel, ArmLabel.id == ClassRoom.arm_label_id)
                .where(
                    Student.tenant_id == tenant_id,
                    or_(
                        Student.first_name.ilike(term),
                        Student.last_name.ilike(term),
                        Student.admission_number.ilike(term),
                        AcademicLevel.name.ilike(term),
                        ArmLabel.label.ilike(term),
                    ),
                )
                .limit(per_type_limit)
            )
        ).all()
        for student, classroom in students:
            class_label = classroom.display_name if classroom else None
            items.append(
                TenantSearchResult(
                    label=TenantSearchService._name(student.first_name, student.last_name),
                    role="student",
                    metadata=class_label,
                    admission_number=student.admission_number,
                    class_name=class_label,
                    href=f"/admin/students?admissionNumber={student.admission_number}",
                )
            )

        teachers = (
            (
                await db.execute(
                    select(Teacher)
                    .join(TeacherAccount, TeacherAccount.id == Teacher.teacher_account_id)
                    .options(selectinload(Teacher.teacher_account))
                    .where(
                        Teacher.tenant_id == tenant_id,
                        or_(
                            TeacherAccount.first_name.ilike(term),
                            TeacherAccount.last_name.ilike(term),
                            TeacherAccount.email.ilike(term),
                            Teacher.staff_id.ilike(term),
                        ),
                    )
                    .limit(per_type_limit)
                )
            )
            .scalars()
            .all()
        )
        for teacher in teachers:
            items.append(
                TenantSearchResult(
                    label=TenantSearchService._name(teacher.first_name, teacher.last_name),
                    role="teacher",
                    metadata=teacher.specialization,
                    staff_id=teacher.staff_id,
                    email=teacher.email,
                    href=f"/admin/teachers?staffId={teacher.staff_id or teacher.email}",
                )
            )

        parents = (
            (
                await db.execute(
                    select(Parent)
                    .join(ParentAccount, ParentAccount.id == Parent.parent_account_id)
                    .options(selectinload(Parent.parent_account))
                    .where(
                        Parent.tenant_id == tenant_id,
                        or_(
                            ParentAccount.first_name.ilike(term),
                            ParentAccount.last_name.ilike(term),
                            ParentAccount.email.ilike(term),
                        ),
                    )
                    .limit(per_type_limit)
                )
            )
            .scalars()
            .all()
        )
        for parent in parents:
            items.append(
                TenantSearchResult(
                    label=TenantSearchService._name(parent.first_name, parent.last_name),
                    role="parent",
                    metadata=parent.phone_number,
                    email=parent.email,
                    href=f"/admin/parents?email={parent.email}",
                )
            )

        classes = (
            (
                await db.execute(
                    select(ClassRoom)
                    .options(
                        selectinload(ClassRoom.academic_level),
                        selectinload(ClassRoom.arm_label_ref),
                    )
                    .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
                    .outerjoin(ArmLabel, ArmLabel.id == ClassRoom.arm_label_id)
                    .where(
                        ClassRoom.tenant_id == tenant_id,
                        or_(
                            AcademicLevel.name.ilike(term),
                            ArmLabel.label.ilike(term),
                        ),
                    )
                    .limit(per_type_limit)
                )
            )
            .scalars()
            .all()
        )
        for classroom in classes:
            label = classroom.display_name
            items.append(
                TenantSearchResult(
                    label=label,
                    role="class",
                    metadata=classroom.arm_label,
                    class_name=label,
                    href=f"/admin/classes?level={classroom.academic_level_name}&arm={classroom.arm_label or ''}",
                )
            )

        subjects = (
            (
                await db.execute(
                    select(Subject)
                    .where(
                        Subject.tenant_id == tenant_id,
                        or_(Subject.name.ilike(term), Subject.code.ilike(term)),
                    )
                    .limit(per_type_limit)
                )
            )
            .scalars()
            .all()
        )
        for subject in subjects:
            items.append(
                TenantSearchResult(
                    label=subject.name,
                    role="subject",
                    metadata=subject.code,
                    subject_name=subject.name,
                    href=f"/admin/subjects?code={subject.code or subject.name}",
                )
            )

        return items[:limit]

    @staticmethod
    async def search_teacher(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
        query: str,
        limit: int = 20,
    ) -> list[TenantSearchResult]:
        per_type_limit = max(1, min(limit, 10))
        items: list[TenantSearchResult] = []

        assignment_rows = (
            await db.execute(
                select(ClassRoom, Subject)
                .options(
                    selectinload(ClassRoom.academic_level),
                    selectinload(ClassRoom.arm_label_ref),
                )
                .join(
                    TeacherAssignment,
                    TeacherAssignment.class_id == ClassRoom.id,
                )
                .join(
                    CurriculumSubject,
                    CurriculumSubject.id == TeacherAssignment.curriculum_subject_id,
                )
                .join(Subject, Subject.id == CurriculumSubject.subject_id)
                .join(AcademicLevel, AcademicLevel.id == ClassRoom.academic_level_id)
                .outerjoin(ArmLabel, ArmLabel.id == ClassRoom.arm_label_id)
                .where(
                    ClassRoom.tenant_id == tenant_id,
                    TeacherAssignment.teacher_membership_id == teacher_id,
                    TeacherAssignment.is_active.is_(True),
                    CurriculumSubject.is_active.is_(True),
                )
                .order_by(AcademicLevel.name, ArmLabel.label, Subject.name)
            )
        ).all()

        class_rows: list[ClassRoom] = []
        subject_rows: list[Subject] = []
        seen_classes: set[uuid.UUID] = set()
        seen_subjects: set[uuid.UUID] = set()

        for classroom, subject in assignment_rows:
            if classroom.id not in seen_classes:
                class_rows.append(classroom)
                seen_classes.add(classroom.id)
            if subject.id not in seen_subjects:
                subject_rows.append(subject)
                seen_subjects.add(subject.id)

        for classroom in class_rows:
            label = classroom.display_name
            if TenantSearchService._matches(query, label):
                items.append(
                    TenantSearchService._result(
                        label=label,
                        role="class",
                        metadata=classroom.arm_label,
                        class_name=label,
                        href="/teacher/classes",
                    )
                )

        for subject in subject_rows:
            if TenantSearchService._matches(query, subject.name, subject.code, subject.description):
                items.append(
                    TenantSearchService._result(
                        label=subject.name,
                        role="subject",
                        metadata=subject.code,
                        subject_name=subject.name,
                        href="/teacher/subjects",
                    )
                )

        assigned_class_ids = [classroom.id for classroom in class_rows]
        if assigned_class_ids:
            student_rows = (
                await db.execute(
                    select(Student, ClassRoom)
                    .options(
                        selectinload(ClassRoom.academic_level),
                        selectinload(ClassRoom.arm_label_ref),
                    )
                    .outerjoin(ClassRoom, ClassRoom.id == Student.class_id)
                    .where(
                        Student.tenant_id == tenant_id,
                        Student.class_id.in_(assigned_class_ids),
                    )
                    .order_by(Student.first_name, Student.last_name, Student.admission_number)
                )
            ).all()
            for student, classroom in student_rows:
                class_label = classroom.display_name if classroom else None
                if TenantSearchService._matches(
                    query,
                    student.first_name,
                    student.last_name,
                    student.admission_number,
                    class_label,
                ):
                    items.append(
                        TenantSearchService._result(
                            label=TenantSearchService._name(student.first_name, student.last_name),
                            role="student",
                            metadata=class_label,
                            admission_number=student.admission_number,
                            class_name=class_label,
                            href="/teacher/students",
                        )
                    )

        result_rows = (
            await db.execute(
                select(
                    StudentSubjectResult,
                    Student,
                    ClassRoom,
                    Subject,
                    AcademicSession,
                    AcademicTerm,
                )
                .options(
                    selectinload(ClassRoom.academic_level),
                    selectinload(ClassRoom.arm_label_ref),
                )
                .join(Student, Student.id == StudentSubjectResult.student_id)
                .join(ClassRoom, ClassRoom.id == StudentSubjectResult.class_id)
                .join(Subject, Subject.id == StudentSubjectResult.subject_id)
                .join(
                    AcademicSession,
                    AcademicSession.id == StudentSubjectResult.academic_session_id,
                )
                .join(
                    AcademicTerm,
                    AcademicTerm.id == StudentSubjectResult.academic_term_id,
                )
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.teacher_membership_id == teacher_id,
                )
                .order_by(Student.first_name, Student.last_name, Subject.name)
            )
        ).all()
        for result, student, classroom, subject, session, term in result_rows:
            class_label = classroom.display_name
            session_label = session.name if session else None
            term_label = term.name.value if term else None
            if TenantSearchService._matches(
                query,
                student.first_name,
                student.last_name,
                student.admission_number,
                class_label,
                subject.name,
                subject.code,
                session_label,
                term_label,
                result.grade,
                result.status,
            ):
                items.append(
                    TenantSearchService._result(
                        label=f"{TenantSearchService._name(student.first_name, student.last_name)} - {subject.name}",
                        role="result",
                        metadata=f"{class_label} | {session_label} | {term_label}",
                        admission_number=student.admission_number,
                        class_name=class_label,
                        subject_name=subject.name,
                        href="/teacher/results",
                    )
                )

        return items[:limit]

    @staticmethod
    async def search_superadmin(
        db: AsyncSession,
        query: str,
        limit: int = 20,
    ) -> list[TenantSearchResult]:
        per_type_limit = max(1, min(limit, 10))
        items: list[TenantSearchResult] = []

        tenant_rows = (
            (
                await db.execute(
                    select(Tenant)
                    .where(
                        or_(
                            Tenant.school_name.ilike(f"%{query.strip()}%"),
                            Tenant.email.ilike(f"%{query.strip()}%"),
                            Tenant.slug.ilike(f"%{query.strip()}%"),
                            cast(Tenant.status, String).ilike(f"%{query.strip()}%"),
                            cast(Tenant.plan, String).ilike(f"%{query.strip()}%"),
                        )
                    )
                    .order_by(Tenant.school_name)
                )
            )
            .scalars()
            .all()
        )
        for tenant in tenant_rows[:per_type_limit]:
            items.append(
                TenantSearchService._result(
                    label=tenant.school_name,
                    role="tenant",
                    metadata=f"{tenant.status.value if hasattr(tenant.status, 'value') else tenant.status} | {tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan}",
                    email=tenant.email,
                    href="/superadmin/dashboard",
                )
            )

        superadmin_rows = (
            (
                await db.execute(
                    select(SuperAdmin)
                    .where(SuperAdmin.email.ilike(f"%{query.strip()}%"))
                    .order_by(SuperAdmin.email)
                )
            )
            .scalars()
            .all()
        )
        for superadmin in superadmin_rows[:per_type_limit]:
            items.append(
                TenantSearchService._result(
                    label=superadmin.email,
                    role="superadmin",
                    metadata="Platform administrator",
                    email=superadmin.email,
                    href="/superadmin/settings",
                )
            )

        return items[:limit]
