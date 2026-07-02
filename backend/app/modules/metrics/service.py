import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementRead,
    AnnouncementReadStatus,
)
from app.modules.classes.models import ClassRoom
from app.modules.metrics.schemas import ChartPoint, DashboardMetricsResponse
from app.modules.parents.models import Parent, ParentAccountStatus
from app.modules.students.models import Student, StudentAccountStatus, StudentParentLink, StudentProfileStatus
from app.modules.subjects.models import Subject
from app.modules.student_academics.models import AcademicSession, AcademicTerm, ClassSubjectTeacher, StudentSubjectResult, TeacherAssignment
from app.modules.report_cards.models import ReportCard, ReportCardStatus
from app.modules.teachers.models import Teacher, TeacherAccountStatus
from app.tenant_management.models import SubscriptionPlan, Tenant, TenantStatus, TenantVerificationStatus


class MetricsService:
    """Read-only dashboard aggregations."""

    @staticmethod
    async def _count(db: AsyncSession, model, *filters) -> int:
        return int((await db.execute(select(func.count()).select_from(model).where(*filters))).scalar_one())

    @staticmethod
    async def superadmin_dashboard(db: AsyncSession) -> DashboardMetricsResponse:
        total_tenants = await MetricsService._count(db, Tenant)
        active_tenants = await MetricsService._count(db, Tenant, Tenant.status == TenantStatus.ACTIVE, Tenant.is_deleted.is_(False))
        pending_tenants = await MetricsService._count(
            db,
            Tenant,
            Tenant.verification_status == TenantVerificationStatus.PENDING_VERIFICATION,
            Tenant.is_deleted.is_(False),
        )
        suspended_tenants = await MetricsService._count(db, Tenant, Tenant.status == TenantStatus.SUSPENDED, Tenant.is_deleted.is_(False))
        verified_tenants = await MetricsService._count(
            db,
            Tenant,
            Tenant.verification_status == TenantVerificationStatus.ACTIVE,
            Tenant.is_deleted.is_(False),
        )
        unverified_tenants = max(total_tenants - verified_tenants, 0)

        growth_period = func.date_trunc("month", Tenant.created_at)
        growth_rows = (
            await db.execute(
                select(growth_period.label("period"), func.count(Tenant.id).label("value"))
                .where(Tenant.is_deleted.is_(False))
                .group_by(growth_period)
                .order_by(growth_period)
            )
        ).all()

        return DashboardMetricsResponse(
            stats={
                "total_tenants": total_tenants,
                "active_tenants": active_tenants,
                "pending_tenants": pending_tenants,
                "suspended_tenants": suspended_tenants,
            },
            charts={
                "tenant_growth": [
                    ChartPoint(label=row.period.strftime("%Y-%m") if row.period else "", value=int(row.value))
                    for row in growth_rows
                ],
                "tenant_status_distribution": [
                    ChartPoint(label="active", value=active_tenants),
                    ChartPoint(label="pending", value=pending_tenants),
                    ChartPoint(label="suspended", value=suspended_tenants),
                ],
                "tenant_verification_breakdown": [
                    ChartPoint(label="verified", value=verified_tenants),
                    ChartPoint(label="unverified", value=unverified_tenants),
                ],
                "subscription_plan_distribution": [
                    ChartPoint(
                        label=plan.value,
                        value=await MetricsService._count(db, Tenant, Tenant.plan == plan, Tenant.is_deleted.is_(False)),
                    )
                    for plan in SubscriptionPlan
                ],
            },
        )

    @staticmethod
    async def tenant_admin_dashboard(db: AsyncSession, tenant_id: uuid.UUID) -> DashboardMetricsResponse:
        total_students = await MetricsService._count(db, Student, Student.tenant_id == tenant_id)
        total_teachers = await MetricsService._count(db, Teacher, Teacher.tenant_id == tenant_id)
        total_parents = await MetricsService._count(db, Parent, Parent.tenant_id == tenant_id)
        total_classes = await MetricsService._count(db, ClassRoom, ClassRoom.tenant_id == tenant_id)
        total_subjects = await MetricsService._count(db, Subject, Subject.tenant_id == tenant_id)
        report_cards_generated = await MetricsService._count(db, ReportCard, ReportCard.tenant_id == tenant_id)
        report_cards_published = await MetricsService._count(
            db,
            ReportCard,
            ReportCard.tenant_id == tenant_id,
            ReportCard.status == ReportCardStatus.PUBLISHED,
        )
        current_session = (
            await db.execute(
                select(AcademicSession).where(
                    AcademicSession.tenant_id == tenant_id,
                    AcademicSession.is_current.is_(True),
                    AcademicSession.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        current_term = (
            await db.execute(
                select(AcademicTerm).where(
                    AcademicTerm.tenant_id == tenant_id,
                    AcademicTerm.is_current.is_(True),
                    AcademicTerm.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        complete_profiles = await MetricsService._count(
            db,
            Student,
            Student.tenant_id == tenant_id,
            Student.profile_status == StudentProfileStatus.COMPLETE,
        )
        pending_teachers = await MetricsService._count(
            db,
            Teacher,
            Teacher.tenant_id == tenant_id,
            Teacher.account_status == TeacherAccountStatus.PENDING,
        )
        active_teachers = await MetricsService._count(
            db,
            Teacher,
            Teacher.tenant_id == tenant_id,
            Teacher.account_status == TeacherAccountStatus.ACTIVE,
        )
        pending_parents = await MetricsService._count(
            db,
            Parent,
            Parent.tenant_id == tenant_id,
            Parent.account_status == ParentAccountStatus.PENDING,
        )
        active_parents = await MetricsService._count(
            db,
            Parent,
            Parent.tenant_id == tenant_id,
            Parent.account_status == ParentAccountStatus.ACTIVE,
        )

        category_rows = (
            await db.execute(
                select(Announcement.category, func.count(Announcement.id))
                .where(Announcement.tenant_id == tenant_id)
                .group_by(Announcement.category)
            )
        ).all()
        class_rows = (
            await db.execute(
                select(ClassRoom.name, ClassRoom.arm, func.count(Student.id))
                .select_from(ClassRoom)
                .outerjoin(
                    Student,
                    and_(Student.class_id == ClassRoom.id, Student.tenant_id == ClassRoom.tenant_id),
                )
                .where(ClassRoom.tenant_id == tenant_id)
                .group_by(ClassRoom.id, ClassRoom.name, ClassRoom.arm)
                .order_by(ClassRoom.name.asc(), ClassRoom.arm.asc())
            )
        ).all()
        grade_rows = (
            await db.execute(
                select(StudentSubjectResult.grade, func.count(StudentSubjectResult.id))
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(StudentSubjectResult.grade)
            )
        ).all()
        result_status_rows = (
            await db.execute(
                select(StudentSubjectResult.status, func.count(StudentSubjectResult.id))
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(StudentSubjectResult.status)
            )
        ).all()
        subject_performance_rows = (
            await db.execute(
                select(Subject.name, func.avg(StudentSubjectResult.total_score))
                .join(Subject, Subject.id == StudentSubjectResult.subject_id)
                .where(StudentSubjectResult.tenant_id == tenant_id)
                .group_by(Subject.name)
                .order_by(Subject.name.asc())
            )
        ).all()

        return DashboardMetricsResponse(
            stats={
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_parents": total_parents,
                "total_classes": total_classes,
                "total_subjects": total_subjects,
                "student_profiles_complete": complete_profiles,
                "student_profiles_incomplete": max(total_students - complete_profiles, 0),
                "pending_teacher_accounts": pending_teachers,
                "pending_parent_accounts": pending_parents,
                "active_academic_session": current_session.name if current_session else None,
                "active_academic_term": current_term.name.value if current_term else None,
                "report_cards_generated": report_cards_generated,
                "report_cards_published": report_cards_published,
            },
            charts={
                "user_population_breakdown": [
                    ChartPoint(label="students", value=total_students),
                    ChartPoint(label="teachers", value=total_teachers),
                    ChartPoint(label="parents", value=total_parents),
                ],
                "student_profile_completion_rate": [
                    ChartPoint(label="complete", value=complete_profiles),
                    ChartPoint(label="incomplete", value=max(total_students - complete_profiles, 0)),
                ],
                "account_status_overview": [
                    ChartPoint(label="active_teachers", value=active_teachers),
                    ChartPoint(label="pending_teachers", value=pending_teachers),
                    ChartPoint(label="active_parents", value=active_parents),
                    ChartPoint(label="pending_parents", value=pending_parents),
                ],
                "announcements_by_category": [
                    ChartPoint(label=row[0].value if hasattr(row[0], "value") else str(row[0]), value=int(row[1]))
                    for row in category_rows
                ],
                "class_population": [
                    ChartPoint(label=f"{row.name} {row.arm}".strip(), value=int(row[2]))
                    for row in class_rows
                ],
                "grade_distribution": [
                    ChartPoint(label=row[0], value=int(row[1])) for row in grade_rows
                ],
                "result_status_distribution": [
                    ChartPoint(
                        label=row[0].value if hasattr(row[0], "value") else str(row[0]),
                        value=int(row[1]),
                    )
                    for row in result_status_rows
                ],
                "subject_performance": [
                    ChartPoint(label=row[0] or "Subject", value=round(float(row[1] or 0), 2))
                    for row in subject_performance_rows
                ],
            },
        )

    @staticmethod
    async def teacher_dashboard(db: AsyncSession, teacher_id: uuid.UUID, tenant_id: uuid.UUID) -> DashboardMetricsResponse:
        class_rows = (
            await db.execute(
                select(ClassRoom.id, ClassRoom.name, ClassRoom.arm, func.count(Student.id))
                .select_from(ClassRoom)
                .outerjoin(Student, and_(Student.class_id == ClassRoom.id, Student.tenant_id == ClassRoom.tenant_id))
                .where(ClassRoom.tenant_id == tenant_id, ClassRoom.teacher_id == teacher_id)
                .group_by(ClassRoom.id, ClassRoom.name, ClassRoom.arm)
                .order_by(ClassRoom.name.asc(), ClassRoom.arm.asc())
            )
        ).all()
        assignment_rows = (
            await db.execute(
                select(TeacherAssignment.id)
                .where(
                    TeacherAssignment.tenant_id == tenant_id,
                    TeacherAssignment.teacher_id == teacher_id,
                    TeacherAssignment.is_active.is_(True),
                )
            )
        ).scalars().all()
        submitted_results = await MetricsService._count(
            db,
            StudentSubjectResult,
            StudentSubjectResult.tenant_id == tenant_id,
            StudentSubjectResult.teacher_id == teacher_id,
            StudentSubjectResult.status == "submitted",
        )
        teacher_grade_rows = (
            await db.execute(
                select(StudentSubjectResult.grade, func.count(StudentSubjectResult.id))
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.teacher_id == teacher_id,
                )
                .group_by(StudentSubjectResult.grade)
            )
        ).all()
        own_announcement_ids = (
            await db.execute(
                select(Announcement.id).where(
                    Announcement.tenant_id == tenant_id,
                    Announcement.created_by_actor_type == AnnouncementActorType.TEACHER,
                    Announcement.created_by_actor_id == teacher_id,
                )
            )
        ).scalars().all()
        read_count = ack_count = 0
        if own_announcement_ids:
            read_count = await MetricsService._count(
                db,
                AnnouncementRead,
                AnnouncementRead.tenant_id == tenant_id,
                AnnouncementRead.announcement_id.in_(own_announcement_ids),
                AnnouncementRead.status.in_([AnnouncementReadStatus.READ, AnnouncementReadStatus.ACKNOWLEDGED]),
            )
            ack_count = await MetricsService._count(
                db,
                AnnouncementRead,
                AnnouncementRead.tenant_id == tenant_id,
                AnnouncementRead.announcement_id.in_(own_announcement_ids),
                AnnouncementRead.status == AnnouncementReadStatus.ACKNOWLEDGED,
            )
        category_rows = (
            await db.execute(
                select(Announcement.category, func.count(Announcement.id))
                .where(
                    Announcement.tenant_id == tenant_id,
                    Announcement.created_by_actor_type == AnnouncementActorType.TEACHER,
                    Announcement.created_by_actor_id == teacher_id,
                )
                .group_by(Announcement.category)
            )
        ).all()
        return DashboardMetricsResponse(
            stats={
                "total_classes": len(class_rows),
                "assigned_subjects": len(assignment_rows),
                "total_announcements": len(own_announcement_ids),
                "results_submitted": submitted_results,
                "results_published": submitted_results,
            },
            charts={
                "class_sizes": [
                    ChartPoint(label=f"{row.name} {row.arm}".strip(), value=int(row[3]))
                    for row in class_rows
                ],
                "announcement_read_vs_acknowledged": [
                    ChartPoint(label="read", value=read_count),
                    ChartPoint(label="acknowledged", value=ack_count),
                ],
                "announcement_category_breakdown": [
                    ChartPoint(label=row[0].value if hasattr(row[0], "value") else str(row[0]), value=int(row[1]))
                    for row in category_rows
                ],
                "grade_distribution": [
                    ChartPoint(label=row[0], value=int(row[1])) for row in teacher_grade_rows
                ],
            },
        )

    @staticmethod
    async def _personal_announcement_metrics(
        db: AsyncSession,
        *,
        actor_id: uuid.UUID,
        tenant_id: uuid.UUID,
        feed_total: int,
        read_count: int,
        category_counts: dict[str, int],
    ) -> DashboardMetricsResponse:
        return DashboardMetricsResponse(
            stats={"feed_total": feed_total, "read_count": read_count, "unread_count": max(feed_total - read_count, 0)},
            charts={
                "announcement_read_vs_unread": [
                    ChartPoint(label="read", value=read_count),
                    ChartPoint(label="unread", value=max(feed_total - read_count, 0)),
                ],
                "announcement_category_breakdown": [
                    ChartPoint(label=label, value=value)
                    for label, value in category_counts.items()
                ],
            },
        )

    @staticmethod
    async def parent_dashboard(
        db: AsyncSession,
        parent_id: uuid.UUID,
        tenant_id: uuid.UUID,
        feed_total: int,
        read_count: int,
        category_counts: dict[str, int],
    ) -> DashboardMetricsResponse:
        response = await MetricsService._personal_announcement_metrics(
            db,
            actor_id=parent_id,
            tenant_id=tenant_id,
            feed_total=feed_total,
            read_count=read_count,
            category_counts=category_counts,
        )
        return response

    @staticmethod
    async def student_dashboard(
        db: AsyncSession,
        student_id: uuid.UUID,
        tenant_id: uuid.UUID,
        feed_total: int,
        read_count: int,
        category_counts: dict[str, int],
    ) -> DashboardMetricsResponse:
        result_rows = (
            await db.execute(
                select(StudentSubjectResult)
                .where(
                    StudentSubjectResult.tenant_id == tenant_id,
                    StudentSubjectResult.student_id == student_id,
                    StudentSubjectResult.status == "submitted",
                )
            )
        ).scalars().all()
        average = (
            round(sum(float(row.total_score or 0) for row in result_rows) / len(result_rows), 2)
            if result_rows
            else 0
        )
        grade_counts: dict[str, int] = {}
        for row in result_rows:
            grade_counts[row.grade] = grade_counts.get(row.grade, 0) + 1
        return DashboardMetricsResponse(
            stats={
                "feed_total": feed_total,
                "read_count": read_count,
                "unread_count": max(feed_total - read_count, 0),
                "current_average": average,
                "published_results": len(result_rows),
            },
            charts={
                "grade_distribution": [
                    ChartPoint(label=label, value=value) for label, value in grade_counts.items()
                ],
                "subject_comparison": [
                    ChartPoint(label=row.grade, value=float(row.total_score or 0)) for row in result_rows
                ],
            },
        )
