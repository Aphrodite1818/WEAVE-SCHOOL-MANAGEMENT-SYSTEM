"""Allow partial student scores and support student subject cards.

Revision ID: 20260702_partial_results
Revises: 20260702_teacher_assign_active
Create Date: 2026-07-02 23:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260702_partial_results"
down_revision = "20260702_teacher_assign_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "student_subject_results",
        "test_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=True,
    )
    op.alter_column(
        "student_subject_results",
        "assessment_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=True,
    )
    op.alter_column(
        "student_subject_results",
        "exam_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=True,
    )
    op.alter_column(
        "student_subject_results",
        "grade",
        existing_type=sa.String(length=10),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "student_subject_results",
        "grade",
        existing_type=sa.String(length=10),
        nullable=False,
    )
    op.alter_column(
        "student_subject_results",
        "exam_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=False,
    )
    op.alter_column(
        "student_subject_results",
        "assessment_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=False,
    )
    op.alter_column(
        "student_subject_results",
        "test_score",
        existing_type=sa.Numeric(precision=5, scale=2),
        nullable=False,
    )
