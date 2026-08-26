"""Repositories for the tenant academic structure."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.classes.models import (
    AcademicLevel,
    AcademicLevelStatus,
    ArmLabel,
    ClassRoom,
    Department,
)
from app.modules.student_academics.curriculum_models import (
    Curriculum,
    CurriculumSubject,
    CurriculumOffering,
    ClassTermDepartmentAssignment,
)
from app.modules.student_academics.models import TeacherAssignment, AcademicTermStatus, AcademicTerm
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment


class AcademicLevelRepository:
    @staticmethod
    async def add(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    @staticmethod
    async def save(db: AsyncSession, level: AcademicLevel) -> AcademicLevel:
        db.add(level)
        await db.flush()
        return level

    @staticmethod
    async def delete(db: AsyncSession, level: AcademicLevel) -> None:
        await db.delete(level)

    @staticmethod
    async def get_by_id(
        db: AsyncSession, tenant_id: uuid.UUID, level_id: uuid.UUID, *, lock: bool = False
    ):
        query = select(AcademicLevel).where(
            AcademicLevel.tenant_id == tenant_id, AcademicLevel.id == level_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_name(db: AsyncSession, tenant_id: uuid.UUID, name: str):
        from app.core.utils.normalization import normalized_class_name_key

        normalized = normalized_class_name_key(name)
        return (
            await db.execute(
                select(AcademicLevel).where(
                    AcademicLevel.tenant_id == tenant_id,
                    AcademicLevel.normalized_name == normalized,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def get_by_category_position(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        category,
        position: int,
        *,
        exclude_id: uuid.UUID | None = None,
    ):
        query = select(AcademicLevel).where(
            AcademicLevel.tenant_id == tenant_id,
            AcademicLevel.category == category,
            AcademicLevel.position == position,
        )
        if exclude_id is not None:
            query = query.where(AcademicLevel.id != exclude_id)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ):
        query = select(AcademicLevel).where(AcademicLevel.tenant_id == tenant_id)
        if active_only:
            query = query.where(AcademicLevel.status == AcademicLevelStatus.ACTIVE)
        elif not include_archived:
            query = query.where(AcademicLevel.status != AcademicLevelStatus.ARCHIVED)
        query = query.order_by(AcademicLevel.category, AcademicLevel.position, AcademicLevel.name)
        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def count_setup_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        level_id: uuid.UUID,
    ) -> dict[str, int]:
        """
        Return all AcademicLevel dependency counts needed by lifecycle rules.

        Total counts tell us whether the level has ever been structurally used.
        Active/current counts tell us whether the level is still in live use.

        An empty Curriculum container is intentionally not treated as real usage.
        Actual curriculum usage begins when CurriculumSubject rows exist.
        """

        def count_subquery(model, *conditions):
            return select(func.count()).select_from(model).where(*conditions).scalar_subquery()

        curriculum_ids = select(Curriculum.id).where(
            Curriculum.tenant_id == tenant_id,
            Curriculum.academic_level_id == level_id,
        )

        query = select(
            # ---------------------------------------------------------
            # Classes
            # ---------------------------------------------------------
            count_subquery(
                ClassRoom,
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.academic_level_id == level_id,
            ).label("classes_total"),
            count_subquery(
                ClassRoom,
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.academic_level_id == level_id,
                ClassRoom.is_active.is_(True),
                ClassRoom.archived_at.is_(None),
            ).label("classes_active"),
            # ---------------------------------------------------------
            # Departments
            # ---------------------------------------------------------
            count_subquery(
                Department,
                Department.tenant_id == tenant_id,
                Department.academic_level_id == level_id,
            ).label("departments_total"),
            count_subquery(
                Department,
                Department.tenant_id == tenant_id,
                Department.academic_level_id == level_id,
                Department.is_active.is_(True),
                Department.archived_at.is_(None),
            ).label("departments_active"),
            # ---------------------------------------------------------
            # Curriculum subjects
            # ---------------------------------------------------------
            count_subquery(
                CurriculumSubject,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.curriculum_id.in_(curriculum_ids),
            ).label("curriculum_subjects_total"),
            count_subquery(
                CurriculumSubject,
                CurriculumSubject.tenant_id == tenant_id,
                CurriculumSubject.curriculum_id.in_(curriculum_ids),
                CurriculumSubject.is_active.is_(True),
            ).label("curriculum_subjects_active"),
            # ---------------------------------------------------------
            # Student enrollments
            # ---------------------------------------------------------
            count_subquery(
                StudentEnrollment,
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_level_id == level_id,
            ).label("enrollments_total"),
            count_subquery(
                StudentEnrollment,
                StudentEnrollment.tenant_id == tenant_id,
                StudentEnrollment.academic_level_id == level_id,
                StudentEnrollment.is_current.is_(True),
            ).label("enrollments_current"),
        )

        row = (await db.execute(query)).one()

        return {
            "classes_total": int(row.classes_total),
            "classes_active": int(row.classes_active),
            "departments_total": int(row.departments_total),
            "departments_active": int(row.departments_active),
            "curriculum_subjects_total": int(row.curriculum_subjects_total),
            "curriculum_subjects_active": int(row.curriculum_subjects_active),
            "enrollments_total": int(row.enrollments_total),
            "enrollments_current": int(row.enrollments_current),
        }


class DepartmentRepository:
    @staticmethod
    async def add(db: AsyncSession, department: Department) -> Department:
        db.add(department)
        await db.flush()
        return department

    @staticmethod
    async def save(db: AsyncSession, department: Department) -> Department:
        db.add(department)
        await db.flush()
        return department

    @staticmethod
    async def get_by_id(
        db: AsyncSession, tenant_id: uuid.UUID, department_id: uuid.UUID, *, lock: bool = False
    ):
        query = select(Department).where(
            Department.tenant_id == tenant_id, Department.id == department_id
        )
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_name(
        db: AsyncSession, tenant_id: uuid.UUID, academic_level_id: uuid.UUID, normalized_name: str
    ) -> Department | None:
        return (
            await db.execute(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.academic_level_id == academic_level_id,
                    Department.normalized_name == normalized_name,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_for_level(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ) -> list[Department]:
        query = select(Department).where(
            Department.tenant_id == tenant_id,
            Department.academic_level_id == academic_level_id,
        )

        if active_only:
            query = query.where(
                Department.is_active.is_(True),
                Department.archived_at.is_(None),
            )

        elif not include_archived:
            query = query.where(
                Department.archived_at.is_(None),
            )

        query = query.order_by(Department.name)

        return list((await db.execute(query)).scalars().all())

    @staticmethod
    async def list_for_tenant(db: AsyncSession, tenant_id: uuid.UUID, *, active_only: bool = False):
        query = select(Department).where(Department.tenant_id == tenant_id)
        if active_only:
            query = query.where(Department.is_active.is_(True), Department.archived_at.is_(None))
        return list(
            (await db.execute(query.order_by(Department.academic_level_id, Department.name)))
            .scalars()
            .all()
        )

    @staticmethod
    async def count_dependencies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> dict[str, int]:
        """
        Return Department dependency counts used by lifecycle rules.

        Total counts represent all historical and current usage.

        Live counts represent usage attached to terms that are still capable of
        affecting current/future academic configuration:
        - DRAFT
        - OPEN
        - CLOSING

        CLOSED-term references are historical and therefore do not count as live.
        """

        live_term_statuses = (
            AcademicTermStatus.DRAFT,
            AcademicTermStatus.OPEN,
            AcademicTermStatus.CLOSING,
        )

        class_assignments_total = (
            select(func.count())
            .select_from(ClassTermDepartmentAssignment)
            .where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.department_id == department_id,
            )
            .scalar_subquery()
        )

        class_assignments_live = (
            select(func.count())
            .select_from(ClassTermDepartmentAssignment)
            .join(
                AcademicTerm,
                AcademicTerm.id == ClassTermDepartmentAssignment.academic_term_id,
            )
            .where(
                ClassTermDepartmentAssignment.tenant_id == tenant_id,
                ClassTermDepartmentAssignment.department_id == department_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(live_term_statuses),
            )
            .scalar_subquery()
        )

        offerings_total = (
            select(func.count())
            .select_from(CurriculumOffering)
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.department_id == department_id,
            )
            .scalar_subquery()
        )

        offerings_live = (
            select(func.count())
            .select_from(CurriculumOffering)
            .join(
                AcademicTerm,
                AcademicTerm.id == CurriculumOffering.academic_term_id,
            )
            .where(
                CurriculumOffering.tenant_id == tenant_id,
                CurriculumOffering.department_id == department_id,
                AcademicTerm.tenant_id == tenant_id,
                AcademicTerm.status.in_(live_term_statuses),
            )
            .scalar_subquery()
        )

        query = select(
            class_assignments_total.label("class_assignments_total"),
            class_assignments_live.label("class_assignments_live"),
            offerings_total.label("offerings_total"),
            offerings_live.label("offerings_live"),
        )

        row = (await db.execute(query)).one()

        return {
            "class_assignments_total": int(row.class_assignments_total),
            "class_assignments_live": int(row.class_assignments_live),
            "offerings_total": int(row.offerings_total),
            "offerings_live": int(row.offerings_live),
        }

    @staticmethod
    async def delete(db: AsyncSession, department: Department) -> None:
        await db.delete(department)


class ArmLabelRepository:
    @staticmethod
    async def add(db: AsyncSession, arm_label: ArmLabel):
        db.add(arm_label)
        await db.flush()
        return arm_label

    @staticmethod
    async def save(db: AsyncSession, arm_label: ArmLabel):
        db.add(arm_label)
        await db.flush()
        return arm_label

    @staticmethod
    async def get_by_id(
        db: AsyncSession, tenant_id: uuid.UUID, arm_label_id: uuid.UUID, *, lock: bool = False
    ):
        query = select(ArmLabel).where(ArmLabel.tenant_id == tenant_id, ArmLabel.id == arm_label_id)
        if lock:
            query = query.with_for_update()
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_label(
        db: AsyncSession, tenant_id: uuid.UUID, normalized_label: str
    ):
        return (
            await db.execute(
                select(ArmLabel).where(
                    ArmLabel.tenant_id == tenant_id, ArmLabel.normalized_label == normalized_label
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        active_only: bool = False,
        include_archived: bool = False,
    ):
        query = select(ArmLabel).where(ArmLabel.tenant_id == tenant_id)
        if active_only:
            query = query.where(ArmLabel.is_active.is_(True), ArmLabel.archived_at.is_(None))
        elif not include_archived:
            query = query.where(ArmLabel.archived_at.is_(None))
        return list((await db.execute(query.order_by(ArmLabel.label))).scalars().all())

    @staticmethod
    async def count_class_dependencies(
        db: AsyncSession, tenant_id: uuid.UUID, arm_label_id: uuid.UUID
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(ClassRoom)
                    .where(ClassRoom.tenant_id == tenant_id, ClassRoom.arm_label_id == arm_label_id)
                )
            ).scalar_one()
        )


class ClassRoomRepository:
    LOAD = (joinedload(ClassRoom.academic_level), joinedload(ClassRoom.arm_label_ref))

    @staticmethod
    async def add(db: AsyncSession, classroom: ClassRoom):
        db.add(classroom)
        await db.flush()
        return classroom

    @staticmethod
    async def save(db: AsyncSession, classroom: ClassRoom):
        db.add(classroom)
        await db.flush()
        return classroom

    @staticmethod
    async def delete_classroom(db: AsyncSession, classroom: ClassRoom):
        await db.delete(classroom)

    @staticmethod
    async def get_by_id(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, *, lock: bool = False
    ):
        query = (
            select(ClassRoom)
            .options(*ClassRoomRepository.LOAD)
            .where(ClassRoom.tenant_id == tenant_id, ClassRoom.id == class_id)
        )
        if lock:
            query = query.with_for_update(of=ClassRoom)
        return (await db.execute(query)).scalar_one_or_none()

    @staticmethod
    async def get_by_level_arm_label(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        academic_level_id: uuid.UUID,
        arm_label_id: uuid.UUID,
    ):
        return (
            await db.execute(
                select(ClassRoom).where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.academic_level_id == academic_level_id,
                    ClassRoom.arm_label_id == arm_label_id,
                )
            )
        ).scalar_one_or_none()

    @staticmethod
    async def list_for_tenant(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 100,
        include_archived: bool = False,
    ):
        query = (
            select(ClassRoom)
            .options(*ClassRoomRepository.LOAD)
            .where(ClassRoom.tenant_id == tenant_id)
        )
        if not include_archived:
            query = query.where(ClassRoom.archived_at.is_(None))
        return list(
            (await db.execute(query.order_by(ClassRoom.created_at).offset(offset).limit(limit)))
            .scalars()
            .unique()
            .all()
        )

    @staticmethod
    async def list_by_teacher_membership(
        db: AsyncSession, tenant_id: uuid.UUID, teacher_membership_id: uuid.UUID
    ):
        query = (
            select(ClassRoom)
            .options(*ClassRoomRepository.LOAD)
            .where(
                ClassRoom.tenant_id == tenant_id,
                ClassRoom.teacher_membership_id == teacher_membership_id,
                ClassRoom.archived_at.is_(None),
            )
        )
        return list((await db.execute(query)).scalars().unique().all())

    @staticmethod
    async def list_by_ids(db: AsyncSession, tenant_id: uuid.UUID, class_ids: list[uuid.UUID]):
        if not class_ids:
            return []
        return list(
            (
                await db.execute(
                    select(ClassRoom)
                    .options(*ClassRoomRepository.LOAD)
                    .where(ClassRoom.tenant_id == tenant_id, ClassRoom.id.in_(class_ids))
                )
            )
            .scalars()
            .unique()
            .all()
        )

    @staticmethod
    async def count_assigned_students_by_status(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, status: AcademicStatus
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Student)
                    .where(
                        Student.tenant_id == tenant_id,
                        Student.class_id == class_id,
                        Student.status == status,
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_current_enrollments(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(StudentEnrollment)
                    .where(
                        StudentEnrollment.tenant_id == tenant_id,
                        StudentEnrollment.class_id == class_id,
                        StudentEnrollment.is_current.is_(True),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_active_teacher_assignments(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> int:
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(TeacherAssignment)
                    .where(
                        TeacherAssignment.tenant_id == tenant_id,
                        TeacherAssignment.class_id == class_id,
                        TeacherAssignment.is_active.is_(True),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def count_class_dependencies(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> dict[str, int]:
        return {
            "students": await ClassRoomRepository.count_current_enrollments(
                db, tenant_id, class_id
            ),
            "teacher_assignments": await ClassRoomRepository.count_active_teacher_assignments(
                db, tenant_id, class_id
            ),
        }
