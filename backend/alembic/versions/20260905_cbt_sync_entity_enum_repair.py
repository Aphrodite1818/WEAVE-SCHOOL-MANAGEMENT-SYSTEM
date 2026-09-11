"""Repair durable CBT sync entity enum drift.

Revision ID: 20260905_cbt_sync_enum_repair
Revises: 20260903_curriculum_scopes
Create Date: 2026-09-05

The September curriculum cutover defines this complete enum contract. This
repair is intentionally idempotent so databases that were stamped or otherwise
drifted can converge on the runtime wire contract safely.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260905_cbt_sync_enum_repair"
down_revision: Union[str, Sequence[str], None] = "20260903_curriculum_scopes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"
CBT_SYNC_ENTITY_VALUES = (
    "academic_level",
    "department",
    "arm_label",
    "class",
    "class_term_department",
    "academic_session",
    "academic_term",
    "subject",
    "curriculum",
    "curriculum_subject",
    "curriculum_subject_department",
    "assessment_scheme",
    "assessment_component",
    "admin",
    "teacher",
    "teacher_assignment",
    "student_enrollment",
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for value in CBT_SYNC_ENTITY_VALUES:
            op.execute(
                f"ALTER TYPE {SCHEMA}.cbt_sync_entity_type "
                f"ADD VALUE IF NOT EXISTS '{value}'"
            )


def downgrade() -> None:
    raise RuntimeError(
        "CBT sync entity enum repair is intentionally irreversible before launch."
    )
