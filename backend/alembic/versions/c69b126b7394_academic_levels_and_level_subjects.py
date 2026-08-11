"""Replace class-scoped curriculum with academic levels and level subjects.

Revision ID: c69b126b7394
Revises: 20260810_dynamic_assessments
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c69b126b7394"
down_revision: Union[str, Sequence[str], None] = "20260810_dynamic_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_levels",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("next_level_id", sa.UUID(), nullable=True),
        sa.Column("is_terminal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "next_level_id IS NULL OR next_level_id <> id", name="ck_academic_levels_next_not_self"
        ),
        sa.CheckConstraint(
            "(is_terminal = true AND next_level_id IS NULL) OR is_terminal = false",
            name="ck_academic_levels_terminal_has_no_next",
        ),
        sa.CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_academic_levels_archived_requires_inactive",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.ForeignKeyConstraint(
            ["archived_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["next_level_id"], ["public.academic_levels.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "normalized_name", name="uq_academic_levels_tenant_normalized_name"
        ),
        schema="public",
    )
    op.create_index(
        "ix_academic_levels_tenant_active",
        "academic_levels",
        ["tenant_id", "is_active"],
        schema="public",
    )
    op.create_index(
        "ix_academic_levels_tenant_archived",
        "academic_levels",
        ["tenant_id", "archived_at"],
        schema="public",
    )
    op.create_index(
        "ix_academic_levels_tenant_next",
        "academic_levels",
        ["tenant_id", "next_level_id"],
        schema="public",
    )

    op.execute(
        sa.text("""
        INSERT INTO public.academic_levels
            (id, tenant_id, name, normalized_name, is_active, archived_at,
             archived_by_admin_id, is_terminal, created_at, updated_at)
        SELECT gen_random_uuid(), tenant_id, min(name), normalized_name,
               bool_or(is_active),
               CASE WHEN bool_or(is_active) THEN NULL ELSE max(archived_at) END,
               NULL::uuid,
               bool_or(is_terminal), min(created_at), max(updated_at)
        FROM public.classes
        GROUP BY tenant_id, normalized_name
    """)
    )

    op.add_column(
        "classes", sa.Column("academic_level_id", sa.UUID(), nullable=True), schema="public"
    )
    op.execute(
        sa.text("""
        UPDATE public.classes AS c
        SET academic_level_id = l.id,
            arm = COALESCE(NULLIF(BTRIM(c.arm), ''), 'DEFAULT'),
            normalized_arm = COALESCE(NULLIF(BTRIM(c.normalized_arm), ''), 'DEFAULT')
        FROM public.academic_levels AS l
        WHERE l.tenant_id = c.tenant_id AND l.normalized_name = c.normalized_name
    """)
    )
    op.alter_column("classes", "academic_level_id", nullable=False, schema="public")
    op.alter_column("classes", "arm", nullable=False, schema="public")
    op.drop_index("ix_classes_tenant_next_class", table_name="classes", schema="public")
    op.drop_index("ix_classes_tenant_terminal_active", table_name="classes", schema="public")
    op.drop_constraint(
        "uq_classes_tenant_normalized_name_arm", "classes", schema="public", type_="unique"
    )
    op.drop_constraint("classes_next_class_id_fkey", "classes", schema="public", type_="foreignkey")
    op.create_foreign_key(
        "fk_classes_academic_level",
        "classes",
        "academic_levels",
        ["academic_level_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_classes_tenant_level", "classes", ["tenant_id", "academic_level_id"], schema="public"
    )
    op.create_unique_constraint(
        "uq_classes_tenant_level_arm",
        "classes",
        ["tenant_id", "academic_level_id", "normalized_arm"],
        schema="public",
    )

    op.create_table(
        "level_subjects",
        sa.Column("academic_level_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("is_core", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by_admin_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_level_subjects_archived_requires_inactive",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.ForeignKeyConstraint(
            ["academic_level_id"], ["public.academic_levels.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["public.subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["archived_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "academic_level_id",
            "subject_id",
            name="uq_level_subject_tenant_level_subject",
        ),
        schema="public",
    )
    op.create_index(
        "ix_level_subjects_tenant_archived",
        "level_subjects",
        ["tenant_id", "archived_at"],
        schema="public",
    )
    op.execute(
        sa.text("""
        INSERT INTO public.level_subjects
            (id, tenant_id, academic_level_id, subject_id, is_core, is_active,
             archived_at, archived_by_admin_id, created_at, updated_at)
        SELECT gen_random_uuid(), cs.tenant_id, c.academic_level_id, cs.subject_id,
               bool_or(cs.is_core), bool_or(cs.is_active),
               CASE WHEN bool_or(cs.is_active) THEN NULL ELSE max(cs.archived_at) END,
               NULL::uuid,
               min(cs.created_at), max(cs.updated_at)
        FROM public.class_subjects cs
        JOIN public.classes c ON c.id = cs.class_id
        GROUP BY cs.tenant_id, c.academic_level_id, cs.subject_id
    """)
    )

    op.add_column(
        "teacher_assignments", sa.Column("class_id", sa.UUID(), nullable=True), schema="public"
    )
    op.add_column(
        "teacher_assignments",
        sa.Column("level_subject_id", sa.UUID(), nullable=True),
        schema="public",
    )
    op.execute(
        sa.text("""
        UPDATE public.teacher_assignments ta
        SET class_id = cs.class_id, level_subject_id = ls.id
        FROM public.class_subjects cs
        JOIN public.classes c ON c.id = cs.class_id
        JOIN public.level_subjects ls
          ON ls.tenant_id = cs.tenant_id
         AND ls.academic_level_id = c.academic_level_id
         AND ls.subject_id = cs.subject_id
        WHERE ta.class_subject_id = cs.id
    """)
    )
    op.alter_column("teacher_assignments", "class_id", nullable=False, schema="public")
    op.alter_column("teacher_assignments", "level_subject_id", nullable=False, schema="public")
    op.drop_index(
        "uq_teacher_assignment_active_class_subject",
        table_name="teacher_assignments",
        schema="public",
    )
    op.drop_constraint(
        "teacher_assignments_class_subject_id_fkey",
        "teacher_assignments",
        schema="public",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_teacher_assignments_class",
        "teacher_assignments",
        "classes",
        ["class_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_teacher_assignments_level_subject",
        "teacher_assignments",
        "level_subjects",
        ["level_subject_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_teacher_assignment_active_class_level_subject",
        "teacher_assignments",
        ["class_id", "level_subject_id"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("is_active = true"),
    )

    op.add_column(
        "teacher_assignment_lifecycle_audits",
        sa.Column("class_id", sa.UUID(), nullable=True),
        schema="public",
    )
    op.add_column(
        "teacher_assignment_lifecycle_audits",
        sa.Column("level_subject_id", sa.UUID(), nullable=True),
        schema="public",
    )
    op.execute(
        sa.text("""
        UPDATE public.teacher_assignment_lifecycle_audits a
        SET class_id = cs.class_id, level_subject_id = ls.id
        FROM public.class_subjects cs
        JOIN public.classes c ON c.id = cs.class_id
        JOIN public.level_subjects ls
          ON ls.tenant_id = cs.tenant_id
         AND ls.academic_level_id = c.academic_level_id
         AND ls.subject_id = cs.subject_id
        WHERE a.class_subject_id = cs.id
    """)
    )
    op.alter_column(
        "teacher_assignment_lifecycle_audits", "class_id", nullable=False, schema="public"
    )
    op.alter_column(
        "teacher_assignment_lifecycle_audits", "level_subject_id", nullable=False, schema="public"
    )
    op.drop_index(
        "ix_teacher_assignment_lifecycle_audits_tenant_class_subject",
        table_name="teacher_assignment_lifecycle_audits",
        schema="public",
    )
    op.drop_constraint(
        "teacher_assignment_lifecycle_audits_class_subject_id_fkey",
        "teacher_assignment_lifecycle_audits",
        schema="public",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_teacher_assignment_audits_class",
        "teacher_assignment_lifecycle_audits",
        "classes",
        ["class_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_teacher_assignment_audits_level_subject",
        "teacher_assignment_lifecycle_audits",
        "level_subjects",
        ["level_subject_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_teacher_assignment_audits_tenant_class_level_subject",
        "teacher_assignment_lifecycle_audits",
        ["tenant_id", "class_id", "level_subject_id"],
        schema="public",
    )

    op.add_column(
        "student_subject_results",
        sa.Column("level_subject_id", sa.UUID(), nullable=True),
        schema="public",
    )
    op.execute(
        sa.text("DELETE FROM public.student_subject_results WHERE teacher_assignment_id IS NULL")
    )
    op.execute(
        sa.text("""
        UPDATE public.student_subject_results r
        SET level_subject_id = ta.level_subject_id
        FROM public.teacher_assignments ta
        WHERE r.teacher_assignment_id = ta.id
    """)
    )
    op.alter_column("student_subject_results", "level_subject_id", nullable=False, schema="public")
    op.alter_column(
        "student_subject_results", "teacher_assignment_id", nullable=False, schema="public"
    )
    op.drop_constraint(
        "uq_student_subject_result_scope",
        "student_subject_results",
        schema="public",
        type_="unique",
    )
    op.drop_constraint(
        "student_subject_results_class_subject_teacher_id_fkey",
        "student_subject_results",
        schema="public",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_student_results_level_subject",
        "student_subject_results",
        "level_subjects",
        ["level_subject_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_student_subject_result_scope",
        "student_subject_results",
        [
            "tenant_id",
            "student_id",
            "teacher_assignment_id",
            "academic_session_id",
            "academic_term_id",
        ],
        schema="public",
    )

    op.drop_column("student_subject_results", "class_subject_teacher_id", schema="public")
    op.drop_column("teacher_assignment_lifecycle_audits", "class_subject_id", schema="public")
    op.drop_column("teacher_assignments", "class_subject_id", schema="public")
    op.drop_index(
        "ix_class_subject_teachers_tenant_membership_active",
        table_name="class_subject_teachers",
        schema="public",
    )
    op.drop_table("class_subject_teachers", schema="public")
    op.drop_index("ix_class_subjects_tenant_archived", table_name="class_subjects", schema="public")
    op.drop_table("class_subjects", schema="public")
    op.drop_column("students", "arm", schema="public")
    op.drop_column("classes", "next_class_id", schema="public")
    op.drop_column("classes", "is_terminal", schema="public")
    op.drop_column("classes", "normalized_name", schema="public")
    op.drop_column("classes", "name", schema="public")


def downgrade() -> None:
    raise RuntimeError(
        "This destructive development migration cannot reconstruct removed per-class curriculum history."
    )
