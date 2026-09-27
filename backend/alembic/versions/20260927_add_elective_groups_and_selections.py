"""add elective groups and persistent student selections

Revision ID: 20260927_elective_groups
Revises: 20260911_initial_schema
Create Date: 2026-09-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260927_elective_groups"
down_revision: Union[str, Sequence[str], None] = "20260911_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CBT change rows use a PostgreSQL enum, so extending the Python enum alone is
    # not enough. Keep the database wire enum aligned before any elective-selection
    # change can be recorded.
    op.execute(
        "ALTER TYPE public.cbt_sync_entity_type "
        "ADD VALUE IF NOT EXISTS 'student_elective_selection'"
    )

    op.create_table(
        "curriculum_elective_groups",
        sa.Column("curriculum_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("minimum_choices", sa.Integer(), server_default="0", nullable=False),
        sa.Column("maximum_choices", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("minimum_choices >= 0", name="ck_elective_group_min_nonnegative"),
        sa.CheckConstraint("maximum_choices >= 1", name="ck_elective_group_max_positive"),
        sa.CheckConstraint(
            "minimum_choices <= maximum_choices", name="ck_elective_group_min_lte_max"
        ),
        sa.CheckConstraint(
            "lifecycle IN ('ACTIVE', 'ARCHIVED')", name="ck_elective_group_lifecycle"
        ),
        sa.ForeignKeyConstraint(["curriculum_id"], ["curricula.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_curriculum_elective_groups_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "curriculum_id", "name", name="uq_curriculum_elective_group_name"
        ),
    )
    op.create_index(
        "ix_curriculum_elective_groups_tenant_curriculum",
        "curriculum_elective_groups",
        ["tenant_id", "curriculum_id"],
        unique=False,
    )

    # Nullable is intentional for migration compatibility with legacy elective rows.
    # The service layer will require a group for every new/edited elective subject;
    # admins can reconcile pre-existing electives without a destructive migration.
    op.add_column(
        "curriculum_subjects",
        sa.Column("elective_group_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_curriculum_subjects_elective_group",
        "curriculum_subjects",
        "curriculum_elective_groups",
        ["elective_group_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_compulsory_subject_has_no_elective_group",
        "curriculum_subjects",
        "is_elective OR elective_group_id IS NULL",
    )
    op.create_index(
        "ix_curriculum_subjects_elective_group",
        "curriculum_subjects",
        ["tenant_id", "elective_group_id"],
        unique=False,
    )

    op.create_table(
        "student_elective_selections",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("elective_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("curriculum_subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["elective_group_id"], ["curriculum_elective_groups.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curriculum_subject_id"], ["curriculum_subjects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "curriculum_subject_id",
            name="uq_student_elective_selection_subject",
        ),
    )
    op.create_index(
        "ix_student_elective_selections_student_group",
        "student_elective_selections",
        ["tenant_id", "student_id", "elective_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_student_elective_selections_curriculum_subject",
        "student_elective_selections",
        ["tenant_id", "curriculum_subject_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_student_elective_selections_curriculum_subject",
        table_name="student_elective_selections",
    )
    op.drop_index(
        "ix_student_elective_selections_student_group", table_name="student_elective_selections"
    )
    op.drop_table("student_elective_selections")
    op.drop_index("ix_curriculum_subjects_elective_group", table_name="curriculum_subjects")
    op.drop_constraint(
        "ck_compulsory_subject_has_no_elective_group", "curriculum_subjects", type_="check"
    )
    op.drop_constraint(
        "fk_curriculum_subjects_elective_group", "curriculum_subjects", type_="foreignkey"
    )
    op.drop_column("curriculum_subjects", "elective_group_id")
    op.drop_index(
        "ix_curriculum_elective_groups_tenant_curriculum", table_name="curriculum_elective_groups"
    )
    op.drop_table("curriculum_elective_groups")

    # PostgreSQL enum values cannot be removed safely in-place. Leaving the additive
    # wire value behind makes downgrade non-destructive for any retained sync rows;
    # a later full type rebuild can remove it if the deployment explicitly requires it.
