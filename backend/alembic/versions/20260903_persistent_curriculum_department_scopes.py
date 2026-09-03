"""Replace term subject offerings with persistent curriculum department scopes.

Revision ID: 20260903_curriculum_scopes
Revises: 20260901_global_departments
Create Date: 2026-09-03

This is an intentional pre-production contract cutover. Curriculum subject
applicability is persistent; terms no longer own subject offerings.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260903_curriculum_scopes"
down_revision: Union[str, Sequence[str], None] = "20260901_global_departments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.create_table(
        "curriculum_subject_departments",
        sa.Column("curriculum_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_level_department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["curriculum_subject_id"],
            [f"{SCHEMA}.curriculum_subjects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["academic_level_department_id"],
            [f"{SCHEMA}.academic_level_departments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], [f"{SCHEMA}.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "curriculum_subject_id",
            "academic_level_department_id",
            name="uq_curriculum_subject_department_scope",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_curriculum_subject_departments_tenant_subject",
        "curriculum_subject_departments",
        ["tenant_id", "curriculum_subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_curriculum_subject_departments_tenant_level_department",
        "curriculum_subject_departments",
        ["tenant_id", "academic_level_department_id"],
        schema=SCHEMA,
    )

    # Collapse repeated term-specific specialized offerings into one persistent
    # curriculum-subject/level-department relationship. General offerings become
    # the absence of a row in the new table.
    op.execute(
        sa.text(
            f"""
            INSERT INTO {SCHEMA}.curriculum_subject_departments
                (id, tenant_id, curriculum_subject_id,
                 academic_level_department_id, created_at, updated_at)
            SELECT DISTINCT ON (
                    tenant_id,
                    curriculum_subject_id,
                    academic_level_department_id
                )
                id,
                tenant_id,
                curriculum_subject_id,
                academic_level_department_id,
                created_at,
                updated_at
            FROM {SCHEMA}.curriculum_offerings
            WHERE academic_level_department_id IS NOT NULL
            ORDER BY
                tenant_id,
                curriculum_subject_id,
                academic_level_department_id,
                created_at,
                id
            """
        )
    )

    op.drop_table("curriculum_offerings", schema=SCHEMA)

    # Normalize the specialization policy before enforcing the new invariant.
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.academic_levels
            SET specialization_required_from_term_position = NULL
            WHERE category <> 'SENIOR_SECONDARY'
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.academic_levels
            SET specialization_required_from_term_position = 2
            WHERE category = 'SENIOR_SECONDARY'
              AND position = 1
              AND specialization_required_from_term_position IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            f"""
            UPDATE {SCHEMA}.academic_levels
            SET specialization_required_from_term_position = 1
            WHERE category = 'SENIOR_SECONDARY'
              AND position > 1
            """
        )
    )
    op.create_check_constraint(
        "ck_academic_levels_specialization_policy",
        "academic_levels",
        """
        (category <> 'SENIOR_SECONDARY'
            AND specialization_required_from_term_position IS NULL)
        OR
        (category = 'SENIOR_SECONDARY' AND (
            (position = 1
                AND specialization_required_from_term_position BETWEEN 1 AND 3)
            OR
            (position > 1
                AND specialization_required_from_term_position = 1)
        ))
        """,
        schema=SCHEMA,
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260903_curriculum_scopes is an intentional pre-production semantic cutover "
        "and cannot reconstruct removed term-specific curriculum offerings."
    )
