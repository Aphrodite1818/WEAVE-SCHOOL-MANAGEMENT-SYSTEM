"""Regression checks for the fresh Alembic schema baseline."""

from sqlalchemy.orm import configure_mappers

from app.modules import import_model_modules
from app.shared.base_model import Base


CRITICAL_TABLES = {
    "tenants",
    "tenant_admins",
    "teachers",
    "parents",
    "students",
    "auth_identities",
    "auth_sessions",
    "auth_refresh_tokens",
    "media_assets",
    "platform_controls",
    "security_ip_blocks",
    "email_outbox",
    "import_jobs",
}


def test_model_registry_contains_critical_fresh_schema_tables() -> None:
    """Ensure the baseline imports every critical SQLAlchemy model module."""

    import_model_modules()
    configure_mappers()

    registered_table_names = {table.name for table in Base.metadata.tables.values()}
    missing_tables = CRITICAL_TABLES - registered_table_names

    assert not missing_tables, (
        "The fresh migration baseline is missing registered model tables: "
        f"{sorted(missing_tables)}"
    )


def test_model_registry_has_unique_table_keys() -> None:
    """Guard against duplicate table registrations before migration execution."""

    import_model_modules()
    configure_mappers()

    table_keys = list(Base.metadata.tables)
    assert len(table_keys) == len(set(table_keys))
