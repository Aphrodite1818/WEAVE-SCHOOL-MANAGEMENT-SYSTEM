#==========================#
#     parents.models.py    #
#==========================#

"""Global parent identity model supports cross-tenant relationship"""


from __future__ import annotations

import uuid 
from datetime import datetime , timezone
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import(
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped , mapped_column , relationship

from app.shared.mixins import TimestampMixin , UUIDMixin
from app.shared.base_model import PUBLIC_SCHEMA, Base , BaseModel
from app.modules.students.models import ParentRelationship



if TYPE_CHECKING:
    from app.modules.students.models import StudentParentLink


def enum_values(enum_cls : type[PyEnum]) -> list[Any]:
    """Persist enum values rather than python enum member names"""

    return [item.value for item in enum_cls]



class ParentAccountStatus(str , PyEnum):
    """Global parent login-account status"""


    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"


class ParentMembershipStatus(str , PyEnum):
    """parent's relationship with a particular tenant"""

    ACTIVE = "active"
    READ_ONLY = "read_only"
    INACTIVE = "inactive"



class ParentInvitationStatus(str , PyEnum):
    """Lifecycle of an invitation sent by a school"""


    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"



class ParentAccount(UUIDMixin , TimestampMixin  , Base):
    """
    Global parent login identity

    This model is intentionally not tenant-scoped . One human parent owns one 
    account and may hold memberships in several tenants
    """

    __tablename__ = "parent_accounts"

    email : Mapped[str] = mapped_column(
        String(300),
        nullable = False
    )


    password_hash : Mapped[str] = mapped_column(
        String(300),
        nullable = False
    )


    first_name : Mapped[str | None] = mapped_column(
        String(100),
        nullable = True
    )


    last_name : Mapped[str | None] = mapped_column(
        String(100),
        nullable = True
    )


    phone_number : Mapped[str | None] = mapped_column(
        String(30),
        nullable=True
    )


    occupation : Mapped[str | None] = mapped_column(
        String(150),
        nullable = True
    )



    address : Mapped[str | None] = mapped_column(
        String(500),
        nullable  = True
    )


    emergency_phone : Mapped[str | None] = mapped_column(
        String(30),
        nullable = True
    )


    account_status : Mapped[ParentAccountStatus] = mapped_column(
        SQLEnum(ParentAccountStatus , 
                name = "parent_account_status",
                schema = PUBLIC_SCHEMA,
                values_callable = enum_values
                ),
        nullable = False ,
        default = ParentAccountStatus.PENDING,
        server_default=ParentAccountStatus.PENDING.value
    )


    is_verified : Mapped[bool] = mapped_column(
        Boolean,
        nullable = False ,
        default = False,
        server_default = "false"
    )

    is_active : Mapped[bool] = mapped_column(
        Boolean ,
        nullable = False,
        default = True,
        server_default="true"
    )

    last_login_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable = True 
    )

    memberships: Mapped[list["ParentMembership"]] = relationship(
    "ParentMembership",
    back_populates="parent_account",
    # Auto-save new/updated memberships when the parent is saved, but
    # deliberately excludes "delete"/"delete-orphan" — deleting a
    # ParentAccount must NEVER cascade-delete ParentMembership rows.
    # Schools own their membership records; they must survive even if
    # the parent's global account is removed.
    cascade="save-update, merge",
    # Don't load/manage child memberships in Python when a parent is
    # deleted — trust the DB's own ON DELETE rule on the FK instead
    # (must be set explicitly in the migration, e.g. RESTRICT or SET NULL).
    passive_deletes=True
    )



    __table_args__ = (
        UniqueConstraint(
            "email",
            name = "uq_parent_accounts_email"
        ),

        Index(
            "ix_parent_account_email",
            "email"
        ),

        Index(
            "ix_parent_accounts_account_status",
            "account_status"
        ),

        Index(
            "ix_parent_accounts_active_verified",
            "is_active",
            "is_verified"
        )
    )


    @property
    def profile_completed(self) -> bool:
        """Return whether required parent profile fields are present"""

        return bool(
            self.first_name
            and self.first_name.strip()
            and self.last_name
            and self.last_name.strip()
        )
    






class ParentMembership(BaseModel):
    """
    Tenant-scoped relationship between a parent account and a school 
    A membership identifies the parent inside one tenant but does not grant access to any student by itself
    """

    __tablename__ = "parent_memberships"

    parent_account_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid = True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.parent_accounts.id",
            ondelete = "RESTRICT"
        ),
        nullable=False
    )


    status : Mapped[ParentMembershipStatus] = mapped_column(
        SQLEnum(
            ParentMembershipStatus,
            name = "parent_membership_status",
            values_callable = enum_values,
            schema = PUBLIC_SCHEMA
        ),

        nullable = False,
        default = ParentMembershipStatus.ACTIVE,
        server_default = ParentMembershipStatus.ACTIVE.value
    )


    joined_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone = True),
        nullable = True
    )


    ended_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone = True),
        nullable = True
    )

    end_reason : Mapped[str | None] = mapped_column(
        String(500),
        nullable = True
    )


    receive_email_notifications : Mapped[bool] = mapped_column(
        Boolean ,
        nullable = False,
        default = True ,
        server_default="true"
    )


    receive_push_notifications: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    parent_account: Mapped["ParentAccount"] = relationship(
        "ParentAccount",
        back_populates="memberships",
    )

    student_links: Mapped[list["StudentParentLink"]] = relationship(
        "StudentParentLink",
        back_populates="parent_membership",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    student_link_requests: Mapped[list["StudentParentLinkRequest"]] = relationship(
        "StudentParentLinkRequest",
        back_populates="parent_membership",
        cascade="save-update, merge",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "parent_account_id",
            "tenant_id",
            name="uq_parent_memberships_account_tenant",
        ),
        CheckConstraint(
            """
            (
                status IN ('active', 'read_only')
                AND ended_at IS NULL
            )
            OR
            (
                status = 'inactive'
            )
            """,
            name="ck_parent_membership_status_end_consistency",
        ),
        Index(
            "ix_parent_memberships_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_parent_memberships_tenant_account",
            "tenant_id",
            "parent_account_id",
        ),
        Index(
            "ix_parent_memberships_account_status",
            "parent_account_id",
            "status",
        ),
    )






class ParentInvitation(BaseModel):
    """
    Tenant-scoped invitation for a specific student and parent email

    Creating an invitation does not create a global ParentAccount or a 
    ParentMembership
    """

    __tablename__ = "parent_invitations"

    student_id : Mapped[uuid.UUID]  = mapped_column(
        ForeignKey(
            f"{PUBLIC_SCHEMA}.students.id",
            ondelete = "RESTRICT"
        ),
        nullable = False
    )

    invited_email : Mapped[str] = mapped_column(
        String(300),
        nullable = False
    )


    relationship_type : Mapped[ParentRelationship] = mapped_column(
        SQLEnum(
            ParentRelationship,
            name="parentrelationship",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ParentRelationship.GUARDIAN,
        server_default=ParentRelationship.GUARDIAN.value,
    )


    admission_number_snapshot : Mapped[str] = mapped_column(
        String(100),
        nullable = False
    )


    token_digest: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )


    status : Mapped[ParentInvitationStatus] = mapped_column(
        SQLEnum(
            ParentInvitationStatus,
            name = "parent_invitation_status",
            schema = PUBLIC_SCHEMA,
            values_callable = enum_values
        ),
        nullable = False,
        default = ParentInvitationStatus.PENDING,
        server_default=ParentInvitationStatus.PENDING.value
    )



    expires_at : Mapped[datetime] = mapped_column(
        DateTime(timezone = True),
        nullable = False
    )


    accepted_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone = True),
        nullable = True
    )

    revoked_at : Mapped[datetime | None] = mapped_column(
        DateTime(timezone = True),
        nullable = True
    )



    created_by_admin_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid = True),
        ForeignKey(
             f"{PUBLIC_SCHEMA}.tenant_admins.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


    accepted_by_parent_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            f"{PUBLIC_SCHEMA}.parent_accounts.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "token_digest",
            name="uq_parent_invitations_token_digest",
        ),
        CheckConstraint(
            """
            (
                status = 'accepted'
                AND accepted_at IS NOT NULL
                AND accepted_by_parent_account_id IS NOT NULL
            )
            OR
            (
                status <> 'accepted'
            )
            """,
            name="ck_parent_invitation_acceptance_consistency",
        ),
        CheckConstraint(
            """
            (
                status = 'revoked'
                AND revoked_at IS NOT NULL
            )
            OR
            (
                status <> 'revoked'
            )
            """,
            name="ck_parent_invitation_revocation_consistency",
        ),
        Index(
            "ix_parent_invitations_tenant_student",
            "tenant_id",
            "student_id",
        ),
        Index(
            "ix_parent_invitations_tenant_email_status",
            "tenant_id",
            "invited_email",
            "status",
        ),
        Index(
            "ix_parent_invitations_expires_at",
            "expires_at",
        ),
        Index(
            "uq_parent_invitations_pending_student_email",
            "tenant_id",
            "student_id",
            "invited_email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )
