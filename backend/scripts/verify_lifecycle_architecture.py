"""Static lifecycle architecture verification used by CI.

This check deliberately avoids database I/O. It confirms that lifecycle models are
registered centrally and that the canonical HTTP entry points remain exposed.
"""

from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
    PaymentTransaction,
    TermPlanEntitlement,
    TenantSubscription,
)
from app.shared.base_model import Base


REQUIRED_MODELS = (
    AcademicSession,
    AcademicTerm,
    StudentSubjectResult,
    ReportCard,
    TenantSubscription,
    PaymentTransaction,
    TermPlanEntitlement,
    NotificationDelivery,
    SchoolCalendar,
)

REQUIRED_ROUTES = {
    "/api/v1/subscriptions/payments",
    "/api/v1/subscriptions/terms/activate-free",
    "/api/v1/subscriptions/terms/checkout",
    "/api/v1/subscriptions/terms/verify/{reference}",
    "/api/v1/tenant-admin/academic/report-cards/bulk/publish",
    "/api/v1/tenant-admin/academics/results/bulk/transition",
}

FORBIDDEN_LEGACY_ROUTES = {
    "/api/v1/subscriptions/plan-change",
    "/api/v1/subscriptions/cancel",
    "/api/v1/teachers/academics/results/bulk/submit",
    "/api/v1/tenant-admin/academics/results/bulk/submit",
}

REQUIRED_INDEXES = {
    TenantSubscription: {
        "uq_tenant_subscriptions_current_per_tenant",
        "ix_tenant_subscriptions_tenant_current",
    },
    PaymentTransaction: {
        "uq_payment_transactions_pending_term",
        "ix_payment_transactions_tenant_term",
    },
    TermPlanEntitlement: {
        "uq_term_entitlements_active_term",
        "uq_term_entitlements_payment_transaction",
        "ix_term_entitlements_tenant_term",
    },
}


def main() -> None:
    unregistered_models = [
        model.__name__ for model in REQUIRED_MODELS if model.__table__.metadata is not Base.metadata
    ]
    if unregistered_models:
        raise SystemExit(f"Lifecycle models are not centrally registered: {unregistered_models}")

    route_paths = {route.path for route in app.routes}
    missing_routes = REQUIRED_ROUTES - route_paths
    if missing_routes:
        raise SystemExit(f"Lifecycle routes are not registered: {sorted(missing_routes)}")

    surviving_legacy_routes = FORBIDDEN_LEGACY_ROUTES & route_paths
    if surviving_legacy_routes:
        raise SystemExit(
            f"Obsolete lifecycle routes are still registered: {sorted(surviving_legacy_routes)}"
        )

    missing_indexes: list[str] = []
    for model, required_names in REQUIRED_INDEXES.items():
        actual_names = {index.name for index in model.__table__.indexes}
        for name in sorted(required_names - actual_names):
            missing_indexes.append(f"{model.__tablename__}.{name}")
    if missing_indexes:
        raise SystemExit(f"Lifecycle database guards are missing: {missing_indexes}")

    print(
        "Lifecycle architecture verified:",
        f"{len(REQUIRED_MODELS)} models,",
        f"{len(REQUIRED_ROUTES)} routes,",
        f"{sum(len(names) for names in REQUIRED_INDEXES.values())} indexes.",
    )


if __name__ == "__main__":
    main()
