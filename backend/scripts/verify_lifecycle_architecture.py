"""Static lifecycle architecture verification used by CI.

This check deliberately avoids database I/O. It confirms that lifecycle models are
registered centrally and that the canonical HTTP entry points remain exposed.
"""

from __future__ import annotations

import app.models  # noqa: F401
from app.main import app
from app.modules.communications.models import NotificationDelivery
from app.modules.report_cards.models import ReportCard
from app.modules.school_calendar.models import SchoolCalendar
from app.modules.student_academics.models import (
    AcademicSession,
    AcademicTerm,
    StudentSubjectResult,
)
from app.modules.subscriptions.models import (
    SubscriptionPlanChange,
    TenantSubscription,
)
from app.shared.base_model import Base


REQUIRED_MODELS = (
    AcademicSession,
    AcademicTerm,
    StudentSubjectResult,
    ReportCard,
    TenantSubscription,
    SubscriptionPlanChange,
    NotificationDelivery,
    SchoolCalendar,
)

REQUIRED_ROUTES = {
    "/api/v1/subscriptions/payments",
    "/api/v1/subscriptions/plan-change",
    "/api/v1/subscriptions/cancel",
    "/api/v1/tenant-admin/academic/report-cards/bulk/publish",
    "/api/v1/tenant-admin/academics/results/bulk/transition",
    "/api/v1/teachers/academics/results/bulk/submit",
}


def main() -> None:
    unregistered_models = [
        model.__name__
        for model in REQUIRED_MODELS
        if model.__table__.metadata is not Base.metadata
    ]
    if unregistered_models:
        raise SystemExit(
            f"Lifecycle models are not centrally registered: {unregistered_models}"
        )

    route_paths = {route.path for route in app.routes}
    missing_routes = REQUIRED_ROUTES - route_paths
    if missing_routes:
        raise SystemExit(f"Lifecycle routes are not registered: {sorted(missing_routes)}")

    index_names = {index.name for index in SubscriptionPlanChange.__table__.indexes}
    if "uq_subscription_plan_changes_open_per_tenant" not in index_names:
        raise SystemExit("Open plan changes are not protected by the expected unique index")

    print(
        "Lifecycle architecture verified:",
        f"{len(REQUIRED_MODELS)} models,",
        f"{len(REQUIRED_ROUTES)} routes.",
    )


if __name__ == "__main__":
    main()
