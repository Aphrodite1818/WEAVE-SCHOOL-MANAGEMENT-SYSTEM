"""Add academic progression and parent membership schema.

Revision ID: e99b2f5e17b2
Revises: 20260711_initial_schema
Create Date: 2026-07-15 16:50:47.465618
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e99b2f5e17b2"
down_revision: Union[str, Sequence[str], None] = "20260711_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _exec(sql: str) -> None:
    op.execute(sa.text(sql))


def _create_enum(name: str, values: Sequence[str]) -> None:
    quoted_values = ", ".join(f"'{value}'" for value in values)
    _exec(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_namespace n ON n.oid = t.typnamespace
                WHERE t.typname = '{name}' AND n.nspname = 'public'
            ) THEN
                CREATE TYPE public.{name} AS ENUM ({quoted_values});
            END IF;
        END
        $$;
        """
    )


def _add_enum_value(name: str, value: str) -> None:
    _exec(f"ALTER TYPE public.{name} ADD VALUE IF NOT EXISTS '{value}'")


def _drop_constraint(table: str, name: str) -> None:
    _exec(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {name}")


def upgrade() -> None:
    """Upgrade schema."""

    _create_enum("academic_term_name", ["first_term", "second_term", "third_term"])
    _create_enum("academicstatus", ["active", "withdrawn", "suspended", "graduated"])
    _create_enum(
        "student_parent_link_request_status",
        ["pending", "approved", "rejected", "cancelled"],
    )
    _create_enum("parent_account_status", ["pending", "active", "inactive"])
    _create_enum("academic_session_status", ["draft", "open", "closed", "closing"])
    _create_enum(
        "student_progression_run_status",
        ["pending", "processing", "completed", "failed"],
    )
    _create_enum(
        "student_progression_item_status",
        ["promoted", "graduated", "skipped", "failed"],
    )
    _create_enum(
        "student_progression_item_action",
        ["promote", "graduate", "skip"],
    )
    _create_enum(
        "student_enrollment_outcome",
        [
            "enrolled",
            "promoted",
            "repeated",
            "reclassified",
            "withdrawn",
            "expelled",
            "graduated",
            "archived",
        ],
    )
    _create_enum(
        "student_parent_link_status",
        ["active", "read_only", "alumni_read_only", "ended"],
    )
    _create_enum(
        "parent_link_verified_by_type",
        ["student", "tenant_admin", "system"],
    )
    _create_enum(
        "parent_membership_status",
        ["active", "read_only", "inactive"],
    )
    _create_enum(
        "parent_invitation_status",
        ["pending", "accepted", "expired", "revoked"],
    )

    _add_enum_value("academicstatus", "expelled")
    _add_enum_value("student_parent_link_request_status", "expired")
    _add_enum_value("parent_account_status", "locked")

    _exec(
        """
        ALTER TABLE public.academic_sessions
            ADD COLUMN IF NOT EXISTS status public.academic_session_status,
            ADD COLUMN IF NOT EXISTS closing_started_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS closed_by_admin_id UUID,
            ADD COLUMN IF NOT EXISTS next_academic_session_id UUID;

        UPDATE public.academic_sessions
        SET status = CASE
            WHEN is_current = true AND is_active = true THEN 'open'::public.academic_session_status
            ELSE 'draft'::public.academic_session_status
        END
        WHERE status IS NULL;

        ALTER TABLE public.academic_sessions
            ALTER COLUMN status SET NOT NULL,
            ALTER COLUMN status SET DEFAULT 'draft';
        """
    )
    _drop_constraint("academic_sessions", "academic_sessions_closed_by_admin_id_fkey")
    _drop_constraint("academic_sessions", "academic_sessions_next_academic_session_id_fkey")
    _drop_constraint("academic_sessions", "ck_academic_session_next_not_self")
    _drop_constraint("academic_sessions", "ck_academic_session_status_timestamps")
    _drop_constraint("academic_sessions", "ck_closed_academic_session_not_current")
    _exec(
        """
        ALTER TABLE public.academic_sessions
            ADD CONSTRAINT academic_sessions_closed_by_admin_id_fkey
                FOREIGN KEY (closed_by_admin_id) REFERENCES public.tenant_admins(id)
                ON DELETE SET NULL,
            ADD CONSTRAINT academic_sessions_next_academic_session_id_fkey
                FOREIGN KEY (next_academic_session_id) REFERENCES public.academic_sessions(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT ck_academic_session_next_not_self
                CHECK (next_academic_session_id IS NULL OR next_academic_session_id <> id),
            ADD CONSTRAINT ck_academic_session_status_timestamps
                CHECK (
                    (
                        status = 'draft'
                        AND closing_started_at IS NULL
                        AND closed_at IS NULL
                    )
                    OR
                    (
                        status = 'open'
                        AND closing_started_at IS NULL
                        AND closed_at IS NULL
                    )
                    OR
                    (
                        status = 'closing'
                        AND closing_started_at IS NOT NULL
                        AND closed_at IS NULL
                    )
                    OR
                    (
                        status = 'closed'
                        AND closing_started_at IS NOT NULL
                        AND closed_at IS NOT NULL
                    )
                ),
            ADD CONSTRAINT ck_closed_academic_session_not_current
                CHECK (status <> 'closed' OR is_current = false);

        DROP INDEX IF EXISTS public.uq_academic_sessions_current_per_tenant;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_academic_sessions_current_per_tenant
            ON public.academic_sessions (tenant_id)
            WHERE is_current = true AND is_active = true AND status = 'open';
        CREATE INDEX IF NOT EXISTS ix_academic_sessions_tenant_status
            ON public.academic_sessions (tenant_id, status);
        CREATE INDEX IF NOT EXISTS ix_academic_sessions_tenant_next
            ON public.academic_sessions (tenant_id, next_academic_session_id);
        """
    )

    _exec(
        """
        CREATE TABLE IF NOT EXISTS public.academic_terms (
            academic_session_id UUID NOT NULL REFERENCES public.academic_sessions(id) ON DELETE CASCADE,
            name public.academic_term_name NOT NULL,
            start_date DATE,
            end_date DATE,
            is_current BOOLEAN DEFAULT false NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_academic_term_tenant_session_name
                UNIQUE (tenant_id, academic_session_id, name),
            UNIQUE (id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_academic_terms_current_per_tenant
            ON public.academic_terms (tenant_id)
            WHERE is_current = true AND is_active = true;
        CREATE INDEX IF NOT EXISTS ix_academic_terms_academic_session_id
            ON public.academic_terms (academic_session_id);

        CREATE TABLE IF NOT EXISTS public.grading_scales (
            min_score NUMERIC(5, 2) NOT NULL,
            max_score NUMERIC(5, 2) NOT NULL,
            grade VARCHAR(10) NOT NULL,
            remark VARCHAR(100),
            is_active BOOLEAN DEFAULT true NOT NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_grading_scale_tenant_grade UNIQUE (tenant_id, grade),
            UNIQUE (id)
        );

        CREATE TABLE IF NOT EXISTS public.class_subjects (
            class_id UUID NOT NULL REFERENCES public.classes(id) ON DELETE CASCADE,
            subject_id UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
            is_core BOOLEAN DEFAULT false NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_class_subject_tenant_class_subject
                UNIQUE (tenant_id, class_id, subject_id),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_class_subjects_class_id
            ON public.class_subjects (class_id);
        CREATE INDEX IF NOT EXISTS ix_class_subjects_subject_id
            ON public.class_subjects (subject_id);
        """
    )

    _exec(
        """
        ALTER TABLE public.classes
            ADD COLUMN IF NOT EXISTS next_class_id UUID,
            ADD COLUMN IF NOT EXISTS is_terminal BOOLEAN DEFAULT false NOT NULL;
        ALTER TABLE public.classes DROP COLUMN IF EXISTS level;
        """
    )
    _drop_constraint("classes", "classes_next_class_id_fkey")
    _drop_constraint("classes", "ck_classes_next_class_not_self")
    _drop_constraint("classes", "ck_classes_terminal_has_no_next_class")
    _exec(
        """
        ALTER TABLE public.classes
            ADD CONSTRAINT classes_next_class_id_fkey
                FOREIGN KEY (next_class_id) REFERENCES public.classes(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT ck_classes_next_class_not_self
                CHECK (next_class_id IS NULL OR next_class_id <> id),
            ADD CONSTRAINT ck_classes_terminal_has_no_next_class
                CHECK (
                    (is_terminal = true AND next_class_id IS NULL)
                    OR
                    (is_terminal = false)
                );
        CREATE INDEX IF NOT EXISTS ix_classes_tenant_next_class
            ON public.classes (tenant_id, next_class_id);
        CREATE INDEX IF NOT EXISTS ix_classes_tenant_terminal_active
            ON public.classes (tenant_id, is_terminal, is_active);
        """
    )

    _exec(
        """
        ALTER TABLE public.students
            ADD COLUMN IF NOT EXISTS promotion_hold BOOLEAN DEFAULT false NOT NULL,
            ADD COLUMN IF NOT EXISTS is_archived BOOLEAN DEFAULT false NOT NULL,
            ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS archived_by_admin_id UUID,
            ADD COLUMN IF NOT EXISTS archive_reason VARCHAR(500);
        """
    )
    _drop_constraint("students", "students_archived_by_admin_id_fkey")
    _drop_constraint("students", "ck_students_archive_consistency")
    _drop_constraint("students", "ck_students_terminal_status_has_no_current_class")
    _drop_constraint("students", "ck_students_graduated_has_date")
    _exec(
        """
        ALTER TABLE public.students
            ADD CONSTRAINT students_archived_by_admin_id_fkey
                FOREIGN KEY (archived_by_admin_id) REFERENCES public.tenant_admins(id)
                ON DELETE SET NULL,
            ADD CONSTRAINT ck_students_archive_consistency
                CHECK (
                    (
                        is_archived = false
                        AND archived_at IS NULL
                        AND archived_by_admin_id IS NULL
                        AND archive_reason IS NULL
                    )
                    OR
                    (
                        is_archived = true
                        AND archived_at IS NOT NULL
                        AND archive_reason IS NOT NULL
                    )
                ),
            ADD CONSTRAINT ck_students_terminal_status_has_no_current_class
                CHECK (status::text NOT IN ('withdrawn', 'expelled', 'graduated') OR class_id IS NULL),
            ADD CONSTRAINT ck_students_graduated_has_date
                CHECK (status::text <> 'graduated' OR graduation_date IS NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_students_tenant_archived
            ON public.students (tenant_id, is_archived);
        CREATE INDEX IF NOT EXISTS ix_students_tenant_class_status_archived
            ON public.students (tenant_id, class_id, status, is_archived);
        """
    )

    _exec(
        """
        CREATE TABLE IF NOT EXISTS public.student_enrollments (
            student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE RESTRICT,
            class_id UUID NOT NULL REFERENCES public.classes(id) ON DELETE RESTRICT,
            academic_session_id UUID NOT NULL REFERENCES public.academic_sessions(id) ON DELETE RESTRICT,
            started_on DATE NOT NULL,
            ended_on DATE,
            is_current BOOLEAN DEFAULT true NOT NULL,
            outcome public.student_enrollment_outcome DEFAULT 'enrolled' NOT NULL,
            reason VARCHAR(500),
            changed_by_admin_id UUID REFERENCES public.tenant_admins(id) ON DELETE SET NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT ck_student_enrollment_current_end_consistency
                CHECK (
                    (is_current = true AND ended_on IS NULL)
                    OR
                    (is_current = false AND ended_on IS NOT NULL)
                ),
            CONSTRAINT ck_student_enrollment_date_order
                CHECK (ended_on IS NULL OR ended_on >= started_on),
            UNIQUE (id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_student_enrollments_one_current
            ON public.student_enrollments (tenant_id, student_id)
            WHERE is_current = true;
        CREATE INDEX IF NOT EXISTS ix_student_enrollments_tenant_student
            ON public.student_enrollments (tenant_id, student_id);
        CREATE INDEX IF NOT EXISTS ix_student_enrollments_tenant_class
            ON public.student_enrollments (tenant_id, class_id);
        CREATE INDEX IF NOT EXISTS ix_student_enrollments_tenant_session
            ON public.student_enrollments (tenant_id, academic_session_id);
        CREATE INDEX IF NOT EXISTS ix_student_enrollments_student_session
            ON public.student_enrollments (student_id, academic_session_id);
        """
    )

    _exec(
        """
        CREATE TABLE IF NOT EXISTS public.parent_accounts (
            email VARCHAR(300) NOT NULL,
            password_hash VARCHAR(300) NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            phone_number VARCHAR(30),
            occupation VARCHAR(150),
            address VARCHAR(500),
            emergency_phone VARCHAR(30),
            account_status public.parent_account_status DEFAULT 'pending' NOT NULL,
            is_verified BOOLEAN DEFAULT false NOT NULL,
            is_active BOOLEAN DEFAULT true NOT NULL,
            last_login_at TIMESTAMP WITH TIME ZONE,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            CONSTRAINT uq_parent_accounts_email UNIQUE (email),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_parent_account_email
            ON public.parent_accounts (email);
        CREATE INDEX IF NOT EXISTS ix_parent_accounts_account_status
            ON public.parent_accounts (account_status);
        CREATE INDEX IF NOT EXISTS ix_parent_accounts_active_verified
            ON public.parent_accounts (is_active, is_verified);

        CREATE TABLE IF NOT EXISTS public.parent_memberships (
            parent_account_id UUID NOT NULL REFERENCES public.parent_accounts(id) ON DELETE RESTRICT,
            status public.parent_membership_status DEFAULT 'active' NOT NULL,
            joined_at TIMESTAMP WITH TIME ZONE,
            ended_at TIMESTAMP WITH TIME ZONE,
            end_reason VARCHAR(500),
            receive_email_notifications BOOLEAN DEFAULT true NOT NULL,
            receive_push_notifications BOOLEAN DEFAULT true NOT NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_parent_memberships_account_tenant
                UNIQUE (parent_account_id, tenant_id),
            CONSTRAINT ck_parent_membership_status_end_consistency
                CHECK (
                    (status IN ('active', 'read_only') AND ended_at IS NULL)
                    OR
                    (status = 'inactive')
                ),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_parent_memberships_tenant_status
            ON public.parent_memberships (tenant_id, status);
        CREATE INDEX IF NOT EXISTS ix_parent_memberships_tenant_account
            ON public.parent_memberships (tenant_id, parent_account_id);
        CREATE INDEX IF NOT EXISTS ix_parent_memberships_account_status
            ON public.parent_memberships (parent_account_id, status);
        """
    )

    _exec(
        """
        DO $$
        BEGIN
            IF to_regclass('public.parents') IS NOT NULL THEN
                INSERT INTO public.parent_accounts (
                    id,
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    phone_number,
                    occupation,
                    address,
                    emergency_phone,
                    account_status,
                    is_verified,
                    is_active,
                    last_login_at,
                    created_at,
                    updated_at
                )
                SELECT DISTINCT ON (lower(email))
                    id,
                    lower(email),
                    password_hash,
                    first_name,
                    last_name,
                    phone_number,
                    occupation,
                    address,
                    emergency_phone,
                    account_status,
                    is_verified,
                    is_active,
                    last_login_at,
                    created_at,
                    updated_at
                FROM public.parents
                ORDER BY lower(email), created_at, id
                ON CONFLICT (email) DO NOTHING;

                INSERT INTO public.parent_memberships (
                    id,
                    tenant_id,
                    parent_account_id,
                    status,
                    joined_at,
                    receive_email_notifications,
                    receive_push_notifications,
                    created_at,
                    updated_at
                )
                SELECT
                    p.id,
                    p.tenant_id,
                    pa.id,
                    CASE
                        WHEN p.is_active THEN 'active'::public.parent_membership_status
                        ELSE 'inactive'::public.parent_membership_status
                    END,
                    p.created_at,
                    true,
                    true,
                    p.created_at,
                    p.updated_at
                FROM public.parents p
                JOIN public.parent_accounts pa ON pa.email = lower(p.email)
                ON CONFLICT (id) DO NOTHING;
            END IF;
        END
        $$;
        """
    )

    _exec(
        """
        CREATE TABLE IF NOT EXISTS public.parent_invitations (
            student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE RESTRICT,
            invited_email VARCHAR(300) NOT NULL,
            relationship_type public.parentrelationship DEFAULT 'guardian' NOT NULL,
            admission_number_snapshot VARCHAR(100) NOT NULL,
            token_digest VARCHAR(255) NOT NULL,
            status public.parent_invitation_status DEFAULT 'pending' NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            accepted_at TIMESTAMP WITH TIME ZONE,
            revoked_at TIMESTAMP WITH TIME ZONE,
            created_by_admin_id UUID REFERENCES public.tenant_admins(id) ON DELETE SET NULL,
            accepted_by_parent_account_id UUID REFERENCES public.parent_accounts(id) ON DELETE SET NULL,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_parent_invitations_token_digest UNIQUE (token_digest),
            CONSTRAINT ck_parent_invitation_acceptance_consistency
                CHECK (
                    (
                        status = 'accepted'
                        AND accepted_at IS NOT NULL
                        AND accepted_by_parent_account_id IS NOT NULL
                    )
                    OR
                    (status <> 'accepted')
                ),
            CONSTRAINT ck_parent_invitation_revocation_consistency
                CHECK (
                    (status = 'revoked' AND revoked_at IS NOT NULL)
                    OR
                    (status <> 'revoked')
                ),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_parent_invitations_tenant_student
            ON public.parent_invitations (tenant_id, student_id);
        CREATE INDEX IF NOT EXISTS ix_parent_invitations_tenant_email_status
            ON public.parent_invitations (tenant_id, invited_email, status);
        CREATE INDEX IF NOT EXISTS ix_parent_invitations_expires_at
            ON public.parent_invitations (expires_at);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_parent_invitations_pending_student_email
            ON public.parent_invitations (tenant_id, student_id, invited_email)
            WHERE status = 'pending';
        """
    )

    _exec(
        """
        ALTER TABLE public.student_parent_links
            ADD COLUMN IF NOT EXISTS status public.student_parent_link_status DEFAULT 'active' NOT NULL,
            ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            ADD COLUMN IF NOT EXISTS verified_by_type public.parent_link_verified_by_type DEFAULT 'system' NOT NULL,
            ADD COLUMN IF NOT EXISTS verified_by_id UUID,
            ADD COLUMN IF NOT EXISTS ended_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS end_reason VARCHAR(500);

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = 'student_parent_links'
                    AND column_name = 'parent_id'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = 'student_parent_links'
                    AND column_name = 'parent_membership_id'
            ) THEN
                ALTER TABLE public.student_parent_links
                    RENAME COLUMN parent_id TO parent_membership_id;
            END IF;
        END
        $$;
        """
    )
    _drop_constraint("student_parent_links", "student_parent_links_parent_id_fkey")
    _drop_constraint("student_parent_links", "student_parent_links_parent_membership_id_fkey")
    _drop_constraint("student_parent_links", "uq_student_parent_tenant_student_parent")
    _drop_constraint("student_parent_links", "uq_student_parent_link_tenant_student_membership")
    _drop_constraint("student_parent_links", "ck_student_parent_link_status_end_consistency")
    _drop_constraint("student_parent_links", "ck_student_parent_link_ended_reason")
    _exec(
        """
        ALTER TABLE public.student_parent_links
            ADD CONSTRAINT student_parent_links_parent_membership_id_fkey
                FOREIGN KEY (parent_membership_id) REFERENCES public.parent_memberships(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT uq_student_parent_link_tenant_student_membership
                UNIQUE (tenant_id, student_id, parent_membership_id),
            ADD CONSTRAINT ck_student_parent_link_status_end_consistency
                CHECK (
                    (
                        status IN ('active', 'read_only', 'alumni_read_only')
                        AND ended_at IS NULL
                    )
                    OR
                    (
                        status = 'ended'
                        AND ended_at IS NOT NULL
                    )
                ),
            ADD CONSTRAINT ck_student_parent_link_ended_reason
                CHECK (
                    (status = 'ended' AND end_reason IS NOT NULL)
                    OR
                    (status <> 'ended')
                );
        DROP INDEX IF EXISTS public.ix_student_parent_links_tenant_parent;
        CREATE INDEX IF NOT EXISTS ix_student_parent_links_tenant_membership
            ON public.student_parent_links (tenant_id, parent_membership_id);
        CREATE INDEX IF NOT EXISTS ix_student_parent_links_tenant_status
            ON public.student_parent_links (tenant_id, status);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_student_parent_links_primary_contact
            ON public.student_parent_links (tenant_id, student_id)
            WHERE is_primary_contact = true
                AND status IN ('active', 'read_only', 'alumni_read_only');
        """
    )

    _exec(
        """
        ALTER TABLE public.student_parent_link_requests
            ADD COLUMN IF NOT EXISTS invitation_id UUID,
            ADD COLUMN IF NOT EXISTS parent_account_id UUID,
            ADD COLUMN IF NOT EXISTS parent_membership_id UUID,
            ADD COLUMN IF NOT EXISTS responded_by_type public.parent_link_verified_by_type,
            ADD COLUMN IF NOT EXISTS responded_by_id UUID,
            ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(500);

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = 'student_parent_link_requests'
                    AND column_name = 'parent_id'
            ) THEN
                UPDATE public.student_parent_link_requests spr
                SET
                    parent_membership_id = COALESCE(parent_membership_id, spr.parent_id),
                    parent_account_id = COALESCE(parent_account_id, pm.parent_account_id)
                FROM public.parent_memberships pm
                WHERE spr.parent_id = pm.id
                    AND spr.parent_account_id IS NULL;
            END IF;
        END
        $$;
        """
    )
    _exec(
        """
        INSERT INTO public.parent_invitations (
            id,
            tenant_id,
            student_id,
            invited_email,
            relationship_type,
            admission_number_snapshot,
            token_digest,
            status,
            expires_at,
            accepted_at,
            accepted_by_parent_account_id,
            created_at,
            updated_at
        )
        SELECT
            (
                substr(md5(spr.id::text || ':parent_invitation'), 1, 8)
                || '-'
                || substr(md5(spr.id::text || ':parent_invitation'), 9, 4)
                || '-'
                || substr(md5(spr.id::text || ':parent_invitation'), 13, 4)
                || '-'
                || substr(md5(spr.id::text || ':parent_invitation'), 17, 4)
                || '-'
                || substr(md5(spr.id::text || ':parent_invitation'), 21, 12)
            )::uuid,
            spr.tenant_id,
            spr.student_id,
            pa.email,
            spr.relationship_type,
            spr.admission_number_snapshot,
            md5(spr.id::text),
            CASE
                WHEN spr.status::text = 'approved' THEN 'accepted'::public.parent_invitation_status
                WHEN spr.status::text = 'expired' THEN 'expired'::public.parent_invitation_status
                WHEN spr.status::text = 'cancelled' THEN 'revoked'::public.parent_invitation_status
                ELSE 'pending'::public.parent_invitation_status
            END,
            now(),
            CASE WHEN spr.status::text = 'approved' THEN spr.responded_at ELSE NULL END,
            CASE WHEN spr.status::text = 'approved' THEN spr.parent_account_id ELSE NULL END,
            spr.created_at,
            spr.updated_at
        FROM public.student_parent_link_requests spr
        JOIN public.parent_accounts pa ON pa.id = spr.parent_account_id
        WHERE spr.invitation_id IS NULL
        ON CONFLICT (token_digest) DO NOTHING;

        UPDATE public.student_parent_link_requests spr
        SET invitation_id = pi.id
        FROM public.parent_invitations pi
        WHERE pi.token_digest = md5(spr.id::text)
            AND spr.invitation_id IS NULL;
        """
    )
    _drop_constraint("student_parent_link_requests", "student_parent_link_requests_parent_id_fkey")
    _drop_constraint("student_parent_link_requests", "student_parent_link_requests_parent_account_id_fkey")
    _drop_constraint("student_parent_link_requests", "student_parent_link_requests_parent_membership_id_fkey")
    _drop_constraint("student_parent_link_requests", "student_parent_link_requests_invitation_id_fkey")
    _drop_constraint("student_parent_link_requests", "uq_student_parent_link_requests_invitation")
    _drop_constraint("student_parent_link_requests", "ck_parent_link_request_response_consistency")
    _drop_constraint("student_parent_link_requests", "ck_parent_link_request_rejection_reason")
    _exec(
        """
        ALTER TABLE public.student_parent_link_requests
            ALTER COLUMN invitation_id SET NOT NULL,
            ALTER COLUMN parent_account_id SET NOT NULL,
            DROP COLUMN IF EXISTS parent_id,
            ADD CONSTRAINT student_parent_link_requests_invitation_id_fkey
                FOREIGN KEY (invitation_id) REFERENCES public.parent_invitations(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT student_parent_link_requests_parent_account_id_fkey
                FOREIGN KEY (parent_account_id) REFERENCES public.parent_accounts(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT student_parent_link_requests_parent_membership_id_fkey
                FOREIGN KEY (parent_membership_id) REFERENCES public.parent_memberships(id)
                ON DELETE RESTRICT,
            ADD CONSTRAINT uq_student_parent_link_requests_invitation
                UNIQUE (invitation_id),
            ADD CONSTRAINT ck_parent_link_request_response_consistency
                CHECK (
                    (
                        status = 'pending'
                        AND responded_at IS NULL
                        AND responded_by_type IS NULL
                        AND responded_by_id IS NULL
                    )
                    OR
                    (
                        status <> 'pending'
                        AND responded_at IS NOT NULL
                    )
                ),
            ADD CONSTRAINT ck_parent_link_request_rejection_reason
                CHECK (status <> 'rejected' OR rejection_reason IS NOT NULL);
        DROP INDEX IF EXISTS public.ix_student_parent_link_requests_tenant_parent;
        CREATE INDEX IF NOT EXISTS ix_student_parent_link_requests_tenant_membership
            ON public.student_parent_link_requests (tenant_id, parent_membership_id);
        CREATE INDEX IF NOT EXISTS ix_student_parent_link_requests_tenant_account
            ON public.student_parent_link_requests (tenant_id, parent_account_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_student_parent_link_requests_pending_account_student
            ON public.student_parent_link_requests (tenant_id, student_id, parent_account_id)
            WHERE status = 'pending';
        """
    )

    _exec(
        """
        ALTER TABLE public.announcement_targets
            ADD COLUMN IF NOT EXISTS parent_membership_id UUID;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = 'announcement_targets'
                    AND column_name = 'parent_id'
            ) THEN
                UPDATE public.announcement_targets
                SET parent_membership_id = parent_id
                WHERE parent_membership_id IS NULL
                    AND parent_id IS NOT NULL;
            END IF;
        END
        $$;
        """
    )
    _drop_constraint("announcement_targets", "announcement_targets_parent_id_fkey")
    _drop_constraint("announcement_targets", "announcement_targets_parent_membership_id_fkey")
    _drop_constraint("announcement_targets", "uq_announcement_target_rule")
    _exec(
        """
        ALTER TABLE public.announcement_targets
            DROP COLUMN IF EXISTS parent_id,
            ADD CONSTRAINT announcement_targets_parent_membership_id_fkey
                FOREIGN KEY (parent_membership_id) REFERENCES public.parent_memberships(id)
                ON DELETE CASCADE,
            ADD CONSTRAINT uq_announcement_target_rule
                UNIQUE (
                    tenant_id,
                    announcement_id,
                    target_type,
                    role,
                    class_id,
                    student_id,
                    parent_membership_id,
                    teacher_id
                );
        CREATE INDEX IF NOT EXISTS ix_announcement_targets_parent_membership_id
            ON public.announcement_targets (parent_membership_id);
        """
    )

    _exec(
        """
        CREATE TABLE IF NOT EXISTS public.student_progression_runs (
            academic_session_id UUID NOT NULL REFERENCES public.academic_sessions(id) ON DELETE RESTRICT,
            next_academic_session_id UUID NOT NULL REFERENCES public.academic_sessions(id) ON DELETE RESTRICT,
            idempotency_key VARCHAR(150) NOT NULL,
            status public.student_progression_run_status DEFAULT 'pending' NOT NULL,
            total_students INTEGER DEFAULT 0 NOT NULL,
            promoted_students INTEGER DEFAULT 0 NOT NULL,
            graduated_students INTEGER DEFAULT 0 NOT NULL,
            skipped_students INTEGER DEFAULT 0 NOT NULL,
            failed_students INTEGER DEFAULT 0 NOT NULL,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            initiated_by_admin_id UUID REFERENCES public.tenant_admins(id) ON DELETE SET NULL,
            failure_reason VARCHAR(1000),
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_student_progression_run_tenant_idempotency
                UNIQUE (tenant_id, idempotency_key),
            CONSTRAINT uq_student_progression_run_tenant_session
                UNIQUE (tenant_id, academic_session_id),
            CONSTRAINT ck_progression_run_nonnegative_counts
                CHECK (
                    total_students >= 0
                    AND promoted_students >= 0
                    AND graduated_students >= 0
                    AND skipped_students >= 0
                    AND failed_students >= 0
                ),
            CONSTRAINT ck_progression_run_count_total
                CHECK (
                    promoted_students
                    + graduated_students
                    + skipped_students
                    + failed_students
                    <= total_students
                ),
            CONSTRAINT ck_progression_run_completion_consistency
                CHECK (
                    (status IN ('pending', 'processing') AND completed_at IS NULL)
                    OR
                    (status IN ('completed', 'failed') AND completed_at IS NOT NULL)
                ),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_student_progression_runs_tenant_status
            ON public.student_progression_runs (tenant_id, status);
        CREATE INDEX IF NOT EXISTS ix_student_progression_runs_tenant_session
            ON public.student_progression_runs (tenant_id, academic_session_id);

        CREATE TABLE IF NOT EXISTS public.student_progression_items (
            progression_run_id UUID NOT NULL REFERENCES public.student_progression_runs(id) ON DELETE RESTRICT,
            student_id UUID NOT NULL REFERENCES public.students(id) ON DELETE RESTRICT,
            from_enrollment_id UUID REFERENCES public.student_enrollments(id) ON DELETE RESTRICT,
            to_enrollment_id UUID REFERENCES public.student_enrollments(id) ON DELETE RESTRICT,
            from_class_id UUID NOT NULL REFERENCES public.classes(id) ON DELETE RESTRICT,
            to_class_id UUID REFERENCES public.classes(id) ON DELETE RESTRICT,
            action public.student_progression_item_action NOT NULL,
            status public.student_progression_item_status NOT NULL,
            reason VARCHAR(1000),
            processed_at TIMESTAMP WITH TIME ZONE,
            id UUID PRIMARY KEY,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            tenant_id UUID NOT NULL REFERENCES public.tenants(id),
            CONSTRAINT uq_progression_item_run_student
                UNIQUE (progression_run_id, student_id),
            CONSTRAINT ck_progression_item_promotion_has_target
                CHECK (action <> 'promote' OR to_class_id IS NOT NULL),
            CONSTRAINT ck_progression_item_graduation_no_target
                CHECK (action <> 'graduate' OR to_class_id IS NULL),
            UNIQUE (id)
        );
        CREATE INDEX IF NOT EXISTS ix_progression_items_tenant_run
            ON public.student_progression_items (tenant_id, progression_run_id);
        CREATE INDEX IF NOT EXISTS ix_progression_items_tenant_student
            ON public.student_progression_items (tenant_id, student_id);
        CREATE INDEX IF NOT EXISTS ix_progression_items_tenant_status
            ON public.student_progression_items (tenant_id, status);
        """
    )

    _exec("DROP TABLE IF EXISTS public.student_link_codes")
    _exec("DROP TABLE IF EXISTS public.parents")


def downgrade() -> None:
    """Downgrade schema."""

    _exec("DROP TABLE IF EXISTS public.student_progression_items")
    _exec("DROP TABLE IF EXISTS public.student_progression_runs")
    _exec("DROP TABLE IF EXISTS public.parent_invitations")
    _exec("DROP TABLE IF EXISTS public.student_enrollments")

    _exec(
        """
        ALTER TABLE public.announcement_targets
            ADD COLUMN IF NOT EXISTS parent_id UUID;
        UPDATE public.announcement_targets
        SET parent_id = parent_membership_id
        WHERE parent_id IS NULL;
        ALTER TABLE public.announcement_targets
            DROP COLUMN IF EXISTS parent_membership_id;
        """
    )

    _exec(
        """
        ALTER TABLE public.student_parent_link_requests
            ADD COLUMN IF NOT EXISTS parent_id UUID;
        UPDATE public.student_parent_link_requests
        SET parent_id = parent_membership_id
        WHERE parent_id IS NULL;
        ALTER TABLE public.student_parent_link_requests
            DROP COLUMN IF EXISTS invitation_id,
            DROP COLUMN IF EXISTS parent_account_id,
            DROP COLUMN IF EXISTS parent_membership_id,
            DROP COLUMN IF EXISTS responded_by_type,
            DROP COLUMN IF EXISTS responded_by_id,
            DROP COLUMN IF EXISTS rejection_reason;
        """
    )

    _exec(
        """
        ALTER TABLE public.student_parent_links
            ADD COLUMN IF NOT EXISTS parent_id UUID;
        UPDATE public.student_parent_links
        SET parent_id = parent_membership_id
        WHERE parent_id IS NULL;
        ALTER TABLE public.student_parent_links
            DROP COLUMN IF EXISTS parent_membership_id,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS verified_at,
            DROP COLUMN IF EXISTS verified_by_type,
            DROP COLUMN IF EXISTS verified_by_id,
            DROP COLUMN IF EXISTS ended_at,
            DROP COLUMN IF EXISTS end_reason;
        """
    )

    _exec("DROP TABLE IF EXISTS public.parent_memberships")
    _exec("DROP TABLE IF EXISTS public.parent_accounts")

    _exec(
        """
        ALTER TABLE public.students
            DROP COLUMN IF EXISTS promotion_hold,
            DROP COLUMN IF EXISTS is_archived,
            DROP COLUMN IF EXISTS archived_at,
            DROP COLUMN IF EXISTS archived_by_admin_id,
            DROP COLUMN IF EXISTS archive_reason;

        ALTER TABLE public.classes
            ADD COLUMN IF NOT EXISTS level VARCHAR(100),
            DROP COLUMN IF EXISTS next_class_id,
            DROP COLUMN IF EXISTS is_terminal;

        ALTER TABLE public.academic_sessions
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS closing_started_at,
            DROP COLUMN IF EXISTS closed_at,
            DROP COLUMN IF EXISTS closed_by_admin_id,
            DROP COLUMN IF EXISTS next_academic_session_id;
        """
    )

    _exec("DROP TYPE IF EXISTS public.student_progression_item_action")
    _exec("DROP TYPE IF EXISTS public.student_progression_item_status")
    _exec("DROP TYPE IF EXISTS public.student_progression_run_status")
    _exec("DROP TYPE IF EXISTS public.parent_invitation_status")
    _exec("DROP TYPE IF EXISTS public.parent_membership_status")
    _exec("DROP TYPE IF EXISTS public.parent_link_verified_by_type")
    _exec("DROP TYPE IF EXISTS public.student_parent_link_status")
    _exec("DROP TYPE IF EXISTS public.student_enrollment_outcome")
    _exec("DROP TYPE IF EXISTS public.academic_session_status")
