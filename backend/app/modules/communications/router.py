"""Communication, message, announcement, and notification routes."""

from __future__ import annotations

import uuid
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.core.dependencies.db import DbSession
from app.core.dependencies.route_guards import (
    CurrentActor,
    get_current_actor,
    get_current_parent,
    get_current_student,
    get_current_superadmin,
    get_current_teacher,
    get_current_tenant_admin,
    get_current_tenant_member,
)
from app.core.exceptions import ForbiddenException
from app.modules.communications.announcement_service import AnnouncementService
from app.modules.communications.enums import AnnouncementStatus, CommunicationActorType, NotificationStatus
from app.modules.communications.messaging_service import MessagingService
from app.modules.communications.notification_service import NotificationService
from app.modules.communications.recipient_resolver import actor_type_for
from app.modules.communications.schemas import (
    AnnouncementCreate,
    AnnouncementListResponse,
    AnnouncementPublishRequest,
    AnnouncementResponse,
    AnnouncementUpdate,
    AvailableRecipientGroup,
    AvailableRecipientsResponse,
    ConversationCreate,
    ConversationListResponse,
    ConversationParticipantResponse,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    NotificationListResponse,
    NotificationResponse,
    RecipientPreviewResponse,
    UnreadCountResponse,
)
from app.modules.parents.models import Parent
from app.modules.parents.models import ParentAccount
from app.modules.students.models import Student
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.teachers.models import TeacherAccount
from app.modules.tenant_admins.models import TenantAdmin


router = APIRouter(prefix="/communications", tags=["Communications"])
messages_router = APIRouter(prefix="/messages", tags=["Messages"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])
superadmin_announcement_router = APIRouter(prefix="/superadmin/announcements", tags=["Superadmin Announcements"])
tenant_admin_announcement_router = APIRouter(prefix="/tenant-admin/announcements", tags=["Tenant Admin Announcements"])

CurrentCommunicationActor: TypeAlias = Annotated[CurrentActor, Depends(get_current_actor)]
CurrentTenantMember = Annotated[TenantAdmin | Teacher | Parent | Student, Depends(get_current_tenant_member)]
CurrentSuperadmin = Annotated[SuperAdmin, Depends(get_current_superadmin)]
CurrentTenantAdmin = Annotated[TenantAdmin, Depends(get_current_tenant_admin)]


async def _active_communication_actor(actor: CurrentCommunicationActor, db: DbSession):
    if isinstance(actor, SuperAdmin):
        return await get_current_superadmin(actor)
    if isinstance(actor, TenantAdmin):
        return await get_current_tenant_admin(actor, db)
    if isinstance(actor, Teacher):
        return await get_current_teacher(actor, db)
    if isinstance(actor, Parent):
        return await get_current_parent(actor, db)
    if isinstance(actor, Student):
        return await get_current_student(actor, db)
    raise ForbiddenException("A tenant membership or superadmin session is required")


def _name(*parts: str | None, fallback: str = "Unknown") -> str:
    value = " ".join(part for part in parts if part).strip()
    return value or fallback


def _label_with_identifier(name: str, identifier: str | None) -> str:
    return f"{name} - {identifier}" if identifier else name


async def _participant_labels(db: DbSession, participants) -> dict[tuple[CommunicationActorType, uuid.UUID], str]:
    ids_by_type: dict[CommunicationActorType, set[uuid.UUID]] = {}
    for participant in participants:
        actor_type = participant.actor_type if isinstance(participant.actor_type, CommunicationActorType) else CommunicationActorType(participant.actor_type)
        ids_by_type.setdefault(actor_type, set()).add(participant.actor_id)

    labels: dict[tuple[CommunicationActorType, uuid.UUID], str] = {}

    student_ids = ids_by_type.get(CommunicationActorType.STUDENT, set())
    if student_ids:
        rows = (await db.execute(select(Student).where(Student.id.in_(student_ids)))).scalars().all()
        for row in rows:
            labels[(CommunicationActorType.STUDENT, row.id)] = _label_with_identifier(
                _name(row.first_name, row.last_name, fallback=row.admission_number),
                row.admission_number,
            )

    teacher_ids = ids_by_type.get(CommunicationActorType.TEACHER, set())
    if teacher_ids:
        rows = (
            await db.execute(
                select(
                    Teacher.id,
                    Teacher.staff_id,
                    TeacherAccount.first_name,
                    TeacherAccount.last_name,
                    TeacherAccount.email,
                )
                .join(TeacherAccount, Teacher.teacher_account_id == TeacherAccount.id)
                .where(Teacher.id.in_(teacher_ids))
            )
        ).all()
        for row in rows:
            labels[(CommunicationActorType.TEACHER, row.id)] = _label_with_identifier(
                _name(row.first_name, row.last_name, fallback=row.email),
                row.staff_id,
            )

    parent_ids = ids_by_type.get(CommunicationActorType.PARENT, set())
    if parent_ids:
        rows = (
            await db.execute(
                select(
                    Parent.id,
                    ParentAccount.first_name,
                    ParentAccount.last_name,
                    ParentAccount.email,
                )
                .join(ParentAccount, Parent.parent_account_id == ParentAccount.id)
                .where(Parent.id.in_(parent_ids))
            )
        ).all()
        for row in rows:
            labels[(CommunicationActorType.PARENT, row.id)] = _label_with_identifier(
                _name(row.first_name, row.last_name, fallback=row.email),
                row.email,
            )

    tenant_admin_ids = ids_by_type.get(CommunicationActorType.TENANT_ADMIN, set())
    if tenant_admin_ids:
        rows = (await db.execute(select(TenantAdmin).where(TenantAdmin.id.in_(tenant_admin_ids)))).scalars().all()
        for row in rows:
            labels[(CommunicationActorType.TENANT_ADMIN, row.id)] = row.email

    superadmin_ids = ids_by_type.get(CommunicationActorType.SUPERADMIN, set())
    if superadmin_ids:
        rows = (await db.execute(select(SuperAdmin).where(SuperAdmin.id.in_(superadmin_ids)))).scalars().all()
        for row in rows:
            labels[(CommunicationActorType.SUPERADMIN, row.id)] = row.email

    return labels


async def _conversation_response(db: DbSession, conversation) -> ConversationResponse:
    labels = await _participant_labels(db, conversation.participants)
    response = ConversationResponse.model_validate(conversation)
    response.participants = [
        ConversationParticipantResponse.model_validate(participant).model_copy(
            update={
                "label": labels.get((
                    participant.actor_type if isinstance(participant.actor_type, CommunicationActorType) else CommunicationActorType(participant.actor_type),
                    participant.actor_id,
                )),
                "group_label": str(
                    participant.actor_type.value if hasattr(participant.actor_type, "value") else participant.actor_type
                ).replace("_", " "),
            },
        )
        for participant in conversation.participants
    ]
    return response


def _announcement_list(items, total: int) -> AnnouncementListResponse:
    return AnnouncementListResponse(items=[AnnouncementResponse.model_validate(item) for item in items], total=total)


@router.get("/available-recipients", response_model=AvailableRecipientsResponse)
async def available_recipients(db: DbSession, actor: CurrentCommunicationActor) -> AvailableRecipientsResponse:
    current = await _active_communication_actor(actor, db)
    recipients = await MessagingService.available_recipients(db, actor=current)
    groups: dict[str, list] = {}
    for recipient in recipients:
        groups.setdefault(recipient.group_label or "Recipients", []).append(recipient.as_schema())
    return AvailableRecipientsResponse(
        groups=[AvailableRecipientGroup(label=label, recipients=items) for label, items in groups.items()]
    )


@messages_router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    db: DbSession,
    actor: CurrentCommunicationActor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> ConversationListResponse:
    current = await _active_communication_actor(actor, db)
    items, total = await MessagingService.list_conversations(db, actor=current, offset=skip, limit=limit)
    unread_count = 0
    return ConversationListResponse(items=[await _conversation_response(db, item) for item in items], total=total, unread_count=unread_count)


@messages_router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: ConversationCreate, db: DbSession, actor: CurrentCommunicationActor) -> ConversationResponse:
    current = await _active_communication_actor(actor, db)
    conversation = await MessagingService.create_conversation(db, actor=current, payload=payload)
    return await _conversation_response(db, conversation)


@messages_router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> ConversationResponse:
    current = await _active_communication_actor(actor, db)
    conversation = await MessagingService.get_conversation(db, actor=current, conversation_id=conversation_id)
    return await _conversation_response(db, conversation)


@messages_router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(conversation_id: uuid.UUID, payload: MessageCreate, db: DbSession, actor: CurrentCommunicationActor) -> MessageResponse:
    current = await _active_communication_actor(actor, db)
    message = await MessagingService.add_message(db, actor=current, conversation_id=conversation_id, body=payload.body)
    return MessageResponse.model_validate(message)


@messages_router.post("/conversations/{conversation_id}/read", response_model=ConversationResponse)
async def mark_conversation_read(conversation_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> ConversationResponse:
    current = await _active_communication_actor(actor, db)
    conversation = await MessagingService.mark_read(db, actor=current, conversation_id=conversation_id)
    return await _conversation_response(db, conversation)


@notifications_router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: DbSession,
    actor: CurrentCommunicationActor,
    status_filter: NotificationStatus | None = Query(default=None, alias="status"),
    source_type: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> NotificationListResponse:
    current = await _active_communication_actor(actor, db)
    items, total, unread = await NotificationService.list_for_actor(
        db,
        actor=current,
        status=status_filter,
        source_type=source_type,
        offset=skip,
        limit=limit,
    )
    return NotificationListResponse(items=[NotificationResponse.model_validate(item) for item in items], total=total, unread_count=unread)


@notifications_router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(db: DbSession, actor: CurrentCommunicationActor) -> UnreadCountResponse:
    current = await _active_communication_actor(actor, db)
    _, _, unread = await NotificationService.list_for_actor(db, actor=current, status=None, source_type=None, offset=0, limit=1)
    return UnreadCountResponse(unread_count=unread)


@notifications_router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> NotificationResponse:
    current = await _active_communication_actor(actor, db)
    delivery = await NotificationService.update_status(db, actor=current, notification_id=notification_id, status=NotificationStatus.READ)
    return NotificationResponse.model_validate(delivery)


@notifications_router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(notification_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> NotificationResponse:
    current = await _active_communication_actor(actor, db)
    delivery = await NotificationService.update_status(db, actor=current, notification_id=notification_id, status=NotificationStatus.READ)
    return NotificationResponse.model_validate(delivery)


@notifications_router.post("/{notification_id}/acknowledge", response_model=NotificationResponse)
async def acknowledge_notification(notification_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> NotificationResponse:
    current = await _active_communication_actor(actor, db)
    delivery = await NotificationService.update_status(db, actor=current, notification_id=notification_id, status=NotificationStatus.ACKNOWLEDGED)
    return NotificationResponse.model_validate(delivery)


@notifications_router.delete("/{notification_id}", response_model=NotificationResponse)
async def dismiss_notification(notification_id: uuid.UUID, db: DbSession, actor: CurrentCommunicationActor) -> NotificationResponse:
    current = await _active_communication_actor(actor, db)
    delivery = await NotificationService.update_status(db, actor=current, notification_id=notification_id, status=NotificationStatus.DISMISSED)
    return NotificationResponse.model_validate(delivery)


@superadmin_announcement_router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_superadmin_announcement(payload: AnnouncementCreate, db: DbSession, actor: CurrentSuperadmin) -> AnnouncementResponse:
    announcement = await AnnouncementService.create(db, actor=actor, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@superadmin_announcement_router.get("", response_model=AnnouncementListResponse)
async def list_superadmin_announcements(
    db: DbSession,
    actor: CurrentSuperadmin,
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementListResponse:
    items, total = await AnnouncementService.list_manageable(db, actor=actor, status=status_filter, offset=skip, limit=limit)
    return _announcement_list(items, total)


@superadmin_announcement_router.post("/preview", response_model=RecipientPreviewResponse)
async def preview_superadmin_announcement(payload: AnnouncementCreate, db: DbSession, actor: CurrentSuperadmin) -> RecipientPreviewResponse:
    label, recipients, excluded = await AnnouncementService.preview(db, actor=actor, audiences=payload.audiences)
    return RecipientPreviewResponse(audience_label=label, recipient_count=len(recipients), excluded_reasons=excluded, recipients=[item.as_schema() for item in recipients[:50]])


@superadmin_announcement_router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_superadmin_announcement(announcement_id: uuid.UUID, payload: AnnouncementUpdate, db: DbSession, actor: CurrentSuperadmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.update(db, actor=actor, announcement_id=announcement_id, payload=payload))


@superadmin_announcement_router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_superadmin_announcement(announcement_id: uuid.UUID, payload: AnnouncementPublishRequest, db: DbSession, actor: CurrentSuperadmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.publish(db, actor=actor, announcement_id=announcement_id, publish_at=payload.publish_at))


@superadmin_announcement_router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_superadmin_announcement(announcement_id: uuid.UUID, db: DbSession, actor: CurrentSuperadmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.archive(db, actor=actor, announcement_id=announcement_id))


@superadmin_announcement_router.post("/{announcement_id}/cancel", response_model=AnnouncementResponse)
async def cancel_superadmin_announcement(announcement_id: uuid.UUID, db: DbSession, actor: CurrentSuperadmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.cancel(db, actor=actor, announcement_id=announcement_id))


@tenant_admin_announcement_router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_admin_announcement(payload: AnnouncementCreate, db: DbSession, actor: CurrentTenantAdmin) -> AnnouncementResponse:
    announcement = await AnnouncementService.create(db, actor=actor, payload=payload)
    return AnnouncementResponse.model_validate(announcement)


@tenant_admin_announcement_router.get("", response_model=AnnouncementListResponse)
async def list_tenant_admin_announcements(
    db: DbSession,
    actor: CurrentTenantAdmin,
    status_filter: AnnouncementStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AnnouncementListResponse:
    items, total = await AnnouncementService.list_manageable(db, actor=actor, status=status_filter, offset=skip, limit=limit)
    return _announcement_list(items, total)


@tenant_admin_announcement_router.post("/preview", response_model=RecipientPreviewResponse)
async def preview_tenant_admin_announcement(payload: AnnouncementCreate, db: DbSession, actor: CurrentTenantAdmin) -> RecipientPreviewResponse:
    label, recipients, excluded = await AnnouncementService.preview(db, actor=actor, audiences=payload.audiences)
    return RecipientPreviewResponse(audience_label=label, recipient_count=len(recipients), excluded_reasons=excluded, recipients=[item.as_schema() for item in recipients[:50]])


@tenant_admin_announcement_router.patch("/{announcement_id}", response_model=AnnouncementResponse)
async def update_tenant_admin_announcement(announcement_id: uuid.UUID, payload: AnnouncementUpdate, db: DbSession, actor: CurrentTenantAdmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.update(db, actor=actor, announcement_id=announcement_id, payload=payload))


@tenant_admin_announcement_router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_tenant_admin_announcement(announcement_id: uuid.UUID, payload: AnnouncementPublishRequest, db: DbSession, actor: CurrentTenantAdmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.publish(db, actor=actor, announcement_id=announcement_id, publish_at=payload.publish_at))


@tenant_admin_announcement_router.post("/{announcement_id}/archive", response_model=AnnouncementResponse)
async def archive_tenant_admin_announcement(announcement_id: uuid.UUID, db: DbSession, actor: CurrentTenantAdmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.archive(db, actor=actor, announcement_id=announcement_id))


@tenant_admin_announcement_router.post("/{announcement_id}/cancel", response_model=AnnouncementResponse)
async def cancel_tenant_admin_announcement(announcement_id: uuid.UUID, db: DbSession, actor: CurrentTenantAdmin) -> AnnouncementResponse:
    return AnnouncementResponse.model_validate(await AnnouncementService.cancel(db, actor=actor, announcement_id=announcement_id))
