"""Normalize departments into a tenant-wide pool with per-level mappings.

Revision ID: 20260901_global_departments
Revises: academic_session_hardening
Create Date: 2026-09-01

This is an intentional pre-production contract cutover. Department identities are
canonical per tenant. Per-level lifecycle and every operational specialization
reference move to academic_level_departments.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260901_global_departments"
down_revision: Union[str, Sequence[str], None] = "academic_session_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.create_table(
        "academic_level_departments",
        sa.Column("academic_level_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["academic_level_id"], [f"{SCHEMA}.academic_levels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], [f"{SCHEMA}.departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["archived_by_admin_id"], [f"{SCHEMA}.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "academic_level_id", "department_id",
            name="uq_academic_level_departments_scope",
        ),
        sa.CheckConstraint(
            "(archived_at IS NULL AND archived_by_admin_id IS NULL) OR "
            "(archived_at IS NOT NULL AND is_active = false)",
            name="ck_academic_level_departments_archive_metadata",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_level_departments_tenant_level",
        "academic_level_departments",
        ["tenant_id", "academic_level_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_level_departments_tenant_department",
        "academic_level_departments",
        ["tenant_id", "department_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_level_departments_tenant_level_active",
        "academic_level_departments",
        ["tenant_id", "academic_level_id", "is_active"],
        schema=SCHEMA,
    )

    # One link is created for every old level-owned Department before canonical
    # duplicates are merged. Its UUID becomes the operational specialization ID.
    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.academic_level_departments
                (id, tenant_id, academic_level_id, department_id, is_active,
                 archived_at, archived_by_admin_id, created_at, updated_at)
            SELECT gen_random_uuid(), tenant_id, academic_level_id, id, is_active,
                   archived_at, archived_by_admin_id, created_at, updated_at
            FROM {SCHEMA}.departments
            """
        )
    )

    op.add_column(
        "class_term_department_assignments",
        sa.Column("academic_level_department_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "curriculum_offerings",
        sa.Column("academic_level_department_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema=SCHEMA,
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.class_term_department_assignments ctd
            SET academic_level_department_id = ald.id
            FROM {SCHEMA}.academic_level_departments ald
            WHERE ald.tenant_id = ctd.tenant_id
              AND ald.department_id = ctd.department_id
              AND ald.academic_level_id = (
                  SELECT c.academic_level_id FROM {SCHEMA}.classes c WHERE c.id = ctd.class_id
              )
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.curriculum_offerings co
            SET academic_level_department_id = ald.id
            FROM {SCHEMA}.academic_level_departments ald
            WHERE co.department_id IS NOT NULL
              AND ald.tenant_id = co.tenant_id
              AND ald.department_id = co.department_id
            """
        )
    )

    # Merge same-name canonical rows per tenant. Level links retain the old
    # per-level lifecycle but point at the deterministic lowest UUID survivor.
    op.execute(
        sa.text(
            f"""
            WITH survivors AS (
                SELECT tenant_id, normalized_name, MIN(id::text)::uuid AS survivor_id
                FROM {SCHEMA}.departments
                GROUP BY tenant_id, normalized_name
            )
            UPDATE {SCHEMA}.academic_level_departments ald
            SET department_id = s.survivor_id
            FROM {SCHEMA}.departments d
            JOIN survivors s
              ON s.tenant_id = d.tenant_id
             AND s.normalized_name = d.normalized_name
            WHERE ald.department_id = d.id
              AND ald.department_id <> s.survivor_id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            WITH survivors AS (
                SELECT tenant_id, normalized_name, MIN(id::text)::uuid AS survivor_id
                FROM {SCHEMA}.departments
                GROUP BY tenant_id, normalized_name
            )
            DELETE FROM {SCHEMA}.departments d
            USING survivors s
            WHERE d.tenant_id = s.tenant_id
              AND d.normalized_name = s.normalized_name
              AND d.id <> s.survivor_id
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.departments d
            SET is_active = EXISTS (
                    SELECT 1 FROM {SCHEMA}.academic_level_departments ald
                    WHERE ald.tenant_id = d.tenant_id
                      AND ald.department_id = d.id
                      AND ald.is_active = true
                      AND ald.archived_at IS NULL
                ),
                archived_at = NULL,
                archived_by_admin_id = NULL
            """
        )
    )

    op.alter_column(
        "class_term_department_assignments",
        "academic_level_department_id",
        nullable=False,
        schema=SCHEMA,
    )
    op.create_foreign_key(
        "fk_ctd_academic_level_department",
        "class_term_department_assignments",
        "academic_level_departments",
        ["academic_level_department_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_curriculum_offering_level_department",
        "curriculum_offerings",
        "academic_level_departments",
        ["academic_level_department_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_class_term_department_tenant_level_department",
        "class_term_department_assignments",
        ["tenant_id", "academic_level_department_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_curriculum_offerings_tenant_level_department",
        "curriculum_offerings",
        ["tenant_id", "academic_level_department_id"],
        schema=SCHEMA,
    )

    # Existing constraints/indexes reference the old department_id columns.
    op.drop_constraint(
        "uq_curriculum_offering_scope", "curriculum_offerings", schema=SCHEMA, type_="unique"
    )
    op.drop_index("uq_curriculum_offering_general_scope", table_name="curriculum_offerings", schema=SCHEMA)
    op.create_unique_constraint(
        "uq_curriculum_offering_scope",
        "curriculum_offerings",
        ["tenant_id", "curriculum_subject_id", "academic_term_id", "academic_level_department_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_curriculum_offering_general_scope",
        "curriculum_offerings",
        ["tenant_id", "curriculum_subject_id", "academic_term_id"],
        unique=True,
        postgresql_where=sa.text("academic_level_department_id IS NULL"),
        schema=SCHEMA,
    )

    op.drop_column("class_term_department_assignments", "department_id", schema=SCHEMA)
    op.drop_column("curriculum_offerings", "department_id", schema=SCHEMA)

    op.drop_constraint("uq_departments_tenant_level_name", "departments", schema=SCHEMA, type_="unique")
    op.drop_index("ix_departments_tenant_level_active", table_name="departments", schema=SCHEMA)
    # academic_level_id was declared index=True before the composite indexes,
    # but older local databases may already be missing this redundant index.
    op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.ix_departments_academic_level_id")
    op.drop_column("departments", "academic_level_id", schema=SCHEMA)
    op.create_unique_constraint(
        "uq_departments_tenant_name", "departments", ["tenant_id", "normalized_name"], schema=SCHEMA
    )
    op.create_index("ix_departments_tenant_active", "departments", ["tenant_id", "is_active"], schema=SCHEMA)
    op.create_index("ix_departments_tenant_archived", "departments", ["tenant_id", "archived_at"], schema=SCHEMA)


def downgrade() -> None:
    raise RuntimeError(
        "20260901_global_departments is a deliberate pre-production contract cutover and is not reversible."
    )
