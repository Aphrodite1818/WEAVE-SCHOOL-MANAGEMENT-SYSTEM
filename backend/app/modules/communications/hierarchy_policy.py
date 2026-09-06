"""Hierarchy-aware direct-message authorization.

The communication graph is derived from current academic placement and current
role assignments. Historical conversations remain readable after the graph
changes, but only currently authorized pairs may continue writing to them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException
from app.modules.classes.models import ClassRoom
from app.modules.communications.enums import CommunicationActorType
from app.modules.communications.recipient_resolver import (
    RecipientResolver,
    ResolvedRecipient,
    _dedupe,
    _label_with_identifier,
    _name,
)
from app.modules.communications.schemas import RecipientTarget
from app.modules.parents.models import Parent
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
)
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin


class HierarchyMessagingPolicy:
    """Resolve the current direct-message graph for one actor."""

    @staticmethod
    async def available_recipients(db: AsyncSession, sender) -> list[ResolvedRecipient]:
        if isinstance(sender, SuperAdmin):
            return await RecipientResolver._tenant_admins(db, group="School administrators")

        if isinstance(sender, TenantAdmin):
            recipients: list[ResolvedRecipient] = []
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db,
                    tenant_id=sender.tenant_id,
                    group="School administrators",
                )
            )
            recipients = [
                item
                for item in recipients
                if not (
                    item.actor_type == CommunicationActorType.TENANT_ADMIN
                    and item.actor_id == sender.id
                )
            ]
            recipients.extend(
                await RecipientResolver._teachers(
                    db,
                    sender.tenant_id,
                    group="Teachers",
                )
            )
            recipients.extend(
                await RecipientResolver._students(
                    db,
                    sender.tenant_id,
                    group="Students",
                )
            )
            recipients.extend(
                await RecipientResolver._parents(
                    db,
                    sender.tenant_id,
                    group="Parents",
                )
            )
            recipients.extend(
                await RecipientResolver._superadmins(
                    db,
                    group="WEAVE administration",
                )
            )
            return _dedupe(recipients)

        if isinstance(sender, Teacher):
            recipients = []
            recipients.extend(
                await RecipientResolver._teachers(
                    db,
                    sender.tenant_id,
                    group="Teachers",
                    exclude_id=sender.id,
                )
            )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db,
                    tenant_id=sender.tenant_id,
                    group="School administrators",
                )
            )

            # Subject assignment alone never grants a student/parent DM channel.
            # Only current class-teacher ownership does.
            class_ids = await HierarchyMessagingPolicy._class_teacher_class_ids(db, sender)
            if class_ids:
                recipients.extend(
                    await HierarchyMessagingPolicy._students_in_classes(
                        db,
                        tenant_id=sender.tenant_id,
                        class_ids=class_ids,
                        group="My class students",
                    )
                )
                for class_id in class_ids:
                    recipients.extend(
                        await RecipientResolver._parents_for_class(
                            db,
                            sender.tenant_id,
                            class_id,
                        )
                    )
            return _dedupe(recipients)

        if isinstance(sender, Student):
            recipients = []
            if sender.class_id is not None:
                recipients.extend(
                    await RecipientResolver._class_teacher(
                        db,
                        sender.tenant_id,
                        sender.class_id,
                        group="My class teacher",
                    )
                )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db,
                    tenant_id=sender.tenant_id,
                    group="School administrators",
                )
            )
            return _dedupe(recipients)

        if isinstance(sender, Parent):
            recipients = []
            for class_id in await RecipientResolver._parent_child_class_ids(db, sender):
                recipients.extend(
                    await RecipientResolver._class_teacher(
                        db,
                        sender.tenant_id,
                        class_id,
                        group="My child's class teacher",
                    )
                )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db,
                    tenant_id=sender.tenant_id,
                    group="School administrators",
                )
            )
            return _dedupe(recipients)

        raise ForbiddenException("Unsupported communication actor")

    @staticmethod
    async def resolve_target(
        db: AsyncSession,
        sender,
        target: RecipientTarget,
    ) -> ResolvedRecipient:
        actor_type = (
            target.actor_type
            if isinstance(target.actor_type, CommunicationActorType)
            else CommunicationActorType(target.actor_type)
        )
        for recipient in await HierarchyMessagingPolicy.available_recipients(db, sender):
            if recipient.actor_type == actor_type and recipient.actor_id == target.actor_id:
                return recipient
        raise ForbiddenException("You cannot message this recipient")

    @staticmethod
    async def can_continue_conversation(db: AsyncSession, sender, conversation) -> bool:
        sender_type = RecipientResolverActorType.for_actor(sender)
        counterpart = next(
            (
                participant
                for participant in conversation.participants
                if participant.left_at is None
                and not (
                    participant.actor_type == sender_type
                    and participant.actor_id == sender.id
                )
            ),
            None,
        )
        if counterpart is None:
            return False
        available = await HierarchyMessagingPolicy.available_recipients(db, sender)
        return any(
            item.actor_type == counterpart.actor_type and item.actor_id == counterpart.actor_id
            for item in available
        )

    @staticmethod
    async def ensure_can_continue_conversation(db: AsyncSession, sender, conversation) -> None:
        if not await HierarchyMessagingPolicy.can_continue_conversation(db, sender, conversation):
            raise ForbiddenException(
                "This conversation is read-only because the current school relationship no longer permits direct messaging"
            )

    @staticmethod
    async def _class_teacher_class_ids(db: AsyncSession, teacher: Teacher) -> set[uuid.UUID]:
        rows = (
            (
                await db.execute(
                    select(ClassRoom.id).where(
                        ClassRoom.tenant_id == teacher.tenant_id,
                        ClassRoom.teacher_membership_id == teacher.id,
                        ClassRoom.is_active.is_(True),
                        ClassRoom.archived_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        return set(rows)

    @staticmethod
    async def _students_in_classes(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID,
        class_ids: set[uuid.UUID],
        group: str,
    ) -> list[ResolvedRecipient]:
        if not class_ids:
            return []
        rows = (
            (
                await db.execute(
                    select(Student).where(
                        Student.tenant_id == tenant_id,
                        Student.class_id.in_(class_ids),
                        Student.is_active.is_(True),
                        Student.is_verified.is_(True),
                        Student.is_archived.is_(False),
                        Student.account_status == StudentAccountStatus.ACTIVE,
                        Student.status == AcademicStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        return [
            ResolvedRecipient(
                actor_type=CommunicationActorType.STUDENT,
                actor_id=row.id,
                tenant_id=tenant_id,
                label=_label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.admission_number),
                    row.admission_number,
                ),
                group_label=group,
            )
            for row in rows
        ]


class RecipientResolverActorType:
    """Tiny adapter kept local to avoid duplicating actor-type dispatch."""

    @staticmethod
    def for_actor(actor) -> CommunicationActorType:
        from app.modules.communications.recipient_resolver import actor_type_for

        return actor_type_for(actor)
