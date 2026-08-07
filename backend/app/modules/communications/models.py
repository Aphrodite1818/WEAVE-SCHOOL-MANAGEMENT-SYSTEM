"""Canonical communication database models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.communications.enums import (
    AnnouncementAudienceType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementStatus,
    CommunicationActorType,
    ConversationType,
    NotificationSourceType,
    NotificationStatus,
    enum_values,
)
from app.shared.base_model import Base, PUBLIC_SCHEMA
from app.shared.mixins import TimestampMixin, UUIDMixin


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_conversations"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    conversation_type: Mapped[ConversationType] = mapped_column(
        SQLEnum(
            ConversationType,
            name="communication_conversation_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=ConversationType.DIRECT,
        server_default=ConversationType.DIRECT.value,
    )
    created_by_actor_type: Mapped[CommunicationActorType] = mapped_column(
        SQLEnum(
            CommunicationActorType,
            name="communication_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    participants: Mapped[list["ConversationParticipant"]] = relationship(
        "ConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class ConversationParticipant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_conversation_participants"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    actor_type: Mapped[CommunicationActorType] = mapped_column(
        SQLEnum(
            CommunicationActorType,
            name="communication_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="participants")

    __table_args__ = (
        Index(
            "uq_comm_participant_active",
            "conversation_id",
            "actor_type",
            "actor_id",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
        ),
        Index("ix_comm_participants_actor", "tenant_id", "actor_type", "actor_id"),
    )


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    sender_actor_type: Mapped[CommunicationActorType] = mapped_column(
        SQLEnum(
            CommunicationActorType,
            name="communication_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    sender_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


class Announcement(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_announcements"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    created_by_actor_type: Mapped[CommunicationActorType] = mapped_column(
        SQLEnum(
            CommunicationActorType,
            name="communication_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    created_by_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[AnnouncementCategory] = mapped_column(
        SQLEnum(
            AnnouncementCategory,
            name="communication_announcement_category",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AnnouncementCategory.GENERAL,
        server_default=AnnouncementCategory.GENERAL.value,
    )
    priority: Mapped[AnnouncementPriority] = mapped_column(
        SQLEnum(
            AnnouncementPriority,
            name="communication_announcement_priority",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AnnouncementPriority.NORMAL,
        server_default=AnnouncementPriority.NORMAL.value,
    )
    status: Mapped[AnnouncementStatus] = mapped_column(
        SQLEnum(
            AnnouncementStatus,
            name="communication_announcement_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=AnnouncementStatus.DRAFT,
        server_default=AnnouncementStatus.DRAFT.value,
    )
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audiences: Mapped[list["AnnouncementAudience"]] = relationship(
        "AnnouncementAudience",
        back_populates="announcement",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_comm_announcements_tenant_status", "tenant_id", "status", "publish_at"),
    )


class AnnouncementAudience(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_announcement_audiences"

    announcement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("communication_announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    audience_type: Mapped[AnnouncementAudienceType] = mapped_column(
        SQLEnum(
            AnnouncementAudienceType,
            name="communication_audience_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    tenant_target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("classes.id"), nullable=True, index=True
    )

    announcement: Mapped[Announcement] = relationship("Announcement", back_populates="audiences")

    __table_args__ = (
        UniqueConstraint(
            "announcement_id",
            "audience_type",
            "tenant_target_id",
            "actor_id",
            "class_id",
            name="uq_comm_announcement_audience",
        ),
    )


class NotificationDelivery(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "communication_notification_deliveries"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True
    )
    recipient_actor_type: Mapped[CommunicationActorType] = mapped_column(
        SQLEnum(
            CommunicationActorType,
            name="communication_actor_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    recipient_actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    source_type: Mapped[NotificationSourceType] = mapped_column(
        SQLEnum(
            NotificationSourceType,
            name="communication_notification_source_type",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    preview: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    action_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(
            NotificationStatus,
            name="communication_notification_status",
            schema=PUBLIC_SCHEMA,
            values_callable=enum_values,
        ),
        nullable=False,
        default=NotificationStatus.UNREAD,
        server_default=NotificationStatus.UNREAD.value,
    )
    delivered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "recipient_actor_type",
            "recipient_actor_id",
            "source_type",
            "source_id",
            name="uq_comm_notification_delivery_source",
        ),
        Index(
            "ix_comm_notifications_inbox",
            "tenant_id",
            "recipient_actor_type",
            "recipient_actor_id",
            "status",
            "delivered_at",
        ),
    )
