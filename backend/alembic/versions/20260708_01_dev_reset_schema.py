"""dev reset schema

Revision ID: 20260708_dev_reset_schema
Revises: 20260707_normalize_legacy_plan_names
Create Date: 2026-07-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import MetaData, text

revision = "20260708_dev_reset_schema"
down_revision = "20260707_normalize_legacy_plan_names"
branch_labels = None
depends_on = None

ENUM_TYPES = [
    "userrole",
    "userstatus",
    "actor_type",
    "invitationstatus",
    "tenantstatus",
    "subscriptionplan",
    "tenantverificationstatus",
    "academicstatus",
    "gender",
    "bloodgroup",
    "parentrelationship",
    "linkstatus",
    "subjectassignmentstatus",
    "studentresultstatus",
    "reportcardstatus",
    "announcement_status",
    "announcement_priority",
    "announcement_category",
    "announcement_author_type",
    "announcement_target_type",
    "announcement_recipient_actor_type",
    "subscription_status",
    "billing_interval",
    "payment_provider",
    "payment_status",
]


def upgrade() -> None:
    bind = op.get_bind()
    metadata = MetaData()
    metadata.reflect(bind=bind, schema="public")

    for table_key in list(metadata.tables):
        table = metadata.tables[table_key]
        if table.name == "alembic_version":
            metadata.remove(table)

    metadata.drop_all(bind=bind)

    for enum_name in ENUM_TYPES:
        bind.execute(text(f'DROP TYPE IF EXISTS public."{enum_name}" CASCADE'))

    from app.modules import import_model_modules
    from app.shared.base_model import Base

    import_model_modules()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    raise RuntimeError("The dev reset migration is intentionally not reversible.")
