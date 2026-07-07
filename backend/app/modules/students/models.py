#==========================#
#  student model.py#
#==========================#
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum as PyEnum
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA

if TYPE_CHECKING:
    from app.modules.parents.models import Parent


class Gender(str, PyEnum):
    MALE = "male"
    FEMALE = "female"


class AcademicStatus(str, PyEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    SUSPENDED = "suspended"
    GRADUATED = "graduated"


class ParentRelationship(str, PyEnum):
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    SPONSOR = "sponsor"
    OTHER = "other"


class StudentProfileStatus(str, PyEnum):
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"


class StudentAccountStatus(str, PyEnum):
    """Student account lifecycle status."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"


class StudentAccessCodePurpose(str, PyEnum):
    """Reason why a temporary student access code was created."""

    INITIAL_SETUP = "initial_setup"
    PASSWORD_RESET = "password_reset"


class StudentParentLinkRequestStatus(str, PyEnum):
    """Lifecycle states for parent-student link approval requests."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class Student(BaseModel):
    """Student actor account and academic profile."""

    __tablename__ = "students"

    admission_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Nullable because a new student may not have created their real password yet.
    # Initial access is handled through StudentAccessCode.
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    account_status: Mapped[StudentAccountStatus] = mapped_column(
        SQLEnum(
            StudentAccountStatus,
            name="student_account_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=StudentAccountStatus.ACTIVE,
        server_default=StudentAccountStatus.ACTIVE.value,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    password_reset_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Admin-controlled field. Students should not be allowed to edit this
    # through student self-service schemas.
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    gender: Mapped[Gender | None] = mapped_column(
        SQLEnum(
            Gender,
            name="studentgender",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=True,
    )

    # Admin-controlled for now. Keep length limited.
    state_of_origin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    passport_photo_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    admission_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )

    graduation_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=True,
    )

    arm: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    status: Mapped[AcademicStatus] = mapped_column(
        SQLEnum(
            AcademicStatus,
            name="academicstatus",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=AcademicStatus.ACTIVE,
        server_default=AcademicStatus.ACTIVE.value,
    )

    profile_status: Mapped[StudentProfileStatus] = mapped_column(
        SQLEnum(
            StudentProfileStatus,
            name="studentprofilestatus",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=StudentProfileStatus.INCOMPLETE,
        server_default=StudentProfileStatus.INCOMPLETE.value,
    )

    parent_links: Mapped[list["StudentParentLink"]] = relationship(
        "StudentParentLink",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    link_codes: Mapped[list["StudentLinkCode"]] = relationship(
        "StudentLinkCode",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    parent_link_requests: Mapped[list["StudentParentLinkRequest"]] = relationship(
        "StudentParentLinkRequest",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    access_codes: Mapped[list["StudentAccessCode"]] = relationship(
        "StudentAccessCode",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    @property
    def parents(self) -> list["Parent"]:
        """Return linked parents."""

        return [link.parent for link in self.parent_links if link.parent is not None]

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "admission_number",
            name="uq_students_tenant_admission_number",
        ),
        Index("ix_students_tenant_admission_number", "tenant_id", "admission_number"),
        Index("ix_students_tenant_class", "tenant_id", "class_id"),
        Index("ix_students_tenant_status", "tenant_id", "status"),
        Index("ix_students_tenant_account_status", "tenant_id", "account_status"),
    )


class StudentAccessCode(BaseModel):
    """Temporary code used for student first login or password reset."""

    __tablename__ = "student_access_codes"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Store a deterministic digest of the code, not the plain code.
    # The plain code should only be returned once to the admin.
    code_digest: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    purpose: Mapped[StudentAccessCodePurpose] = mapped_column(
        SQLEnum(
            StudentAccessCodePurpose,
            name="student_access_code_purpose",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_admins.id", ondelete="SET NULL"),
        nullable=True,
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="access_codes",
    )

    __table_args__ = (
        Index("ix_student_access_codes_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_access_codes_tenant_code_digest", "tenant_id", "code_digest"),
        Index("ix_student_access_codes_tenant_student_used", "tenant_id", "student_id", "is_used"),
        Index("ix_student_access_codes_expires_at", "expires_at"),
        Index("ix_student_access_codes_is_used", "is_used"),
    )


class StudentParentLink(BaseModel):
    """Many-to-many link between students and parents."""

    __tablename__ = "student_parent_links"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parents.id", ondelete="CASCADE"),
        nullable=False,
    )

    relationship_type: Mapped[ParentRelationship] = mapped_column(
        SQLEnum(
            ParentRelationship,
            name="parentrelationship",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ParentRelationship.GUARDIAN,
        server_default=ParentRelationship.GUARDIAN.value,
    )

    is_primary_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    receives_academic_updates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    receives_fee_updates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="parent_links",
    )

    parent: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="student_links",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "parent_id",
            name="uq_student_parent_tenant_student_parent",
        ),
        Index("ix_student_parent_links_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_parent_links_tenant_parent", "tenant_id", "parent_id"),
    )


class StudentParentLinkRequest(BaseModel):
    """Pending parent request that requires student approval before linking."""

    __tablename__ = "student_parent_link_requests"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parents.id", ondelete="CASCADE"),
        nullable=False,
    )

    admission_number_snapshot: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    relationship_type: Mapped[ParentRelationship] = mapped_column(
        SQLEnum(
            ParentRelationship,
            name="parentrelationship",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ParentRelationship.GUARDIAN,
        server_default=ParentRelationship.GUARDIAN.value,
    )

    status: Mapped[StudentParentLinkRequestStatus] = mapped_column(
        SQLEnum(
            StudentParentLinkRequestStatus,
            name="student_parent_link_request_status",
            schema=PUBLIC_SCHEMA,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=StudentParentLinkRequestStatus.PENDING,
        server_default=StudentParentLinkRequestStatus.PENDING.value,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="parent_link_requests",
    )

    parent: Mapped["Parent"] = relationship(
        "Parent",
        back_populates="student_link_requests",
    )

    __table_args__ = (
        Index(
            "ix_student_parent_link_requests_tenant_student",
            "tenant_id",
            "student_id",
        ),
        Index(
            "ix_student_parent_link_requests_tenant_parent",
            "tenant_id",
            "parent_id",
        ),
        Index(
            "ix_student_parent_link_requests_tenant_status",
            "tenant_id",
            "status",
        ),
    )


class StudentLinkCode(BaseModel):
    """Code used by parents to link themselves to a student."""

    __tablename__ = "student_link_codes"

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    max_use: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    use_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="link_codes",
    )

    @staticmethod
    def generate_code() -> str:
        """Generate a parent-student linking code."""

        return f"STU{token_urlsafe(6).upper()}"

    @property
    def is_expired(self) -> bool:
        """Return whether the link code has expired."""

        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_exhausted(self) -> bool:
        """Return whether the link code has reached max use."""

        return self.use_count >= self.max_use

    @property
    def is_active(self) -> bool:
        """Return whether the link code can still be used."""

        return self.used_at is None and not self.is_expired and not self.is_exhausted

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_student_link_codes_tenant_code"),
        Index("ix_student_link_codes_tenant_student", "tenant_id", "student_id"),
        Index("ix_student_link_codes_tenant_code", "tenant_id", "code"),
    )