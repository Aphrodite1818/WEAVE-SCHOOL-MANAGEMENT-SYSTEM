"""Static lifecycle architecture verification used by CI.

This check deliberately avoids database I/O. It confirms that lifecycle models are
registered centrally and that the canonical HTTP entry points remain exposed.
"""

from __future__ import annotations

import app.models  # noqa: F401
from app.main import app
from app.shared.base_model import Base


REQUIRED_TABLES = {
    "academic_sessions",
    "academic_terms",
    "student_subject_results",
    "report_cards",
    "tenant_subscriptions",
    "subscription_plan_changes",
    "notification_deliveries",
    "school_calendars",
}

REQUIRED_ROUTES = {
    "/api/v1/subscriptions/payments",
    "/api/v1/subscriptions/plan-change",
    "/api/v1/subscriptions/cancel",
    "/api/v1/tenant-admin/academic/report-cards/bulk/publish",
    "/api/v1/tenant-admin/academics/results/bulk/transition",
    "/api/v1/teachers/academics/results/bulk/submit",
}


def main() -> None:
    registered_tables = set(Base.metadata.tables)
    normalized_tables = {name.rsplit(".", 1)[-1] for name in registered_tables}
    missing_tables = REQUIRED_TABLES - normalized_tables
    if missing_tables:
        raise SystemExit(
            f"Lifecycle models are not registered: {sorted(missing_tables)}"
        )

    route_paths = {route.path for route in app.routes}
    missing_routes = REQUIRED_ROUTES - route_paths
    if missing_routes:
        raise SystemExit(
            f"Lifecycle routes are not registered: {sorted(missing_routes)}"
        )

    plan_change_table = Base.metadata.tables.get(
        "public.subscription_plan_changes"
    ) or Base.metadata.tables.get("subscription_plan_changes")
    if plan_change_table is None:
        raise SystemExit("subscription_plan_changes table metadata is unavailable")

    index_names = {index.name for index in plan_change_table.indexes}
    if "uq_subscription_plan_changes_open_per_tenant" not in index_names:
        raise SystemExit(
            "Open plan changes are not protected by the expected unique index"
        )

    print(
        "Lifecycle architecture verified:",
        f"{len(REQUIRED_TABLES)} models,",
        f"{len(REQUIRED_ROUTES)} routes.",
    )


if __name__ == "__main__":
    main()
