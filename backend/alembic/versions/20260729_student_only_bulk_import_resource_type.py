"""Limit bulk import resource types to students.

Revision ID: 20260729_student_import_type
Revises: 20260728_attendance
Create Date: 2026-07-29
"""

from __future__ import annotations

from typing import Sequence

from alembic import op

revision: str = "20260729_student_import_type"
down_revision: str | Sequence[str] | None = "20260728_attendance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


OLD_VALUES = (
    "students",
    "teachers",
    "parents",
    "classes",
    "subjects",
    "class_subjects",
    "teacher_subjects",
    "assessment_records",
)


def _replace_import_resource_type(*, values: tuple[str, ...]) -> None:
    values_sql = ", ".join(f"'{value}'" for value in values)
    op.execute("ALTER TYPE public.import_resource_type RENAME TO import_resource_type_old;")
    op.execute(f"CREATE TYPE public.import_resource_type AS ENUM ({values_sql});")
    op.execute(
        """
        ALTER TABLE public.import_jobs
            ALTER COLUMN resource_type TYPE public.import_resource_type
            USING resource_type::text::public.import_resource_type;
        """
    )
    op.execute("DROP TYPE public.import_resource_type_old;")


def upgrade() -> None:
    op.execute("DELETE FROM public.import_jobs WHERE resource_type::text <> 'students';")
    _replace_import_resource_type(values=("students",))


def downgrade() -> None:
    _replace_import_resource_type(values=OLD_VALUES)
