"""Regression checks for the fresh Alembic schema baseline."""

from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.shared.base_model import Base

CRITICAL_TABLES = {
    "tenants",
    "tenant_admins",
    "teacher_accounts",
    "teacher_memberships",
    "parent_accounts",
    "parent_memberships",
    "students",
    "auth_identities",
    "auth_sessions",
    "auth_refresh_tokens",
    "media_assets",
    "platform_controls",
    "security_ip_blocks",
    "email_outbox",
    "import_jobs",
    "academic_levels",
    "progression_selection_options",
    "classes",
    "level_subjects",
    "teacher_assignments",
    "academic_sessions",
    "academic_terms",
    "assessment_schemes",
    "assessment_components",
    "student_subject_results",
    "tenant_subscriptions",
    "payment_transactions",
    "term_plan_entitlements",
    "payment_webhook_events",
}


def test_model_registry_contains_critical_fresh_schema_tables() -> None:
    """Ensure the baseline imports every critical SQLAlchemy model module."""

    configure_mappers()
    registered_table_names = {table.name for table in Base.metadata.tables.values()}
    missing_tables = CRITICAL_TABLES - registered_table_names
    assert not missing_tables, (
        "The fresh migration baseline is missing registered model tables: "
        f"{sorted(missing_tables)}"
    )


def test_model_registry_has_unique_table_keys() -> None:
    """Guard against duplicate table registrations before migration execution."""

    configure_mappers()
    table_keys = list(Base.metadata.tables)
    assert len(table_keys) == len(set(table_keys))
