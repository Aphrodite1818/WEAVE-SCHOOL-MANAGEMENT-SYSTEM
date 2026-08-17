"""replace legacy class progression with explicit academic hierarchy

Revision ID: 20260815_academic_hierarchy
Revises: 20260813_cbt_name_partial

The development database intentionally has no compatibility layer for the old
progression graph. Existing levels receive a deterministic migration-only
category/position so enrollment history can be retained; administrators can
then correct that explicit structure in the new setup workflow.
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260815_academic_hierarchy"
down_revision = "20260813_cbt_name_partial"
branch_labels = None
depends_on = None

SCHEMA = "public"

OFFLINE_TABLE_NAMES = {
    "academic_levels",
    "classes",
    "level_subjects",
    "progression_selection_options",
    "student_progression_items",
}
OFFLINE_COLUMN_NAMES = {
    "academic_levels": {
        "next_level_id",
        "is_terminal",
        "progression_mode",
        "selection_target_type",
    },
    "classes": {"arm", "normalized_arm"},
    "level_subjects": {"is_core"},
}
OFFLINE_CONSTRAINT_NAMES = {
    "academic_levels": {
        "academic_levels_next_level_id_fkey",
        "ck_academic_levels_next_not_self",
        "ck_academic_levels_terminal_has_no_next",
    },
    "classes": {"uq_classes_tenant_level_arm"},
}
OFFLINE_INDEX_NAMES = {
    "academic_levels": {"ix_academic_levels_tenant_next"},
    "classes": set(),
}


def _table_names() -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_TABLE_NAMES
    return set(sa.inspect(op.get_bind()).get_table_names(schema=SCHEMA))


def _column_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_COLUMN_NAMES.get(table_name, set())
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns(table_name, schema=SCHEMA)
    }


def _constraint_names(table_name: str) -> set[str]:
    if context.is_offline_mode():
        return OFFLINE_CONSTRAINT_NAMES.get(table_name, set())
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
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_indexes(table_name, schema=SCHEMA)
    }


def _drop_constraint_if_exists(table_name: str, name: str, type_: str) -> None:
    if name in _constraint_names(table_name):
        op.drop_constraint(name, table_name, type_=type_, schema=SCHEMA)


def _drop_index_if_exists(table_name: str, name: str) -> None:
    if name in _index_names(table_name):
        op.drop_index(name, table_name=table_name, schema=SCHEMA)


def upgrade() -> None:
    bind = op.get_bind()
    institution_type = postgresql.ENUM(
        "PRIMARY_SCHOOL",
        "SECONDARY_SCHOOL",
        name="institution_type",
        schema=SCHEMA,
    )
    academic_category = postgresql.ENUM(
        "KINDERGARTEN",
        "PRIMARY",
        "JUNIOR_SECONDARY",
        "SENIOR_SECONDARY",
        name="academic_category",
        schema=SCHEMA,
    )
    institution_type.create(bind, checkfirst=True)
    academic_category.create(bind, checkfirst=True)

    op.add_column(
        "tenants",
        sa.Column(
            "institution_type",
            postgresql.ENUM(
                "PRIMARY_SCHOOL",
                "SECONDARY_SCHOOL",
                name="institution_type",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=True,
        ),
        schema=SCHEMA,
    )

    op.add_column(
        "academic_levels",
        sa.Column(
            "category",
            postgresql.ENUM(
                "KINDERGARTEN",
                "PRIMARY",
                "JUNIOR_SECONDARY",
                "SENIOR_SECONDARY",
                name="academic_category",
                schema=SCHEMA,
                create_type=False,
            ),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column("academic_levels", sa.Column("position", sa.Integer()), schema=SCHEMA)
    op.add_column(
        "academic_levels",
        sa.Column("specialization_required_from_term_position", sa.Integer()),
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE public.tenants AS tenant
        SET institution_type = 'SECONDARY_SCHOOL'
        WHERE institution_type IS NULL
          AND EXISTS (
              SELECT 1 FROM public.academic_levels AS level
              WHERE level.tenant_id = tenant.id
          )
        """
    )
    op.execute(
        """
        WITH ordered_levels AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY tenant_id ORDER BY created_at, id
                   ) AS migrated_position
            FROM public.academic_levels
        )
        UPDATE public.academic_levels AS level
        SET category = 'JUNIOR_SECONDARY',
            position = ordered_levels.migrated_position
        FROM ordered_levels
        WHERE level.id = ordered_levels.id
        """
    )
    op.alter_column("academic_levels", "category", nullable=False, schema=SCHEMA)
    op.alter_column("academic_levels", "position", nullable=False, schema=SCHEMA)
    op.create_unique_constraint(
        "uq_academic_levels_tenant_category_position",
        "academic_levels",
        ["tenant_id", "category", "position"],
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_academic_levels_position_positive",
        "academic_levels",
        "position > 0",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_academic_levels_specialization_term_positive",
        "academic_levels",
        "specialization_required_from_term_position IS NULL OR "
        "specialization_required_from_term_position > 0",
        schema=SCHEMA,
    )
    op.create_index(
        "ix_academic_levels_tenant_category_position",
        "academic_levels",
        ["tenant_id", "category", "position"],
        schema=SCHEMA,
    )

    if "progression_selection_options" in _table_names():
        op.drop_table("progression_selection_options", schema=SCHEMA)
    _drop_index_if_exists("academic_levels", "ix_academic_levels_tenant_next")
    for constraint_name, constraint_type in (
        ("ck_academic_levels_terminal_has_no_next", "check"),
        ("ck_academic_levels_next_not_self", "check"),
        ("academic_levels_next_level_id_fkey", "foreignkey"),
    ):
        _drop_constraint_if_exists("academic_levels", constraint_name, constraint_type)
    for column_name in (
        "next_level_id",
        "is_terminal",
        "progression_mode",
        "selection_target_type",
    ):
        if column_name in _column_names("academic_levels"):
            op.drop_column("academic_levels", column_name, schema=SCHEMA)

    op.create_table(
        "departments",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_departments_archived_requires_inactive",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", "normalized_name", name="uq_departments_tenant_name"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_departments_tenant_active",
        "departments",
        ["tenant_id", "is_active"],
        schema=SCHEMA,
    )
    op.create_table(
        "arm_labels",
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column("normalized_label", sa.String(40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position IS NULL OR position > 0", name="ck_arm_labels_position_positive"),
        sa.CheckConstraint(
            "archived_at IS NULL OR is_active = false",
            name="ck_arm_labels_archived_requires_inactive",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("tenant_id", "normalized_label", name="uq_arm_labels_tenant_label"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_arm_labels_tenant_active",
        "arm_labels",
        ["tenant_id", "is_active"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_arm_labels_tenant_position",
        "arm_labels",
        ["tenant_id", "position"],
        schema=SCHEMA,
    )

    op.add_column("classes", sa.Column("department_id", sa.UUID()), schema=SCHEMA)
    op.add_column("classes", sa.Column("arm_label_id", sa.UUID()), schema=SCHEMA)
    if "arm" in _column_names("classes") and "normalized_arm" in _column_names("classes"):
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
    op.create_foreign_key(
        "fk_classes_department_id",
        "classes",
        "departments",
        ["department_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
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
        CREATE UNIQUE INDEX uq_classes_tenant_level_department_arm
        ON public.classes (
            tenant_id,
            academic_level_id,
            COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid),
            COALESCE(arm_label_id, '00000000-0000-0000-0000-000000000000'::uuid)
        )
        """
    )
    op.create_index(
        "ix_classes_tenant_department",
        "classes",
        ["tenant_id", "department_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_classes_tenant_arm_label",
        "classes",
        ["tenant_id", "arm_label_id"],
        schema=SCHEMA,
    )
    for column_name in ("normalized_arm", "arm"):
        if column_name in _column_names("classes"):
            op.drop_column("classes", column_name, schema=SCHEMA)

    op.add_column(
        "student_enrollments",
        sa.Column("academic_level_id", sa.UUID()),
        schema=SCHEMA,
    )
    op.execute(
        """
        UPDATE public.student_enrollments AS enrollment
        SET academic_level_id = class.academic_level_id
        FROM public.classes AS class
        WHERE enrollment.class_id = class.id
        """
    )
    op.alter_column(
        "student_enrollments", "academic_level_id", nullable=False, schema=SCHEMA
    )
    op.create_foreign_key(
        "fk_student_enrollments_academic_level_id",
        "student_enrollments",
        "academic_levels",
        ["academic_level_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="RESTRICT",
    )
    op.alter_column("student_enrollments", "class_id", nullable=True, schema=SCHEMA)
    op.create_index(
        "ix_student_enrollments_tenant_level",
        "student_enrollments",
        ["tenant_id", "academic_level_id"],
        schema=SCHEMA,
    )

    if "is_core" in _column_names("level_subjects"):
        op.drop_column("level_subjects", "is_core", schema=SCHEMA)

    op.create_table(
        "student_department_assignments",
        sa.Column("student_enrollment_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("effective_from_term_id", sa.UUID(), nullable=False),
        sa.Column("assigned_by_admin_id", sa.UUID()),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_enrollment_id"], ["public.student_enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["public.departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["effective_from_term_id"], ["public.academic_terms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_admin_id"], ["public.tenant_admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_enrollment_id",
            "effective_from_term_id",
            name="uq_student_department_assignment_effective_term",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_student_department_assignments_tenant_enrollment",
        "student_department_assignments",
        ["tenant_id", "student_enrollment_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "subject_offerings",
        sa.Column("level_subject_id", sa.UUID(), nullable=False),
        sa.Column("academic_term_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID()),
        sa.Column("is_elective", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["level_subject_id"], ["public.level_subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_term_id"], ["public.academic_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["public.departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        schema=SCHEMA,
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_subject_offering_scope
        ON public.subject_offerings (
            tenant_id,
            level_subject_id,
            academic_term_id,
            COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid)
        )
        """
    )
    op.create_index(
        "ix_subject_offerings_tenant_term",
        "subject_offerings",
        ["tenant_id", "academic_term_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_subject_offerings_tenant_department",
        "subject_offerings",
        ["tenant_id", "department_id"],
        schema=SCHEMA,
    )

    op.alter_column("report_cards", "class_id", nullable=True, schema=SCHEMA)

    if "student_progression_items" in _table_names():
        op.drop_table("student_progression_items", schema=SCHEMA)
    op.execute("DROP TYPE IF EXISTS public.student_progression_item_action")
    op.execute("DROP TYPE IF EXISTS public.student_progression_item_status")
    progression_action = postgresql.ENUM(
        "progress", "complete", "skip", name="student_progression_item_action", schema=SCHEMA
    )
    progression_status = postgresql.ENUM(
        "completed", "blocked", "cancelled", name="student_progression_item_status", schema=SCHEMA
    )
    progression_action.create(bind, checkfirst=True)
    progression_status.create(bind, checkfirst=True)
    op.create_table(
        "student_progression_items",
        sa.Column("progression_run_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("from_enrollment_id", sa.UUID()),
        sa.Column("to_enrollment_id", sa.UUID()),
        sa.Column("from_level_id", sa.UUID(), nullable=False),
        sa.Column("to_level_id", sa.UUID()),
        sa.Column("from_class_id", sa.UUID()),
        sa.Column("to_class_id", sa.UUID()),
        sa.Column(
            "action",
            postgresql.ENUM(
                "progress", "complete", "skip",
                name="student_progression_item_action", schema=SCHEMA, create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "completed", "blocked", "cancelled",
                name="student_progression_item_status", schema=SCHEMA, create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(1000)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status <> 'completed' OR action IN ('progress', 'complete')",
            name="ck_progression_item_completed_action",
        ),
        sa.ForeignKeyConstraint(["progression_run_id"], ["public.student_progression_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["public.students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_enrollment_id"], ["public.student_enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_enrollment_id"], ["public.student_enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_level_id"], ["public.academic_levels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_level_id"], ["public.academic_levels.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("progression_run_id", "student_id", name="uq_progression_item_run_student"),
        schema=SCHEMA,
    )
    op.create_index("ix_progression_items_tenant_run", "student_progression_items", ["tenant_id", "progression_run_id"], schema=SCHEMA)
    op.create_index("ix_progression_items_tenant_student", "student_progression_items", ["tenant_id", "student_id"], schema=SCHEMA)
    op.create_index("ix_progression_items_tenant_status", "student_progression_items", ["tenant_id", "status"], schema=SCHEMA)

    op.execute("DROP TYPE IF EXISTS public.academic_level_progression_mode")
    op.execute("DROP TYPE IF EXISTS public.progression_selection_target_type")


def downgrade() -> None:
    # The old progression graph cannot be reconstructed from position-only
    # progression. This downgrade restores its schema with empty configuration.
    bind = op.get_bind()
    op.drop_table("student_progression_items", schema=SCHEMA)
    op.execute("DROP TYPE IF EXISTS public.student_progression_item_action")
    op.execute("DROP TYPE IF EXISTS public.student_progression_item_status")
    old_action = postgresql.ENUM(
        "promote", "graduate", "skip", name="student_progression_item_action", schema=SCHEMA
    )
    old_status = postgresql.ENUM(
        "promoted", "graduated", "skipped", "failed",
        name="student_progression_item_status", schema=SCHEMA,
    )
    old_action.create(bind, checkfirst=True)
    old_status.create(bind, checkfirst=True)
    op.create_table(
        "student_progression_items",
        sa.Column("progression_run_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("from_enrollment_id", sa.UUID()),
        sa.Column("to_enrollment_id", sa.UUID()),
        sa.Column("from_class_id", sa.UUID(), nullable=False),
        sa.Column("to_class_id", sa.UUID()),
        sa.Column("action", postgresql.ENUM("promote", "graduate", "skip", name="student_progression_item_action", schema=SCHEMA, create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("promoted", "graduated", "skipped", "failed", name="student_progression_item_status", schema=SCHEMA, create_type=False), nullable=False),
        sa.Column("reason", sa.String(1000)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["progression_run_id"], ["public.student_progression_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["student_id"], ["public.students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_enrollment_id"], ["public.student_enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_enrollment_id"], ["public.student_enrollments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["from_class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_class_id"], ["public.classes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["public.tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("progression_run_id", "student_id", name="uq_progression_item_run_student"),
        schema=SCHEMA,
    )
    op.create_index("ix_progression_items_tenant_run", "student_progression_items", ["tenant_id", "progression_run_id"], schema=SCHEMA)
    op.create_index("ix_progression_items_tenant_student", "student_progression_items", ["tenant_id", "student_id"], schema=SCHEMA)
    op.create_index("ix_progression_items_tenant_status", "student_progression_items", ["tenant_id", "status"], schema=SCHEMA)

    op.alter_column("report_cards", "class_id", nullable=False, schema=SCHEMA)
    op.drop_table("subject_offerings", schema=SCHEMA)
    op.drop_table("student_department_assignments", schema=SCHEMA)
    op.add_column("level_subjects", sa.Column("is_core", sa.Boolean(), server_default="false", nullable=False), schema=SCHEMA)
    op.drop_index("ix_student_enrollments_tenant_level", table_name="student_enrollments", schema=SCHEMA)
    op.drop_constraint("fk_student_enrollments_academic_level_id", "student_enrollments", type_="foreignkey", schema=SCHEMA)
    op.alter_column("student_enrollments", "class_id", nullable=False, schema=SCHEMA)
    op.drop_column("student_enrollments", "academic_level_id", schema=SCHEMA)

    op.drop_index("ix_classes_tenant_department", table_name="classes", schema=SCHEMA)
    op.drop_index("uq_classes_tenant_level_department_arm", table_name="classes", schema=SCHEMA)
    op.drop_constraint("fk_classes_department_id", "classes", type_="foreignkey", schema=SCHEMA)
    op.drop_column("classes", "department_id", schema=SCHEMA)
    op.alter_column("classes", "arm", nullable=False, schema=SCHEMA)
    op.alter_column("classes", "normalized_arm", nullable=False, schema=SCHEMA)
    op.create_unique_constraint("uq_classes_tenant_level_arm", "classes", ["tenant_id", "academic_level_id", "normalized_arm"], schema=SCHEMA)
    op.drop_table("departments", schema=SCHEMA)

    op.add_column("academic_levels", sa.Column("next_level_id", sa.UUID()), schema=SCHEMA)
    op.add_column("academic_levels", sa.Column("is_terminal", sa.Boolean(), server_default="false", nullable=False), schema=SCHEMA)
    op.create_foreign_key("academic_levels_next_level_id_fkey", "academic_levels", "academic_levels", ["next_level_id"], ["id"], source_schema=SCHEMA, referent_schema=SCHEMA, ondelete="RESTRICT")
    op.create_check_constraint("ck_academic_levels_next_not_self", "academic_levels", "next_level_id IS NULL OR next_level_id <> id", schema=SCHEMA)
    op.create_check_constraint("ck_academic_levels_terminal_has_no_next", "academic_levels", "(is_terminal = true AND next_level_id IS NULL) OR is_terminal = false", schema=SCHEMA)
    op.create_index("ix_academic_levels_tenant_next", "academic_levels", ["tenant_id", "next_level_id"], schema=SCHEMA)
    op.drop_index("ix_academic_levels_tenant_category_position", table_name="academic_levels", schema=SCHEMA)
    op.drop_constraint("ck_academic_levels_specialization_term_positive", "academic_levels", type_="check", schema=SCHEMA)
    op.drop_constraint("ck_academic_levels_position_positive", "academic_levels", type_="check", schema=SCHEMA)
    op.drop_constraint("uq_academic_levels_tenant_category_position", "academic_levels", type_="unique", schema=SCHEMA)
    op.drop_column("academic_levels", "specialization_required_from_term_position", schema=SCHEMA)
    op.drop_column("academic_levels", "position", schema=SCHEMA)
    op.drop_column("academic_levels", "category", schema=SCHEMA)
    op.drop_column("tenants", "institution_type", schema=SCHEMA)
    op.execute("DROP TYPE IF EXISTS public.academic_category")
    op.execute("DROP TYPE IF EXISTS public.institution_type")
