"""Remove obsolete academic hierarchy compatibility columns.

Revision ID: 20260817_academic_cleanup
Revises: 20260817_curriculum_cutover

This is an intentional pre-launch destructive cutover. The runtime model is now
strictly level-owned with tenant-wide arm labels and term-scoped specialization;
legacy physical columns are removed rather than retained for compatibility.
"""

from alembic import op

revision = "20260817_academic_cleanup"
down_revision = "20260817_curriculum_cutover"
branch_labels = None
depends_on = None
SCHEMA = "public"


def upgrade() -> None:
    # AcademicLevel no longer contains or implies a mandatory specialization term.
    op.execute(
        "ALTER TABLE public.academic_levels "
        "DROP CONSTRAINT IF EXISTS ck_academic_levels_specialization_term_positive"
    )
    op.execute(
        "ALTER TABLE public.academic_levels "
        "DROP COLUMN IF EXISTS specialization_required_from_term_position"
    )

    # Arm labels are tenant-wide naming vocabulary only; they do not carry order.
    op.execute("DROP INDEX IF EXISTS public.ix_arm_labels_tenant_position")
    op.execute(
        "ALTER TABLE public.arm_labels DROP CONSTRAINT IF EXISTS ck_arm_labels_position_positive"
    )
    op.execute("ALTER TABLE public.arm_labels DROP COLUMN IF EXISTS position")

    # Class identity is level + reusable arm label. Department specialization is
    # represented only by class_term_department_assignments.
    op.execute("DROP INDEX IF EXISTS public.uq_classes_tenant_level_department_arm")
    op.execute("DROP INDEX IF EXISTS public.ix_classes_tenant_department")
    op.execute("ALTER TABLE public.classes DROP CONSTRAINT IF EXISTS fk_classes_department_id")
    op.execute("ALTER TABLE public.classes DROP COLUMN IF EXISTS department_id")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM public.classes WHERE arm_label_id IS NULL) THEN
                RAISE EXCEPTION 'classes.arm_label_id must be backfilled before academic cleanup';
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE public.classes ALTER COLUMN arm_label_id SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_classes_tenant_level_arm_label'
                  AND conrelid = 'public.classes'::regclass
            ) THEN
                ALTER TABLE public.classes
                ADD CONSTRAINT uq_classes_tenant_level_arm_label
                UNIQUE (tenant_id, academic_level_id, arm_label_id);
            END IF;
        END $$;
        """
    )

    # Departments are level-owned. Any pre-cutover tenant-wide department with no
    # level cannot participate in the new contract and is deliberately discarded.
    op.execute(
        "ALTER TABLE public.departments DROP CONSTRAINT IF EXISTS uq_departments_tenant_name"
    )
    op.execute("DROP INDEX IF EXISTS public.ix_departments_tenant_active")
    op.execute("DELETE FROM public.departments WHERE academic_level_id IS NULL")
    op.execute("ALTER TABLE public.departments ALTER COLUMN academic_level_id SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_departments_tenant_level_name'
                  AND conrelid = 'public.departments'::regclass
            ) THEN
                ALTER TABLE public.departments
                ADD CONSTRAINT uq_departments_tenant_level_name
                UNIQUE (tenant_id, academic_level_id, normalized_name);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "20260817_academic_cleanup is intentionally irreversible; restore a "
        "pre-cutover development database if rollback is required."
    )
