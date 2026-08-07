import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.modules.communications.enums import (
    CommunicationActorType,
    NotificationSourceType,
    NotificationStatus,
)
from app.modules.communications.models import (
    Announcement,
    NotificationDelivery,
)
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent, ParentAccount, ParentAccountStatus
from app.modules.students.models import Student, StudentProfileStatus
from app.modules.subjects.models import Subject
from app.modules.student_academics.models import (
    AcademicResultStatus,
    AcademicSession,
    AcademicSessionStatus,
    AcademicTerm,
    AcademicTermStatus,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.report_cards.models import ReportCard, ReportCardStatus
from app.modules.teachers.models import Teacher, TeacherAccount, TeacherAccountStatus
from app.tenant_management.models import (
    SubscriptionPlan,
    Tenant,
    TenantStatus,
    TenantVerificationStatus,
)


@dataclass(frozen=True)
class PeriodCount:
    period: datetime | None
    value: int


@dataclass(frozen=True)
class LabelCount:
    label: object
    value: int


@dataclass(frozen=True)
class ClassPopulation:
    name: str
    arm: str | None
    value: int


@dataclass(frozen=True)
class SubjectPerformance:
    name: str | None
    average: float


@dataclass(frozen=True)
class StudentResultMetric:
    grade: str | None
    total_score: Decimal


class MetricsRepository:
    """Database aggregations for dashboard metrics."""

    @staticmethod
    async def count(db: AsyncSession, model: Any, *filters: ColumnElement[bool]) -> int:
        result = await db.execute(select(func.count()).select_from(model).where(*filters))
        return int(result.scalar_one())

    @staticmethod
    def _count_subquery(model: Any, *filters: ColumnElement[bool]):
        return select(func.count()).select_from(model).where(*filters).scalar_subquery()

    @staticmethod
    async def superadmin_counts(db: AsyncSession) -> dict[str, int]:
        row = (
            await db.execute(
                select(
                    func.count(Tenant.id).label("total_tenants"),
                    func.count(Tenant.id)
                    .filter(
                        Tenant.status == TenantStatus.ACTIVE,
                        Tenant.is_deleted.is_(False),
                    )
                    .label("active_tenants"),
                    func.count(Tenant.id)
                    .filter(
                        Tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION,
                        Tenant.is_deleted.is_(False),
                    )
                    .label("pending_tenants"),
                    func.count(Tenant.id)
                    .filter(
                        Tenant.status == TenantStatus.SUSPENDED,
                        Tenant.is_deleted.is_(False),
                    )
                    .label("suspended_tenants"),
                    func.count(Tenant.id)
                    .filter(
                        Tenant.verification_status == TenantVerificationStatus.ACTIVE,
                        Tenant.is_deleted.is_(False),
                    )
                    .label("verified_tenants"),
                )
            )
        ).one()
        return {key: int(value or 0) for key, value in row._mapping.items()}

    @staticmethod
    async def tenant_growth(db: AsyncSession) -> list[PeriodCount]:
        growth_period = func.date_trunc("month", Tenant.created_at)
        rows = (
            await db.execute(
                select(growth_period.label("period"), func.count(Tenant.id).label("value"))
                .where(Tenant.is_deleted.is_(False))
                .group_by(growth_period)
                .order_by(growth_period)
            )
        ).all()
        return [PeriodCount(period=row.period, value=int(row.value)) for row in rows]

    @staticmethod
    async def subscription_plan_distribution(
        db: AsyncSession,
    ) -> dict[SubscriptionPlan, int]:
        rows = (
            await db.execute(
                select(Tenant.plan, func.count(Tenant.id))
                .where(Tenant.is_deleted.is_(False))
                .group_by(Tenant.plan)
            )
        ).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    async def tenant_admin_counts(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
        """Return tenant dashboard counts with one database round trip.

        The previous implementation ran each count as a separate query. That is
        acceptable against local Postgres, but it becomes slow against remote
        Supabase because network round-trip time is paid for every count.
        """
        row = (
            await db.execute(
                select(
                    MetricsRepository._count_subquery(
                        Student,
                        Student.tenant_id == tenant_id,
                    ).label("total_students"),
                    MetricsRepository._count_subquery(
                        Teacher,
                        Teacher.tenant_id == tenant_id,
                    ).label("total_teachers"),
                    MetricsRepository._count_subquery(
                        Parent,
                        Parent.tenant_id == tenant_id,
                    ).label("total_parents"),
                    MetricsRepository._count_subquery(
                        ClassRoom,
                        ClassRoom.tenant_id == tenant_id,
                    ).label("total_classes"),
                    MetricsRepository._count_subquery(
                        Subject,
                        Subject.tenant_id == tenant_id,
                    ).label("total_subjects"),
                    MetricsRepository._count_subquery(
                        ReportCard,
                        ReportCard.tenant_id == tenant_id,
                    ).label("report_cards_generated"),
                    MetricsRepository._count_subquery(
                        ReportCard,
                        ReportCard.tenant_id == tenant_id,
                        ReportCard.status == ReportCardStatus.PUBLISHED,
                    ).label("report_cards_published"),
                    MetricsRepository._count_subquery(
                        Student,
                        Student.tenant_id == tenant_id,
                        Student.profile_status == StudentProfileStatus.COMPLETE,
                    ).label("complete_profiles"),
                    MetricsRepository._count_subquery(
                        Teacher,
                        Teacher.tenant_id == tenant_id,
                        Teacher.teacher_account.has(
                            TeacherAccount.account_status == TeacherAccountStatus.PENDING,
                        ),
                    ).label("pending_teachers"),
                    MetricsRepository._count_subquery(
                        Teacher,
                        Teacher.tenant_id == tenant_id,
                        Teacher.teacher_account.has(
                            TeacherAccount.account_status == TeacherAccountStatus.ACTIVE,
                        ),
                    ).label("active_teachers"),
                    MetricsRepository._count_subquery(
                        Parent,
                        Parent.tenant_id == tenant_id,
                        Parent.parent_account.has(
                            ParentAccount.account_status == ParentAccountStatus.PENDING,
                        ),
                    ).label("pending_parents"),
                    MetricsRepository._count_subquery(
                        Parent,
                        Parent.tenant_id == tenant_id,
                        Parent.parent_account.has(
                            ParentAccount.account_status == ParentAccountStatus.ACTIVE,
                        ),
                    ).label("active_parents"),
                )
            )
        ).one()
        return {key: int(value or 0) for key, value in row._mapping.items()}

    @staticmethod
    async def current_academic_session(
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
    async def current_academic_term(
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
    async def announcement_category_counts(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[LabelCount]:
        rows = (
            await db.execute(
                select(Announcement.category, func.count(Announcement.id))
                .where(Announcement.tenant_id == tenant_id)
                .group_by(Announcement.category)
            )
        ).all()
        return [LabelCount(label=row[0], value=int(row[1])) for row in rows]

    @staticmethod
    async def class_population(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[ClassPopulation]:
        rows = (
            await db.execute(
                select(ClassRoom.name, ClassRoom.arm, func.count(Student.id))
                .select_from(ClassRoom)
                .outerjoin(
                    Student,
                    and_(
                        Student.class_id == ClassRoom.id,
                        Student.tenant_id == ClassRoom.tenant_id,
                    ),
                )
                .where(ClassRoom.tenant_id == tenant_id)
                .group_by(ClassRoom.id, ClassRoom.name, ClassRoom.arm)
                .order_by(ClassRoom.name.asc(), ClassRoom.arm.asc())
            )
        ).all()
        return [ClassPopulation(name=row.name, arm=row.arm, value=int(row[2])) for row in rows]

    @staticmethod
    async def result_grade_counts(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[LabelCount]:
        rows = (
            await db.execute(
                select(StudentSubjectResult.grade, func.count(StudentSubjectResult.id))
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(StudentSubjectResult.grade)
            )
        ).all()
        return [LabelCount(label=row[0], value=int(row[1])) for row in rows]

    @staticmethod
    async def result_status_counts(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[LabelCount]:
        rows = (
            await db.execute(
                select(StudentSubjectResult.status, func.count(StudentSubjectResult.id))
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(StudentSubjectResult.status)
            )
        ).all()
        return [LabelCount(label=row[0], value=int(row[1])) for row in rows]

    @staticmethod
    async def subject_performance(
        db: AsyncSession,
        tenant_id: uuid.UUID,
    ) -> list[SubjectPerformance]:
        rows = (
            await db.execute(
                select(Subject.name, func.avg(StudentSubjectResult.total_score))
                .join(Subject, Subject.id == StudentSubjectResult.subject_id)
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(Subject.name)
                .order_by(Subject.name.asc())
            )
        ).all()
        return [
            SubjectPerformance(name=row[0], average=round(float(row[1] or 0), 2)) for row in rows
        ]

    @staticmethod
    async def teacher_class_sizes(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> list[ClassPopulation]:
        rows = (
            await db.execute(
                select(ClassRoom.id, ClassRoom.name, ClassRoom.arm, func.count(Student.id))
                .select_from(ClassRoom)
                .outerjoin(
                    Student,
                    and_(
                        Student.class_id == ClassRoom.id,
                        Student.tenant_id == ClassRoom.tenant_id,
                    ),
                )
                .where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.teacher_membership_id == teacher_id,
                )
                .group_by(ClassRoom.id, ClassRoom.name, ClassRoom.arm)
                .order_by(ClassRoom.name.asc(), ClassRoom.arm.asc())
            )
        ).all()
        return [ClassPopulation(name=row.name, arm=row.arm, value=int(row[3])) for row in rows]

    @staticmethod
    async def active_teacher_assignment_count(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> int:
        return await MetricsRepository.count(
            db,
            TeacherAssignment,
            TeacherAssignment.tenant_id == tenant_id,
            TeacherAssignment.teacher_membership_id == teacher_id,
            TeacherAssignment.is_active.is_(True),
        )

    @staticmethod
    async def submitted_result_count_for_teacher(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> int:
        return await MetricsRepository.count(
            db,
            StudentSubjectResult,
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.teacher_membership_id == teacher_id,
            StudentSubjectResult.status == AcademicResultStatus.SUBMITTED,
        )

    @staticmethod
    async def teacher_grade_counts(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> list[LabelCount]:
        rows = (
            await db.execute(
                select(StudentSubjectResult.grade, func.count(StudentSubjectResult.id))
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.teacher_membership_id == teacher_id,
                )
                .group_by(StudentSubjectResult.grade)
            )
        ).all()
        return [LabelCount(label=row[0], value=int(row[1])) for row in rows]

    @staticmethod
    async def teacher_announcement_ids(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> list[uuid.UUID]:
        return list(
            (
                await db.execute(
                    select(Announcement.id).where(
                        Announcement.tenant_id == tenant_id,
                        Announcement.created_by_actor_type == CommunicationActorType.TEACHER,
                        Announcement.created_by_actor_id == teacher_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def teacher_announcement_category_counts(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        teacher_id: uuid.UUID,
    ) -> list[LabelCount]:
        rows = (
            await db.execute(
                select(Announcement.category, func.count(Announcement.id))
                .where(
                    Announcement.tenant_id == tenant_id,
                    Announcement.created_by_actor_type == CommunicationActorType.TEACHER,
                    Announcement.created_by_actor_id == teacher_id,
                )
                .group_by(Announcement.category)
            )
        ).all()
        return [LabelCount(label=row[0], value=int(row[1])) for row in rows]

    @staticmethod
    async def announcement_read_count(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        announcement_ids: list[uuid.UUID],
        statuses: list[NotificationStatus],
    ) -> int:
        if not announcement_ids:
            return 0

        return await MetricsRepository.count(
            db,
            NotificationDelivery,
            NotificationDelivery.tenant_id == tenant_id,
            NotificationDelivery.source_type == NotificationSourceType.ANNOUNCEMENT,
            NotificationDelivery.source_id.in_(announcement_ids),
            NotificationDelivery.status.in_(statuses),
        )

    @staticmethod
    async def notification_summary_for_actor(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        actor_type: CommunicationActorType,
        actor_id: uuid.UUID,
    ) -> tuple[int, int, list[LabelCount]]:
        rows = (
            await db.execute(
                select(
                    NotificationDelivery.source_type,
                    NotificationDelivery.status,
                    func.count(NotificationDelivery.id),
                )
                .where(
                    NotificationDelivery.tenant_id == tenant_id,
                    NotificationDelivery.recipient_actor_type == actor_type,
                    NotificationDelivery.recipient_actor_id == actor_id,
                    NotificationDelivery.status != NotificationStatus.DISMISSED,
                )
                .group_by(NotificationDelivery.source_type, NotificationDelivery.status)
            )
        ).all()
        total = 0
        read_count = 0
        by_source: dict[object, int] = {}
        for source_type, status, count in rows:
            value = int(count or 0)
            total += value
            if status in {NotificationStatus.READ, NotificationStatus.ACKNOWLEDGED}:
                read_count += value
            by_source[source_type] = by_source.get(source_type, 0) + value
        return (
            total,
            read_count,
            [LabelCount(label=label, value=value) for label, value in by_source.items()],
        )

    @staticmethod
    async def submitted_results_for_student(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> list[StudentResultMetric]:
        rows = (
            await db.execute(
                select(StudentSubjectResult.grade, StudentSubjectResult.total_score).where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                    StudentSubjectResult.status == AcademicResultStatus.SUBMITTED,
                )
            )
        ).all()
        return [StudentResultMetric(grade=row.grade, total_score=row.total_score) for row in rows]
