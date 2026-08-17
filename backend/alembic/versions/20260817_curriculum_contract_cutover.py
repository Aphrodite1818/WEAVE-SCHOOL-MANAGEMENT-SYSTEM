"""Remove legacy level-subject academic contracts.

Revision ID: 20260817_curriculum_cutover
Revises: 20260817_curriculum_v2

This is intentionally a destructive pre-launch cutover. The application contract
moves fully to CurriculumSubject/CurriculumOffering and does not retain legacy
columns or tables for compatibility.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260817_curriculum_cutover"
down_revision = "20260817_curriculum_v2"
branch_labels = None
depends_on = None
SCHEMA = "public"


def _assert_backfilled(table: str, column: str) -> None:
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM {SCHEMA}.{table} WHERE {column} IS NULL) THEN
                    RAISE EXCEPTION '{table}.{column} could not be derived during curriculum cutover';
                END IF;
            END $$;
            """
        )
    )


def upgrade() -> None:
    op.add_column(
        "teacher_assignments",
        sa.Column("curriculum_subject_id", sa.UUID(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "teacher_assignment_lifecycle_audits",
        sa.Column("curriculum_subject_id", sa.UUID(), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "student_subject_results",
        sa.Column("curriculum_subject_id", sa.UUID(), nullable=True),
        schema=SCHEMA,
    )

    # A curriculum subject is uniquely resolved by the assignment/result class
    # academic level plus the immutable subject identity behind the old mapping.
    op.execute(
        sa.text(
            """
            UPDATE public.teacher_assignments ta
            SET curriculum_subject_id = cs.id
            FROM public.level_subjects ls,
                 public.classes c,
                 public.curricula cu,
                 public.curriculum_subjects cs
            WHERE ls.id = ta.level_subject_id
              AND ls.tenant_id = ta.tenant_id
              AND c.id = ta.class_id
              AND c.tenant_id = ta.tenant_id
              AND cu.tenant_id = ta.tenant_id
              AND cu.academic_level_id = c.academic_level_id
              AND cs.tenant_id = ta.tenant_id
              AND cs.curriculum_id = cu.id
              AND cs.subject_id = ls.subject_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE public.teacher_assignment_lifecycle_audits audit
            SET curriculum_subject_id = cs.id
            FROM public.level_subjects ls,
                 public.classes c,
                 public.curricula cu,
                 public.curriculum_subjects cs
            WHERE ls.id = audit.level_subject_id
              AND ls.tenant_id = audit.tenant_id
              AND c.id = audit.class_id
              AND c.tenant_id = audit.tenant_id
              AND cu.tenant_id = audit.tenant_id
              AND cu.academic_level_id = c.academic_level_id
              AND cs.tenant_id = audit.tenant_id
              AND cs.curriculum_id = cu.id
              AND cs.subject_id = ls.subject_id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE public.student_subject_results result
            SET curriculum_subject_id = cs.id
            FROM public.level_subjects ls,
                 public.classes c,
                 public.curricula cu,
                 public.curriculum_subjects cs
            WHERE ls.id = result.level_subject_id
              AND ls.tenant_id = result.tenant_id
              AND c.id = result.class_id
              AND c.tenant_id = result.tenant_id
              AND cu.tenant_id = result.tenant_id
              AND cu.academic_level_id = c.academic_level_id
              AND cs.tenant_id = result.tenant_id
              AND cs.curriculum_id = cu.id
              AND cs.subject_id = ls.subject_id
            """
        )
    )

    _assert_backfilled("teacher_assignments", "curriculum_subject_id")
    _assert_backfilled("teacher_assignment_lifecycle_audits", "curriculum_subject_id")
    _assert_backfilled("student_subject_results", "curriculum_subject_id")

    op.alter_column(
        "teacher_assignments",
        "curriculum_subject_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "teacher_assignment_lifecycle_audits",
        "curriculum_subject_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema=SCHEMA,
    )
    op.alter_column(
        "student_subject_results",
        "curriculum_subject_id",
        existing_type=sa.UUID(),
        nullable=False,
        schema=SCHEMA,
    )

    op.create_foreign_key(
        "fk_teacher_assignments_curriculum_subject",
        "teacher_assignments",
        "curriculum_subjects",
        ["curriculum_subject_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_teacher_assignment_audits_curriculum_subject",
        "teacher_assignment_lifecycle_audits",
        "curriculum_subjects",
        ["curriculum_subject_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_student_subject_results_curriculum_subject",
        "student_subject_results",
        "curriculum_subjects",
        ["curriculum_subject_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_teacher_assignments_curriculum_subject_id",
        "teacher_assignments",
        ["curriculum_subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_assignment_lifecycle_audits_curriculum_subject_id",
        "teacher_assignment_lifecycle_audits",
        ["curriculum_subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_student_subject_results_curriculum_subject_id",
        "student_subject_results",
        ["curriculum_subject_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "uq_teacher_assignment_active_class_curriculum_subject",
        "teacher_assignments",
        ["class_id", "curriculum_subject_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_unique_constraint(
        "uq_student_subject_result_scope_v2",
        "student_subject_results",
        [
            "tenant_id",
            "student_id",
            "curriculum_subject_id",
            "academic_session_id",
            "academic_term_id",
        ],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_teacher_assignment_audits_tenant_class_curriculum_subject",
        "teacher_assignment_lifecycle_audits",
        ["tenant_id", "class_id", "curriculum_subject_id"],
        schema=SCHEMA,
    )

    # Dropping the old columns with CASCADE removes their generated foreign keys,
    # single-column indexes, active-assignment index and old result scope constraint.
    op.execute("ALTER TABLE public.teacher_assignments DROP COLUMN level_subject_id CASCADE")
    op.execute(
        "ALTER TABLE public.teacher_assignment_lifecycle_audits DROP COLUMN level_subject_id CASCADE"
    )
    op.execute("ALTER TABLE public.student_subject_results DROP COLUMN level_subject_id CASCADE")

    # These tables are obsolete by design. No compatibility views or aliases remain.
    op.execute("DROP TABLE IF EXISTS public.subject_offerings CASCADE")
    op.execute("DROP TABLE IF EXISTS public.student_department_assignments CASCADE")
    op.execute("DROP TABLE IF EXISTS public.level_subjects CASCADE")


def downgrade() -> None:
    raise RuntimeError(
        "20260817_curriculum_cutover is intentionally irreversible; "
        "restore a pre-cutover development database if rollback is required."
    )
