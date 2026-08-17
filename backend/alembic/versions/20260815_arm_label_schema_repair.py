"""Repair arm label schema for databases already stamped past hierarchy.

Revision ID: 20260815_arm_label_repair
Revises: 20260815_offering_backfill
Create Date: 2026-08-15
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260815_arm_label_repair"
down_revision = "20260815_offering_backfill"
branch_labels = None
depends_on = None

SCHEMA = "public"

OFFLINE_TABLE_NAMES = {"arm_labels", "classes"}
OFFLINE_COLUMN_NAMES = {
    "classes": {"arm_label_id"},
}
OFFLINE_CONSTRAINT_NAMES = {
    "classes": {"fk_classes_arm_label_id"},
}
OFFLINE_INDEX_NAMES = {
    "arm_labels": {"ix_arm_labels_tenant_active", "ix_arm_labels_tenant_position"},
    "classes": {"ix_classes_tenant_arm_label", "uq_classes_tenant_level_department_arm"},
}


def _table_names() -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_TABLE_NAMES
    return set(sa.inspect(op.get_bind()).get_table_names(schema=SCHEMA))


def _column_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_COLUMN_NAMES.get(table_name, set())
    if table_name not in _table_names():
        return set()
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=SCHEMA)
    }


def _constraint_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_CONSTRAINT_NAMES.get(table_name, set())
    if table_name not in _table_names():
        return set()
    inspector = sa.inspect(op.get_bind())
    names = {
        item.get("name")
        for item in inspector.get_unique_constraints(table_name, schema=SCHEMA)
    }
    names.update(
        item.get("name")
        for item in inspector.get_foreign_keys(table_name, schema=SCHEMA)
    )
    names.update(
        item.get("name")
        for item in inspector.get_check_constraints(table_name, schema=SCHEMA)
    )
    return {name for name in names if name}


def _index_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_INDEX_NAMES.get(table_name, set())
    if table_name not in _table_names():
        return set()
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes(table_name, schema=SCHEMA)
    }


def _drop_constraint_if_exists(table_name: str, constraint_name: str, type_: str) -> None:
    if constraint_name in _constraint_names(table_name):
        op.drop_constraint(constraint_name, table_name, type_=type_, schema=SCHEMA)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name, schema=SCHEMA)


def upgrade() -> None:
    if "arm_labels" not in _table_names():
        op.create_table(
            "arm_labels",
            sa.Column("label", sa.String(20), nullable=False),
            sa.Column("normalized_label", sa.String(40), nullable=False),
            sa.Column("position", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "position IS NULL OR position > 0",
                name="ck_arm_labels_position_positive",
            ),
            sa.CheckConstraint(
                "archived_at IS NULL OR is_active = false",
                name="ck_arm_labels_archived_requires_inactive",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id",
                "normalized_label",
                name="uq_arm_labels_tenant_label",
            ),
            schema=SCHEMA,
        )
    if "ix_arm_labels_tenant_active" not in _index_names("arm_labels"):
        op.create_index(
            "ix_arm_labels_tenant_active",
            "arm_labels",
            ["tenant_id", "is_active"],
            schema=SCHEMA,
        )
    if "ix_arm_labels_tenant_position" not in _index_names("arm_labels"):
        op.create_index(
            "ix_arm_labels_tenant_position",
            "arm_labels",
            ["tenant_id", "position"],
            schema=SCHEMA,
        )

    class_columns = _column_names("classes")
    if "arm_label_id" not in class_columns:
        op.add_column("classes", sa.Column("arm_label_id", sa.UUID()), schema=SCHEMA)
        class_columns.add("arm_label_id")

    if {"arm", "normalized_arm"}.issubset(class_columns):
        op.execute(
            """
            INSERT INTO public.arm_labels (
                tenant_id, id, label, normalized_label, position, is_active, created_at, updated_at
            )
            SELECT
                tenant_id,
                md5(tenant_id::text || ':arm:' || normalized_arm)::uuid,
                MIN(arm),
                normalized_arm,
                NULL,
                TRUE,
                now(),
                now()
            FROM public.classes
            WHERE normalized_arm IS NOT NULL
            GROUP BY tenant_id, normalized_arm
            ON CONFLICT DO NOTHING
            """
        )
        op.execute(
            """
            UPDATE public.classes AS class
            SET arm_label_id = arm_label.id
            FROM public.arm_labels AS arm_label
            WHERE arm_label.tenant_id = class.tenant_id
              AND arm_label.normalized_label = class.normalized_arm
            """
        )

    if "fk_classes_arm_label_id" not in _constraint_names("classes"):
        op.create_foreign_key(
            "fk_classes_arm_label_id",
            "classes",
            "arm_labels",
            ["arm_label_id"],
            ["id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="RESTRICT",
        )

    _drop_constraint_if_exists("classes", "uq_classes_tenant_level_arm", "unique")
    _drop_index_if_exists("classes", "uq_classes_tenant_level_department_arm")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_level_department_arm
        ON public.classes (
            tenant_id,
            academic_level_id,
            COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid),
            COALESCE(arm_label_id, '00000000-0000-0000-0000-000000000000'::uuid)
        )
        """
    )
    if "ix_classes_tenant_arm_label" not in _index_names("classes"):
        op.create_index(
            "ix_classes_tenant_arm_label",
            "classes",
            ["tenant_id", "arm_label_id"],
            schema=SCHEMA,
        )

    for column_name in ("normalized_arm", "arm"):
        if column_name in _column_names("classes"):
            op.drop_column("classes", column_name, schema=SCHEMA)


def downgrade() -> None:
    if "classes" in _table_names():
        _drop_index_if_exists("classes", "ix_classes_tenant_arm_label")
        _drop_index_if_exists("classes", "uq_classes_tenant_level_department_arm")
        _drop_constraint_if_exists("classes", "fk_classes_arm_label_id", "foreignkey")
        if "arm_label_id" in _column_names("classes"):
            op.drop_column("classes", "arm_label_id", schema=SCHEMA)

    if "arm_labels" in _table_names():
        _drop_index_if_exists("arm_labels", "ix_arm_labels_tenant_position")
        _drop_index_if_exists("arm_labels", "ix_arm_labels_tenant_active")
        op.drop_table("arm_labels", schema=SCHEMA)
