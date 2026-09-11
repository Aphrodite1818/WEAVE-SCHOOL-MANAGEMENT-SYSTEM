"""Harden academic-session lifecycle and date invariants.

Revision ID: academic_session_hardening
Revises: student_enrollment_segments
Create Date: 2026-08-26

The pre-launch academic lifecycle keeps ``is_current`` for API compatibility but
makes it a strict mirror of the operational OPEN/CLOSING states. Complete session
ranges may not overlap within a tenant, and operational sessions must have a
complete valid date range.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "academic_session_hardening"
down_revision: Union[str, Sequence[str], None] = "student_enrollment_segments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "public"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # Fail loudly rather than silently choosing one operational session if stale
    # development data contains more than one OPEN/CLOSING row for a tenant.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT tenant_id
                FROM public.academic_sessions
                WHERE status IN ('open', 'closing')
                GROUP BY tenant_id
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'academic session hardening failed: tenant has multiple OPEN/CLOSING sessions';
            END IF;
        END
        $$;
        """
    )

    # Normalize the redundant flag before enforcing exact state equivalence.
    op.execute(
        """
        UPDATE public.academic_sessions
        SET is_current = (status IN ('open', 'closing'))
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.academic_sessions
                WHERE start_date IS NOT NULL
                  AND end_date IS NOT NULL
                  AND end_date <= start_date
            ) THEN
                RAISE EXCEPTION
                    'academic session hardening failed: invalid session date range exists';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.academic_sessions
                WHERE status IN ('open', 'closing', 'closed')
                  AND (start_date IS NULL OR end_date IS NULL)
            ) THEN
                RAISE EXCEPTION
                    'academic session hardening failed: operational/historical session is missing dates';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM public.academic_sessions a
                JOIN public.academic_sessions b
                  ON a.tenant_id = b.tenant_id
                 AND a.id < b.id
                 AND a.start_date IS NOT NULL
                 AND a.end_date IS NOT NULL
                 AND b.start_date IS NOT NULL
                 AND b.end_date IS NOT NULL
                 AND daterange(a.start_date, a.end_date, '[]')
                     && daterange(b.start_date, b.end_date, '[]')
            ) THEN
                RAISE EXCEPTION
                    'academic session hardening failed: overlapping session date ranges exist';
            END IF;
        END
        $$;
        """
    )

    # Earlier development baselines used this weaker check. The fresh baseline
    # may not contain it, so make the cutover independent of baseline history.
    op.execute(
        """
        ALTER TABLE public.academic_sessions
        DROP CONSTRAINT IF EXISTS ck_closed_academic_session_not_current
        """
    )

    op.create_check_constraint(
        "ck_academic_session_current_matches_status",
        "academic_sessions",
        "((status IN ('open', 'closing')) AND is_current = true) OR "
        "((status IN ('draft', 'closed')) AND is_current = false)",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_academic_session_date_range",
        "academic_sessions",
        "start_date IS NULL OR end_date IS NULL OR end_date > start_date",
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_academic_session_operational_dates",
        "academic_sessions",
        "status = 'draft' OR (start_date IS NOT NULL AND end_date IS NOT NULL)",
        schema=SCHEMA,
    )

    op.execute(
        """
        ALTER TABLE public.academic_sessions
        ADD CONSTRAINT excl_academic_sessions_date_overlap
        EXCLUDE USING gist (
            tenant_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        )
        WHERE (start_date IS NOT NULL AND end_date IS NOT NULL)
        """
    )


def downgrade() -> None:
    raise RuntimeError(
        "Academic-session hardening is a pre-launch invariant cutover and is not reversible."
    )
