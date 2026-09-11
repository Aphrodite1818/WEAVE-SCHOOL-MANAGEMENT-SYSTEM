"""Introduce institution-aware structure fields and durable CBT sync tables.

Revision ID: 20260817_academic_cbt_sync
Revises: 20260815_arm_label_repair
Create Date: 2026-08-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260817_academic_cbt_sync"
down_revision = "20260815_arm_label_repair"
branch_labels = None
depends_on = None
SCHEMA = "public"


def upgrade() -> None:
    op.execute(
        "ALTER TYPE public.academic_category ADD VALUE IF NOT EXISTS 'NURSERY' AFTER 'KINDERGARTEN'"
    )

    # The application no longer reads the legacy specialization/class-department
    # fields. Keeping the physical columns for this development migration makes
    # the upgrade safe to run on any existing staging fixture; the next fresh
    # schema baseline can omit them entirely.
    op.add_column(
        "departments", sa.Column("academic_level_id", sa.UUID(), nullable=True), schema=SCHEMA
    )
    op.create_foreign_key(
        "fk_departments_academic_level",
        "departments",
        "academic_levels",
        ["academic_level_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_departments_tenant_level_active",
        "departments",
        ["tenant_id", "academic_level_id", "is_active"],
        schema=SCHEMA,
    )

    sync_operation = postgresql.ENUM(
        "created", "updated", "deleted", name="cbt_sync_operation", schema=SCHEMA
    )
    sync_entity = postgresql.ENUM(
        "academic_level",
        "department",
        "arm_label",
        "class",
        "class_term_department",
        "academic_session",
        "academic_term",
        "subject",
        "curriculum",
        "curriculum_subject",
        "subject_offering",
        "assessment_scheme",
        "assessment_component",
        "teacher",
        "teacher_assignment",
        "student_enrollment",
        name="cbt_sync_entity_type",
        schema=SCHEMA,
    )
    sync_operation.create(op.get_bind(), checkfirst=True)
    sync_entity.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cbt_sync_tenant_states",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("last_cursor", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
        schema=SCHEMA,
    )
    op.create_table(
        "cbt_sync_changes",
        sa.Column("cursor", sa.BigInteger(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column(
            "entity_type",
            postgresql.ENUM(
                "academic_level",
                "department",
                "arm_label",
                "class",
                "class_term_department",
                "academic_session",
                "academic_term",
                "subject",
                "curriculum",
                "curriculum_subject",
                "subject_offering",
                "assessment_scheme",
                "assessment_component",
                "teacher",
                "teacher_assignment",
                "student_enrollment",
                name="cbt_sync_entity_type",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "operation",
            postgresql.ENUM(
                "created",
                "updated",
                "deleted",
                name="cbt_sync_operation",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="2", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", "cursor", name="uq_cbt_sync_changes_tenant_cursor"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cbt_sync_changes_tenant_entity",
        "cbt_sync_changes",
        ["tenant_id", "entity_type", "entity_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_cbt_sync_changes_created_at", "cbt_sync_changes", ["created_at"], schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index("ix_cbt_sync_changes_created_at", table_name="cbt_sync_changes", schema=SCHEMA)
    op.drop_index("ix_cbt_sync_changes_tenant_entity", table_name="cbt_sync_changes", schema=SCHEMA)
    op.drop_table("cbt_sync_changes", schema=SCHEMA)
    op.drop_table("cbt_sync_tenant_states", schema=SCHEMA)
    postgresql.ENUM(name="cbt_sync_entity_type", schema=SCHEMA).drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="cbt_sync_operation", schema=SCHEMA).drop(op.get_bind(), checkfirst=True)
    op.drop_index("ix_departments_tenant_level_active", table_name="departments", schema=SCHEMA)
    op.drop_constraint(
        "fk_departments_academic_level", "departments", type_="foreignkey", schema=SCHEMA
    )
    op.drop_column("departments", "academic_level_id", schema=SCHEMA)
