#==========================#
#   Announcement model     #
#==========================#

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import BaseModel, PUBLIC_SCHEMA


class AnnouncementCategory(str, PyEnum):
    """Categories used to classify announcements by purpose or audience."""
    GENERAL = "general"
    ACADEMIC = "academic"
    EXAMINATION = "examination"
    ASSIGNMENT = "assignment"
    ATTENDANCE = "attendance"
    EVENT = "event"
    HOLIDAY = "holiday"
    FINANCE = "finance"
    DISCIPLINE = "discipline"
    SPORTS = "sports"
    CLUB_ACTIVITY = "club_activity"
    HEALTH = "health"
    TRANSPORT = "transport"
    EMERGENCY = "emergency"
    SYSTEM = "system"


class AnnouncementPriority(str, PyEnum):
    """Priority levels used to indicate how urgently an announcement should be noticed."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AnnouncementStatus(str, PyEnum):
    """Lifecycle states for an announcement from draft to archive."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    CANCELLED = "cancelled"


class AnnouncementActorType(str, PyEnum):
    """Actor roles that are allowed to create or manage announcements."""
    SUPERADMIN = "superadmin"
    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"


class AnnouncementTargetType(str, PyEnum):
    """Targeting scopes that define who an announcement should be delivered to."""
    ALL = "all"
    ROLE = "role"
    CLASS = "class"
    SPECIFIC_PARENT = "specific_parent"
    SPECIFIC_STUDENT = "specific_student"
    SPECIFIC_TEACHER = "specific_teacher"
    PARENTS_OF_STUDENT = "parents_of_student"
    PARENTS_OF_CLASS = "parents_of_class"


class AnnouncementRecipientRole(str, PyEnum):
    """Recipient roles used when an announcement targets a user category."""
    TENANT_ADMIN = "tenant_admin"
    TEACHER = "teacher"
    PARENT = "parent"
    STUDENT = "student"


class AnnouncementReadStatus(str, PyEnum):
    """Announcement read lifecycle."""
    UNREAD = "unread"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"


class Announcement(BaseModel):
    __tablename__ = "announcements"

    __table_args__ = (
        Index(
            "ix_announcements_tenant_status_feed",
            "tenant_id",
            "status",
            "is_pinned",
            "created_at",
        ),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[AnnouncementCategory] = mapped_column(
        SQLEnum(
            AnnouncementCategory,
            name="announcement_category",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
        default=AnnouncementCategory.GENERAL,
    )

    priority: Mapped[AnnouncementPriority] = mapped_column(
        SQLEnum(
            AnnouncementPriority,
            name="announcement_priority",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
        default=AnnouncementPriority.NORMAL,
    )

    status: Mapped[AnnouncementStatus] = mapped_column(
        SQLEnum(
            AnnouncementStatus,
            name="announcement_status",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
        default=AnnouncementStatus.DRAFT,
    )

    created_by_actor_type: Mapped[AnnouncementActorType] = mapped_column(
        SQLEnum(
            AnnouncementActorType,
            name="announcement_actor_type",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
    )

    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        nullable=False,
        index=True,
    )

    publish_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    targets: Mapped[list["AnnouncementTarget"]] = relationship(
        "AnnouncementTarget",
        back_populates="announcement",
        cascade="all, delete-orphan",
    )

    reads: Mapped[list["AnnouncementRead"]] = relationship(
        "AnnouncementRead",
        back_populates="announcement",
        cascade="all, delete-orphan",
    )


class AnnouncementTarget(BaseModel):
    __tablename__ = "announcement_targets"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "announcement_id",
            "target_type",
            "role",
            "class_id",
            "student_id",
            "parent_membership_id",
            "teacher_membership_id",
            name="uq_announcement_target_rule",
        ),
    )

    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_type: Mapped[AnnouncementTargetType] = mapped_column(
        SQLEnum(
            AnnouncementTargetType,
            name="announcement_target_type",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
    )

    role: Mapped[AnnouncementRecipientRole | None] = mapped_column(
        SQLEnum(
            AnnouncementRecipientRole,
            name="announcement_recipient_role",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=True,
    )

    class_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    parent_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parent_memberships.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    teacher_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teacher_memberships.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="targets",
    )


class AnnouncementRead(BaseModel):
    __tablename__ = "announcement_reads"

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "announcement_id",
            "actor_type",
            "actor_id",
            name="uq_announcement_read_actor",
        ),
        Index(
            "ix_announcement_reads_actor_status",
            "tenant_id",
            "actor_type",
            "actor_id",
            "status",
        ),
    )

    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    actor_type: Mapped[AnnouncementRecipientRole] = mapped_column(
        SQLEnum(
            AnnouncementRecipientRole,
            name="announcement_read_actor_type",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        nullable=False,
        index=True,
    )

    status: Mapped[AnnouncementReadStatus] = mapped_column(
        SQLEnum(
            AnnouncementReadStatus,
            name="announcement_read_status",
            schema=PUBLIC_SCHEMA,
        ),
        nullable=False,
        default=AnnouncementReadStatus.UNREAD,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    announcement: Mapped["Announcement"] = relationship(
        "Announcement",
        back_populates="reads",
    )
