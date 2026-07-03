import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.cache.manager import CacheManager
from app.modules.announcements.models import AnnouncementReadStatus
from app.modules.announcements.service import AnnouncementService
from app.modules.metrics.cache import (
    parent_dashboard_cache_key,
    student_dashboard_cache_key,
    superadmin_dashboard_cache_key,
    teacher_dashboard_cache_key,
    tenant_admin_dashboard_cache_key,
)
from app.modules.metrics.repository import MetricsRepository
from app.modules.metrics.schemas import ChartPoint, DashboardMetricsResponse
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.tenant_management.models import SubscriptionPlan


class MetricsService:
    """Business logic for dashboard metrics and cache orchestration."""

    @staticmethod
    def _enum_label(value: object) -> str:
        return value.value if hasattr(value, "value") else str(value)

    @staticmethod
    def _label(value: object, fallback: str = "Unknown") -> str:
        if value is None:
            return fallback
        return MetricsService._enum_label(value)

    @staticmethod
    async def _cached_dashboard(key: str, fetcher) -> DashboardMetricsResponse:
        dashboard = await CacheManager.get_or_set(
            key=key,
            fetcher=fetcher,
            ttl=settings.CACHE_SHORT_TTL_SECONDS,
        )
        return DashboardMetricsResponse.model_validate(dashboard)

    @staticmethod
    async def superadmin_dashboard(db: AsyncSession) -> DashboardMetricsResponse:
        async def fetch_dashboard() -> DashboardMetricsResponse:
            counts = await MetricsRepository.superadmin_counts(db)
            growth_rows = await MetricsRepository.tenant_growth(db)
            plan_counts = await MetricsRepository.subscription_plan_distribution(db)
            unverified_tenants = max(
                counts["total_tenants"] - counts["verified_tenants"],
                0,
            )

            return DashboardMetricsResponse(
                stats={
                    "total_tenants": counts["total_tenants"],
                    "active_tenants": counts["active_tenants"],
                    "pending_tenants": counts["pending_tenants"],
                    "suspended_tenants": counts["suspended_tenants"],
                },
                charts={
                    "tenant_growth": [
                        ChartPoint(
                            label=row.period.strftime("%Y-%m") if row.period else "",
                            value=int(row.value),
                        )
                        for row in growth_rows
                    ],
                    "tenant_status_distribution": [
                        ChartPoint(label="active", value=counts["active_tenants"]),
                        ChartPoint(label="pending", value=counts["pending_tenants"]),
                        ChartPoint(label="suspended", value=counts["suspended_tenants"]),
                    ],
                    "tenant_verification_breakdown": [
                        ChartPoint(label="verified", value=counts["verified_tenants"]),
                        ChartPoint(label="unverified", value=unverified_tenants),
                    ],
                    "subscription_plan_distribution": [
                        ChartPoint(label=plan.value, value=plan_counts.get(plan, 0))
                        for plan in SubscriptionPlan
                    ],
                },
            )

        return await MetricsService._cached_dashboard(
            key=superadmin_dashboard_cache_key(),
            fetcher=fetch_dashboard,
        )

    @staticmethod
    async def tenant_admin_dashboard(db: AsyncSession, tenant_id: uuid.UUID) -> DashboardMetricsResponse:
        async def fetch_dashboard() -> DashboardMetricsResponse:
            counts = await MetricsRepository.tenant_admin_counts(db, tenant_id)
            current_session = await MetricsRepository.current_academic_session(db, tenant_id)
            current_term = await MetricsRepository.current_academic_term(db, tenant_id)
            category_rows = await MetricsRepository.announcement_category_counts(db, tenant_id)
            class_rows = await MetricsRepository.class_population(db, tenant_id)
            grade_rows = await MetricsRepository.result_grade_counts(db, tenant_id)
            result_status_rows = await MetricsRepository.result_status_counts(db, tenant_id)
            subject_performance_rows = await MetricsRepository.subject_performance(db, tenant_id)

            incomplete_profiles = max(
                counts["total_students"] - counts["complete_profiles"],
                0,
            )

            return DashboardMetricsResponse(
                stats={
                    "total_students": counts["total_students"],
                    "total_teachers": counts["total_teachers"],
                    "total_parents": counts["total_parents"],
                    "total_classes": counts["total_classes"],
                    "total_subjects": counts["total_subjects"],
                    "student_profiles_complete": counts["complete_profiles"],
                    "student_profiles_incomplete": incomplete_profiles,
                    "pending_teacher_accounts": counts["pending_teachers"],
                    "pending_parent_accounts": counts["pending_parents"],
                    "active_academic_session": current_session.name if current_session else None,
                    "active_academic_term": current_term.name.value if current_term else None,
                    "report_cards_generated": counts["report_cards_generated"],
                    "report_cards_published": counts["report_cards_published"],
                },
                charts={
                    "user_population_breakdown": [
                        ChartPoint(label="students", value=counts["total_students"]),
                        ChartPoint(label="teachers", value=counts["total_teachers"]),
                        ChartPoint(label="parents", value=counts["total_parents"]),
                    ],
                    "student_profile_completion_rate": [
                        ChartPoint(label="complete", value=counts["complete_profiles"]),
                        ChartPoint(label="incomplete", value=incomplete_profiles),
                    ],
                    "account_status_overview": [
                        ChartPoint(label="active_teachers", value=counts["active_teachers"]),
                        ChartPoint(label="pending_teachers", value=counts["pending_teachers"]),
                        ChartPoint(label="active_parents", value=counts["active_parents"]),
                        ChartPoint(label="pending_parents", value=counts["pending_parents"]),
                    ],
                    "announcements_by_category": [
                        ChartPoint(label=MetricsService._enum_label(row[0]), value=int(row[1]))
                        for row in category_rows
                    ],
                    "class_population": [
                        ChartPoint(label=f"{row.name} {row.arm}".strip(), value=int(row[2]))
                        for row in class_rows
                    ],
                    "grade_distribution": [
                        ChartPoint(
                            label=MetricsService._label(row[0], "Ungraded"),
                            value=int(row[1]),
                        )
                        for row in grade_rows
                    ],
                    "result_status_distribution": [
                        ChartPoint(label=MetricsService._enum_label(row[0]), value=int(row[1]))
                        for row in result_status_rows
                    ],
                    "subject_performance": [
                        ChartPoint(label=row[0] or "Subject", value=round(float(row[1] or 0), 2))
                        for row in subject_performance_rows
                    ],
                },
            )

        return await MetricsService._cached_dashboard(
            key=tenant_admin_dashboard_cache_key(tenant_id),
            fetcher=fetch_dashboard,
        )

    @staticmethod
    async def teacher_dashboard(db: AsyncSession, teacher_id: uuid.UUID, tenant_id: uuid.UUID) -> DashboardMetricsResponse:
        async def fetch_dashboard() -> DashboardMetricsResponse:
            class_rows = await MetricsRepository.teacher_class_sizes(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )
            assignment_count = await MetricsRepository.active_teacher_assignment_count(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )
            submitted_results = await MetricsRepository.submitted_result_count_for_teacher(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )
            teacher_grade_rows = await MetricsRepository.teacher_grade_counts(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )
            own_announcement_ids = await MetricsRepository.teacher_announcement_ids(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )
            read_count = await MetricsRepository.announcement_read_count(
                db,
                tenant_id=tenant_id,
                announcement_ids=own_announcement_ids,
                statuses=[AnnouncementReadStatus.READ, AnnouncementReadStatus.ACKNOWLEDGED],
            )
            ack_count = await MetricsRepository.announcement_read_count(
                db,
                tenant_id=tenant_id,
                announcement_ids=own_announcement_ids,
                statuses=[AnnouncementReadStatus.ACKNOWLEDGED],
            )
            category_rows = await MetricsRepository.teacher_announcement_category_counts(
                db,
                tenant_id=tenant_id,
                teacher_id=teacher_id,
            )

            return DashboardMetricsResponse(
                stats={
                    "total_classes": len(class_rows),
                    "assigned_subjects": assignment_count,
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
                        ChartPoint(label=MetricsService._enum_label(row[0]), value=int(row[1]))
                        for row in category_rows
                    ],
                    "grade_distribution": [
                        ChartPoint(
                            label=MetricsService._label(row[0], "Ungraded"),
                            value=int(row[1]),
                        )
                        for row in teacher_grade_rows
                    ],
                },
            )

        return await MetricsService._cached_dashboard(
            key=teacher_dashboard_cache_key(tenant_id, teacher_id),
            fetcher=fetch_dashboard,
        )

    @staticmethod
    async def _personal_announcement_metrics(
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
        parent: Parent,
    ) -> DashboardMetricsResponse:
        async def fetch_dashboard() -> DashboardMetricsResponse:
            feed_total, read_count, category_counts = await AnnouncementService.feed_summary(
                db,
                actor=parent,
            )
            return await MetricsService._personal_announcement_metrics(
                feed_total=feed_total,
                read_count=read_count,
                category_counts=category_counts,
            )

        return await MetricsService._cached_dashboard(
            key=parent_dashboard_cache_key(parent.tenant_id, parent.id),
            fetcher=fetch_dashboard,
        )

    @staticmethod
    async def student_dashboard(
        db: AsyncSession,
        student: Student,
    ) -> DashboardMetricsResponse:
        async def fetch_dashboard() -> DashboardMetricsResponse:
            feed_total, read_count, category_counts = await AnnouncementService.feed_summary(
                db,
                actor=student,
            )
            result_rows = await MetricsRepository.submitted_results_for_student(
                db,
                tenant_id=student.tenant_id,
                student_id=student.id,
            )
            average = (
                round(sum(float(row.total_score or 0) for row in result_rows) / len(result_rows), 2)
                if result_rows
                else 0
            )
            grade_counts: dict[str, int] = {}
            for row in result_rows:
                label = MetricsService._label(row.grade, "Ungraded")
                grade_counts[label] = grade_counts.get(label, 0) + 1

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
                        ChartPoint(
                            label=MetricsService._label(row.grade, "Ungraded"),
                            value=float(row.total_score or 0),
                        )
                        for row in result_rows
                    ],
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

        return await MetricsService._cached_dashboard(
            key=student_dashboard_cache_key(student.tenant_id, student.id),
            fetcher=fetch_dashboard,
        )
