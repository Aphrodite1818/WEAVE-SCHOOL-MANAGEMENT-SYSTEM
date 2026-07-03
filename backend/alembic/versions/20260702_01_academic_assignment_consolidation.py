"""academic assignment consolidation phase 1

Revision ID: 20260702_academic_consolidation
Revises: 20260626_academic_results
Create Date: 2026-07-02 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260702_academic_consolidation"
down_revision: Union[str, Sequence[str], None] = "20260626_academic_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _baseline_already_created_academic_assignment_tables() -> bool:
    """Return True when the staging baseline already emitted this schema.

    The staging baseline creates tables from current model metadata. On a fresh
    staging database, that means these consolidation tables and columns can
    already exist before Alembic reaches this historical migration.
    """

    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    if not {"class_subjects", "teacher_assignments", "student_subject_results", "report_cards"}.issubset(tables):
        return False

    student_result_columns = {column["name"] for column in inspector.get_columns("student_subject_results")}
    report_card_columns = {column["name"] for column in inspector.get_columns("report_cards")}

    return (
        "teacher_assignment_id" in student_result_columns
        and "version" in report_card_columns
        and "published_at" in report_card_columns
        and "superseded_at" in report_card_columns
    )


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _unique_constraint_exists(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return constraint_name in {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def _foreign_key_exists(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return constraint_name in {constraint["name"] for constraint in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _table_exists(inspector, "class_subjects"):
        op.create_table(
            "class_subjects",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("class_id", sa.UUID(), nullable=False),
            sa.Column("subject_id", sa.UUID(), nullable=False),
            sa.Column("is_core", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "class_id", "subject_id", name="uq_class_subject_tenant_class_subject"),
        )

    if not _index_exists(inspector, "class_subjects", "ix_class_subjects_class_id"):
        op.create_index("ix_class_subjects_class_id", "class_subjects", ["class_id"])
    if not _index_exists(inspector, "class_subjects", "ix_class_subjects_subject_id"):
        op.create_index("ix_class_subjects_subject_id", "class_subjects", ["subject_id"])

    if not _table_exists(inspector, "teacher_assignments"):
        op.create_table(
            "teacher_assignments",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("class_subject_id", sa.UUID(), nullable=False),
            sa.Column("teacher_id", sa.UUID(), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("effective_from", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
            sa.Column("effective_to", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _index_exists(inspector, "teacher_assignments", "ix_teacher_assignments_class_subject_id"):
        op.create_index("ix_teacher_assignments_class_subject_id", "teacher_assignments", ["class_subject_id"])
    if not _index_exists(inspector, "teacher_assignments", "ix_teacher_assignments_teacher_id"):
        op.create_index("ix_teacher_assignments_teacher_id", "teacher_assignments", ["teacher_id"])
    if not _index_exists(inspector, "teacher_assignments", "uq_teacher_assignment_active_class_subject_teacher"):
        op.create_index(
            "uq_teacher_assignment_active_class_subject_teacher",
            "teacher_assignments",
            ["class_subject_id", "teacher_id"],
            unique=True,
            postgresql_where=sa.text("is_active = true"),
        )

    if not _column_exists(inspector, "student_subject_results", "teacher_assignment_id"):
        op.add_column(
            "student_subject_results",
            sa.Column("teacher_assignment_id", sa.UUID(), nullable=True),
        )

    if not _foreign_key_exists(inspector, "student_subject_results", "fk_student_subject_results_teacher_assignment_id"):
        op.create_foreign_key(
            "fk_student_subject_results_teacher_assignment_id",
            "student_subject_results",
            "teacher_assignments",
            ["teacher_assignment_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    if not _index_exists(inspector, "student_subject_results", "ix_student_subject_results_teacher_assignment_id"):
        op.create_index(
            "ix_student_subject_results_teacher_assignment_id",
            "student_subject_results",
            ["teacher_assignment_id"],
        )

    # Collapse published/locked score statuses into submitted before narrowing enum.
    op.execute(
        "UPDATE student_subject_results SET status = 'submitted' "
        "WHERE status IN ('published', 'locked')"
    )
    op.execute("ALTER TABLE student_subject_results ALTER COLUMN status DROP DEFAULT")
    op.execute("ALTER TYPE academic_result_status RENAME TO academic_result_status_old")
    op.execute("CREATE TYPE academic_result_status AS ENUM ('draft', 'submitted')")
    op.execute(
        "ALTER TABLE student_subject_results "
        "ALTER COLUMN status TYPE academic_result_status "
        "USING status::text::academic_result_status"
    )
    op.execute(
        "ALTER TABLE student_subject_results "
        "ALTER COLUMN status SET DEFAULT 'draft'::academic_result_status"
    )
    op.execute("DROP TYPE academic_result_status_old")

    if not _column_exists(inspector, "report_cards", "position"):
        op.add_column("report_cards", sa.Column("position", sa.Integer(), nullable=True))
    if not _column_exists(inspector, "report_cards", "position_out_of"):
        op.add_column("report_cards", sa.Column("position_out_of", sa.Integer(), nullable=True))
    if not _column_exists(inspector, "report_cards", "class_teacher_comment"):
        op.add_column("report_cards", sa.Column("class_teacher_comment", sa.Text(), nullable=True))
    if not _column_exists(inspector, "report_cards", "principal_comment"):
        op.add_column("report_cards", sa.Column("principal_comment", sa.Text(), nullable=True))
    if not _column_exists(inspector, "report_cards", "version"):
        op.add_column("report_cards", sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False))
    if not _column_exists(inspector, "report_cards", "published_at"):
        op.add_column("report_cards", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists(inspector, "report_cards", "published_by"):
        op.add_column("report_cards", sa.Column("published_by", sa.UUID(), nullable=True))
    if not _column_exists(inspector, "report_cards", "is_outdated"):
        op.add_column(
            "report_cards",
            sa.Column("is_outdated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
    if not _column_exists(inspector, "report_cards", "superseded_at"):
        op.add_column("report_cards", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    if not _foreign_key_exists(inspector, "report_cards", "fk_report_cards_published_by"):
        op.create_foreign_key(
            "fk_report_cards_published_by",
            "report_cards",
            "tenant_admins",
            ["published_by"],
            ["id"],
            ondelete="SET NULL",
        )

    # Backfill published_at for already-published report cards.
    op.execute(
        "UPDATE report_cards SET published_at = updated_at, version = 1 "
        "WHERE status = 'published' AND published_at IS NULL"
    )

    if _unique_constraint_exists(inspector, "report_cards", "uq_report_cards_student_period"):
        op.drop_constraint("uq_report_cards_student_period", "report_cards", type_="unique")
    if not _index_exists(inspector, "report_cards", "ix_report_cards_active_student_period"):
        op.create_index(
            "ix_report_cards_active_student_period",
            "report_cards",
            ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
            unique=True,
            postgresql_where=sa.text("superseded_at IS NULL"),
        )


def downgrade() -> None:
    op.drop_index("ix_report_cards_active_student_period", table_name="report_cards")
    op.create_unique_constraint(
        "uq_report_cards_student_period",
        "report_cards",
        ["tenant_id", "student_id", "academic_session_id", "academic_term_id"],
    )

    op.drop_constraint("fk_report_cards_published_by", "report_cards", type_="foreignkey")
    op.drop_column("report_cards", "superseded_at")
    op.drop_column("report_cards", "is_outdated")
    op.drop_column("report_cards", "published_by")
    op.drop_column("report_cards", "published_at")
    op.drop_column("report_cards", "version")
    op.drop_column("report_cards", "principal_comment")
    op.drop_column("report_cards", "class_teacher_comment")
    op.drop_column("report_cards", "position_out_of")
    op.drop_column("report_cards", "position")

    op.execute("ALTER TYPE academic_result_status RENAME TO academic_result_status_new")
    op.execute(
        "CREATE TYPE academic_result_status AS ENUM ('draft', 'submitted', 'published', 'locked')"
    )
    op.execute(
        "ALTER TABLE student_subject_results "
        "ALTER COLUMN status TYPE academic_result_status "
        "USING status::text::academic_result_status"
    )
    op.execute("DROP TYPE academic_result_status_new")

    op.drop_index("ix_student_subject_results_teacher_assignment_id", table_name="student_subject_results")
    op.drop_constraint(
        "fk_student_subject_results_teacher_assignment_id",
        "student_subject_results",
        type_="foreignkey",
    )
    op.drop_column("student_subject_results", "teacher_assignment_id")

    op.drop_index(
        "uq_teacher_assignment_active_class_subject_teacher",
        table_name="teacher_assignments",
    )
    op.drop_index("ix_teacher_assignments_teacher_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_class_subject_id", table_name="teacher_assignments")
    op.drop_table("teacher_assignments")
    op.drop_index("ix_class_subjects_subject_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_class_id", table_name="class_subjects")
    op.drop_table("class_subjects")
