"""Centralized communication recipient authorization."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.classes.models import ClassRoom
from app.modules.communications.enums import (
    AnnouncementAudienceType,
    CommunicationActorType,
)
from app.modules.communications.schemas import (
    ActorIdentity,
    AnnouncementAudienceCreate,
    RecipientTarget,
)
from app.modules.parents.models import (
    Parent,
    ParentAccount,
    ParentAccountStatus,
    ParentMembershipStatus,
)
from app.modules.student_academics.models import ClassSubject, TeacherAssignment
from app.modules.students.models import (
    AcademicStatus,
    Student,
    StudentAccountStatus,
    StudentParentLink,
    StudentParentLinkStatus,
)
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import (
    Teacher,
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembershipStatus,
)
from app.modules.tenant_admins.models import TenantAdmin, TenantAdminStatus


@dataclass(frozen=True)
class ResolvedRecipient:
    actor_type: CommunicationActorType
    actor_id: uuid.UUID
    tenant_id: uuid.UUID | None
    label: str
    group_label: str | None = None

    def as_schema(self) -> ActorIdentity:
        return ActorIdentity(
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            tenant_id=self.tenant_id,
            label=self.label,
            group_label=self.group_label,
        )


def actor_type_for(actor) -> CommunicationActorType:
    if isinstance(actor, SuperAdmin):
        return CommunicationActorType.SUPERADMIN
    if isinstance(actor, TenantAdmin):
        return CommunicationActorType.TENANT_ADMIN
    if isinstance(actor, Teacher):
        return CommunicationActorType.TEACHER
    if isinstance(actor, Parent):
        return CommunicationActorType.PARENT
    if isinstance(actor, Student):
        return CommunicationActorType.STUDENT
    raise ForbiddenException("Unsupported communication actor")


def actor_tenant_id(actor) -> uuid.UUID | None:
    return None if isinstance(actor, SuperAdmin) else actor.tenant_id


def _name(*parts: str | None, fallback: str = "Unknown") -> str:
    value = " ".join(part for part in parts if part).strip()
    return value or fallback


def _label_with_identifier(name: str, identifier: str | None) -> str:
    return f"{name} - {identifier}" if identifier else name


def _dedupe(recipients: list[ResolvedRecipient]) -> list[ResolvedRecipient]:
    seen: set[tuple[CommunicationActorType, uuid.UUID]] = set()
    deduped: list[ResolvedRecipient] = []
    for recipient in recipients:
        key = (recipient.actor_type, recipient.actor_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recipient)
    return deduped


class RecipientResolver:
    """Resolve available and submitted recipients using backend authority."""

    @staticmethod
    async def available_direct_recipients(
        db: AsyncSession, sender
    ) -> list[ResolvedRecipient]:
        if isinstance(sender, SuperAdmin):
            return await RecipientResolver._tenant_admins(db, group="Tenant admins")
        if isinstance(sender, TenantAdmin):
            tenant_id = sender.tenant_id
            recipients: list[ResolvedRecipient] = []
            recipients.extend(
                await RecipientResolver._teachers(db, tenant_id, group="Teachers")
            )
            recipients.extend(
                await RecipientResolver._students(db, tenant_id, group="Students")
            )
            recipients.extend(
                await RecipientResolver._parents(db, tenant_id, group="Parents")
            )
            recipients.extend(
                await RecipientResolver._superadmins(db, group="Platform support")
            )
            return _dedupe(recipients)
        if isinstance(sender, Teacher):
            tenant_id = sender.tenant_id
            recipients = []
            recipients.extend(
                await RecipientResolver._students_taught_by_teacher(
                    db, sender, group="Students I teach"
                )
            )
            recipients.extend(
                await RecipientResolver._parents_for_teacher_students(
                    db, sender, group="Parents of students I teach"
                )
            )
            recipients.extend(
                await RecipientResolver._teachers(
                    db, tenant_id, group="Teachers", exclude_id=sender.id
                )
            )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db, tenant_id=tenant_id, group="School administrators"
                )
            )
            return _dedupe(recipients)
        if isinstance(sender, Student):
            if sender.class_id is None:
                return await RecipientResolver._tenant_admins(
                    db, tenant_id=sender.tenant_id, group="School administration"
                )
            recipients = []
            recipients.extend(
                await RecipientResolver._class_teacher(
                    db, sender.tenant_id, sender.class_id, group="My class teacher"
                )
            )
            recipients.extend(
                await RecipientResolver._subject_teachers_for_class(
                    db, sender.tenant_id, sender.class_id, group="My subject teachers"
                )
            )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db, tenant_id=sender.tenant_id, group="School administration"
                )
            )
            return _dedupe(recipients)
        if isinstance(sender, Parent):
            recipients = []
            class_ids = await RecipientResolver._parent_child_class_ids(db, sender)
            for class_id in class_ids:
                recipients.extend(
                    await RecipientResolver._class_teacher(
                        db, sender.tenant_id, class_id, group="My child's class teacher"
                    )
                )
                recipients.extend(
                    await RecipientResolver._subject_teachers_for_class(
                        db,
                        sender.tenant_id,
                        class_id,
                        group="My child's subject teachers",
                    )
                )
            recipients.extend(
                await RecipientResolver._teachers(
                    db, sender.tenant_id, group="Other teachers"
                )
            )
            recipients.extend(
                await RecipientResolver._tenant_admins(
                    db, tenant_id=sender.tenant_id, group="School administration"
                )
            )
            return _dedupe(recipients)
        raise ForbiddenException("Unsupported communication actor")

    @staticmethod
    async def resolve_direct_target(
        db: AsyncSession, sender, target: RecipientTarget
    ) -> ResolvedRecipient:
        actor_type = (
            target.actor_type
            if isinstance(target.actor_type, CommunicationActorType)
            else CommunicationActorType(target.actor_type)
        )
        available = await RecipientResolver.available_direct_recipients(db, sender)
        for recipient in available:
            if (
                recipient.actor_type == actor_type
                and recipient.actor_id == target.actor_id
            ):
                return recipient
        raise ForbiddenException("You cannot message this recipient")

    @staticmethod
    async def resolve_announcement_audience(
        db: AsyncSession,
        *,
        sender,
        audiences: list[AnnouncementAudienceCreate],
    ) -> tuple[list[ResolvedRecipient], list[str]]:
        recipients: list[ResolvedRecipient] = []
        excluded: list[str] = []
        if isinstance(sender, SuperAdmin):
            allowed = {
                AnnouncementAudienceType.ALL_TENANT_ADMINS,
                AnnouncementAudienceType.SELECTED_TENANT_ADMINS,
                AnnouncementAudienceType.TENANT_ADMINS_OF_TENANTS,
            }
            for audience in audiences:
                audience_type = RecipientResolver._audience_type(audience.audience_type)
                if audience_type not in allowed:
                    raise ForbiddenException(
                        "Superadmin announcements can target tenant admins only"
                    )
                recipients.extend(
                    await RecipientResolver._resolve_superadmin_audience(db, audience)
                )
        elif isinstance(sender, TenantAdmin):
            allowed = {
                AnnouncementAudienceType.ALL_TEACHERS,
                AnnouncementAudienceType.SELECTED_TEACHERS,
                AnnouncementAudienceType.ALL_STUDENTS,
                AnnouncementAudienceType.SELECTED_STUDENTS,
                AnnouncementAudienceType.CLASS_STUDENTS,
                AnnouncementAudienceType.ALL_PARENTS,
                AnnouncementAudienceType.SELECTED_PARENTS,
                AnnouncementAudienceType.CLASS_PARENTS,
            }
            for audience in audiences:
                audience_type = RecipientResolver._audience_type(audience.audience_type)
                if audience_type not in allowed:
                    raise ForbiddenException(
                        "Tenant admins cannot use this announcement audience"
                    )
                (
                    resolved,
                    audience_excluded,
                ) = await RecipientResolver._resolve_tenant_admin_audience(
                    db, sender.tenant_id, audience
                )
                recipients.extend(resolved)
                excluded.extend(audience_excluded)
        else:
            raise ForbiddenException("This actor cannot create announcements")

        recipients = _dedupe(recipients)
        if not recipients:
            raise BadRequestException(
                "No active recipients match this audience. Choose a different audience before saving or publishing."
            )
        return recipients, excluded

    @staticmethod
    def _audience_type(
        value: AnnouncementAudienceType | str,
    ) -> AnnouncementAudienceType:
        return (
            value
            if isinstance(value, AnnouncementAudienceType)
            else AnnouncementAudienceType(value)
        )

    @staticmethod
    async def _superadmins(db: AsyncSession, *, group: str) -> list[ResolvedRecipient]:
        rows = (
            (await db.execute(select(SuperAdmin).where(SuperAdmin.is_active.is_(True))))
            .scalars()
            .all()
        )
        return [
            ResolvedRecipient(
                CommunicationActorType.SUPERADMIN, row.id, None, row.email, group
            )
            for row in rows
        ]

    @staticmethod
    async def _tenant_admins(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID | None = None,
        group: str = "Tenant admins",
    ) -> list[ResolvedRecipient]:
        stmt = select(TenantAdmin).where(
            TenantAdmin.is_active.is_(True),
            TenantAdmin.is_verified.is_(True),
            TenantAdmin.account_status == TenantAdminStatus.ACTIVE,
        )
        if tenant_id is not None:
            stmt = stmt.where(TenantAdmin.tenant_id == tenant_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [
            ResolvedRecipient(
                CommunicationActorType.TENANT_ADMIN,
                row.id,
                row.tenant_id,
                row.email,
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _teachers(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        group: str,
        exclude_id: uuid.UUID | None = None,
    ) -> list[ResolvedRecipient]:
        stmt = (
            select(
                Teacher.id,
                Teacher.staff_id,
                TeacherAccount.first_name,
                TeacherAccount.last_name,
                TeacherAccount.email,
            )
            .join(TeacherAccount, Teacher.teacher_account_id == TeacherAccount.id)
            .where(
                Teacher.tenant_id == tenant_id,
                Teacher.status == TeacherMembershipStatus.ACTIVE,
                TeacherAccount.is_active.is_(True),
                TeacherAccount.is_verified.is_(True),
                TeacherAccount.account_status == TeacherAccountStatus.ACTIVE,
            )
        )
        if exclude_id:
            stmt = stmt.where(Teacher.id != exclude_id)
        rows = (await db.execute(stmt)).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.TEACHER,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.staff_id,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _students(
        db: AsyncSession, tenant_id: uuid.UUID, *, group: str
    ) -> list[ResolvedRecipient]:
        rows = (
            (
                await db.execute(
                    select(Student).where(
                        Student.tenant_id == tenant_id,
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
                CommunicationActorType.STUDENT,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.admission_number),
                    row.admission_number,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _parents(
        db: AsyncSession, tenant_id: uuid.UUID, *, group: str
    ) -> list[ResolvedRecipient]:
        rows = (
            await db.execute(
                select(
                    Parent.id,
                    ParentAccount.first_name,
                    ParentAccount.last_name,
                    ParentAccount.email,
                )
                .join(ParentAccount, Parent.parent_account_id == ParentAccount.id)
                .where(
                    Parent.tenant_id == tenant_id,
                    Parent.status.in_(
                        [
                            ParentMembershipStatus.ACTIVE,
                            ParentMembershipStatus.READ_ONLY,
                        ]
                    ),
                    ParentAccount.is_active.is_(True),
                    ParentAccount.is_verified.is_(True),
                    ParentAccount.account_status == ParentAccountStatus.ACTIVE,
                )
            )
        ).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.PARENT,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.email,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _assigned_class_ids_for_teacher(
        db: AsyncSession, teacher: Teacher
    ) -> set[uuid.UUID]:
        homeroom = (
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
        subject_classes = (
            (
                await db.execute(
                    select(ClassSubject.class_id)
                    .join(
                        TeacherAssignment,
                        TeacherAssignment.class_subject_id == ClassSubject.id,
                    )
                    .where(
                        ClassSubject.tenant_id == teacher.tenant_id,
                        ClassSubject.is_active.is_(True),
                        ClassSubject.archived_at.is_(None),
                        TeacherAssignment.teacher_membership_id == teacher.id,
                        TeacherAssignment.is_active.is_(True),
                        TeacherAssignment.effective_to.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        return set(homeroom) | set(subject_classes)

    @staticmethod
    async def _students_taught_by_teacher(
        db: AsyncSession, teacher: Teacher, *, group: str
    ) -> list[ResolvedRecipient]:
        class_ids = await RecipientResolver._assigned_class_ids_for_teacher(db, teacher)
        if not class_ids:
            return []
        rows = (
            (
                await db.execute(
                    select(Student).where(
                        Student.tenant_id == teacher.tenant_id,
                        Student.class_id.in_(class_ids),
                        Student.is_active.is_(True),
                        Student.is_archived.is_(False),
                        Student.status == AcademicStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        return [
            ResolvedRecipient(
                CommunicationActorType.STUDENT,
                row.id,
                teacher.tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.admission_number),
                    row.admission_number,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _parents_for_teacher_students(
        db: AsyncSession, teacher: Teacher, *, group: str
    ) -> list[ResolvedRecipient]:
        class_ids = await RecipientResolver._assigned_class_ids_for_teacher(db, teacher)
        if not class_ids:
            return []
        rows = (
            await db.execute(
                select(
                    Parent.id,
                    ParentAccount.first_name,
                    ParentAccount.last_name,
                    ParentAccount.email,
                )
                .join(
                    StudentParentLink,
                    StudentParentLink.parent_membership_id == Parent.id,
                )
                .join(Student, Student.id == StudentParentLink.student_id)
                .join(ParentAccount, ParentAccount.id == Parent.parent_account_id)
                .where(
                    Parent.tenant_id == teacher.tenant_id,
                    Student.class_id.in_(class_ids),
                    StudentParentLink.status.in_(
                        [
                            StudentParentLinkStatus.ACTIVE,
                            StudentParentLinkStatus.READ_ONLY,
                        ]
                    ),
                    Parent.status.in_(
                        [
                            ParentMembershipStatus.ACTIVE,
                            ParentMembershipStatus.READ_ONLY,
                        ]
                    ),
                    ParentAccount.is_active.is_(True),
                    ParentAccount.is_verified.is_(True),
                    ParentAccount.account_status == ParentAccountStatus.ACTIVE,
                )
            )
        ).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.PARENT,
                row.id,
                teacher.tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.email,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _class_teacher(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, *, group: str
    ) -> list[ResolvedRecipient]:
        row = (
            await db.execute(
                select(
                    Teacher.id,
                    Teacher.staff_id,
                    TeacherAccount.first_name,
                    TeacherAccount.last_name,
                    TeacherAccount.email,
                )
                .join(ClassRoom, ClassRoom.teacher_membership_id == Teacher.id)
                .join(TeacherAccount, TeacherAccount.id == Teacher.teacher_account_id)
                .where(
                    ClassRoom.tenant_id == tenant_id,
                    ClassRoom.id == class_id,
                    Teacher.status == TeacherMembershipStatus.ACTIVE,
                    TeacherAccount.is_active.is_(True),
                    TeacherAccount.is_verified.is_(True),
                    TeacherAccount.account_status == TeacherAccountStatus.ACTIVE,
                )
            )
        ).one_or_none()
        if row is None:
            return []
        return [
            ResolvedRecipient(
                CommunicationActorType.TEACHER,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.staff_id,
                ),
                group,
            )
        ]

    @staticmethod
    async def _subject_teachers_for_class(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID, *, group: str
    ) -> list[ResolvedRecipient]:
        rows = (
            await db.execute(
                select(
                    Teacher.id,
                    Teacher.staff_id,
                    TeacherAccount.first_name,
                    TeacherAccount.last_name,
                    TeacherAccount.email,
                )
                .join(
                    TeacherAssignment,
                    TeacherAssignment.teacher_membership_id == Teacher.id,
                )
                .join(
                    ClassSubject, ClassSubject.id == TeacherAssignment.class_subject_id
                )
                .join(TeacherAccount, TeacherAccount.id == Teacher.teacher_account_id)
                .where(
                    ClassSubject.tenant_id == tenant_id,
                    ClassSubject.class_id == class_id,
                    ClassSubject.is_active.is_(True),
                    ClassSubject.archived_at.is_(None),
                    TeacherAssignment.is_active.is_(True),
                    TeacherAssignment.effective_to.is_(None),
                    Teacher.status == TeacherMembershipStatus.ACTIVE,
                    TeacherAccount.is_active.is_(True),
                    TeacherAccount.is_verified.is_(True),
                    TeacherAccount.account_status == TeacherAccountStatus.ACTIVE,
                )
            )
        ).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.TEACHER,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.staff_id,
                ),
                group,
            )
            for row in rows
        ]

    @staticmethod
    async def _parent_child_class_ids(
        db: AsyncSession, parent: Parent
    ) -> set[uuid.UUID]:
        rows = (
            (
                await db.execute(
                    select(Student.class_id)
                    .join(StudentParentLink, StudentParentLink.student_id == Student.id)
                    .where(
                        StudentParentLink.tenant_id == parent.tenant_id,
                        StudentParentLink.parent_membership_id == parent.id,
                        StudentParentLink.status.in_(
                            [
                                StudentParentLinkStatus.ACTIVE,
                                StudentParentLinkStatus.READ_ONLY,
                            ]
                        ),
                        Student.class_id.is_not(None),
                        Student.status == AcademicStatus.ACTIVE,
                        Student.is_archived.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        return {class_id for class_id in rows if class_id is not None}

    @staticmethod
    async def _resolve_superadmin_audience(
        db: AsyncSession, audience: AnnouncementAudienceCreate
    ) -> list[ResolvedRecipient]:
        audience_type = RecipientResolver._audience_type(audience.audience_type)
        if audience_type == AnnouncementAudienceType.ALL_TENANT_ADMINS:
            return await RecipientResolver._tenant_admins(db)
        if audience_type == AnnouncementAudienceType.SELECTED_TENANT_ADMINS:
            if audience.actor_id is None:
                raise BadRequestException("Choose a tenant admin")
            return [
                item
                for item in await RecipientResolver._tenant_admins(db)
                if item.actor_id == audience.actor_id
            ]
        if audience_type == AnnouncementAudienceType.TENANT_ADMINS_OF_TENANTS:
            if audience.tenant_target_id is None:
                raise BadRequestException("Choose a tenant")
            return await RecipientResolver._tenant_admins(
                db, tenant_id=audience.tenant_target_id
            )
        raise ForbiddenException("Unsupported platform audience")

    @staticmethod
    async def _resolve_tenant_admin_audience(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        audience: AnnouncementAudienceCreate,
    ) -> tuple[list[ResolvedRecipient], list[str]]:
        audience_type = RecipientResolver._audience_type(audience.audience_type)
        if audience_type == AnnouncementAudienceType.ALL_TEACHERS:
            return (
                await RecipientResolver._teachers(db, tenant_id, group="Teachers"),
                [],
            )
        if audience_type == AnnouncementAudienceType.SELECTED_TEACHERS:
            if audience.actor_id is None:
                raise BadRequestException("Choose a teacher")
            return [
                item
                for item in await RecipientResolver._teachers(
                    db, tenant_id, group="Selected teachers"
                )
                if item.actor_id == audience.actor_id
            ], []
        if audience_type == AnnouncementAudienceType.ALL_STUDENTS:
            return (
                await RecipientResolver._students(db, tenant_id, group="Students"),
                [],
            )
        if audience_type == AnnouncementAudienceType.SELECTED_STUDENTS:
            if audience.actor_id is None:
                raise BadRequestException("Choose a student")
            return [
                item
                for item in await RecipientResolver._students(
                    db, tenant_id, group="Selected students"
                )
                if item.actor_id == audience.actor_id
            ], []
        if audience_type == AnnouncementAudienceType.ALL_PARENTS:
            return await RecipientResolver._parents(db, tenant_id, group="Parents"), []
        if audience_type == AnnouncementAudienceType.SELECTED_PARENTS:
            if audience.actor_id is None:
                raise BadRequestException("Choose a parent")
            return [
                item
                for item in await RecipientResolver._parents(
                    db, tenant_id, group="Selected parents"
                )
                if item.actor_id == audience.actor_id
            ], []
        if audience_type == AnnouncementAudienceType.CLASS_STUDENTS:
            if audience.class_id is None:
                raise BadRequestException("Choose a class")
            rows = await RecipientResolver._students(
                db, tenant_id, group="Students in a class"
            )
            return [
                item
                for item in rows
                if await RecipientResolver._student_in_class(
                    db, item.actor_id, audience.class_id
                )
            ], []
        if audience_type == AnnouncementAudienceType.CLASS_PARENTS:
            if audience.class_id is None:
                raise BadRequestException("Choose a class")
            recipients = await RecipientResolver._parents_for_class(
                db, tenant_id, audience.class_id
            )
            missing = await RecipientResolver._students_without_parents_count(
                db, tenant_id, audience.class_id
            )
            excluded = (
                [f"{missing} student(s) without a linked parent"] if missing else []
            )
            return recipients, excluded
        raise ForbiddenException("Unsupported school audience")

    @staticmethod
    async def _student_in_class(
        db: AsyncSession, student_id: uuid.UUID, class_id: uuid.UUID
    ) -> bool:
        return bool(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Student)
                    .where(Student.id == student_id, Student.class_id == class_id)
                )
            ).scalar_one()
        )

    @staticmethod
    async def _parents_for_class(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> list[ResolvedRecipient]:
        rows = (
            await db.execute(
                select(
                    Parent.id,
                    ParentAccount.first_name,
                    ParentAccount.last_name,
                    ParentAccount.email,
                )
                .join(
                    StudentParentLink,
                    StudentParentLink.parent_membership_id == Parent.id,
                )
                .join(Student, Student.id == StudentParentLink.student_id)
                .join(ParentAccount, ParentAccount.id == Parent.parent_account_id)
                .where(
                    Parent.tenant_id == tenant_id,
                    Student.class_id == class_id,
                    StudentParentLink.status.in_(
                        [
                            StudentParentLinkStatus.ACTIVE,
                            StudentParentLinkStatus.READ_ONLY,
                        ]
                    ),
                    Parent.status.in_(
                        [
                            ParentMembershipStatus.ACTIVE,
                            ParentMembershipStatus.READ_ONLY,
                        ]
                    ),
                    ParentAccount.is_active.is_(True),
                    ParentAccount.is_verified.is_(True),
                    ParentAccount.account_status == ParentAccountStatus.ACTIVE,
                )
            )
        ).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.PARENT,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email),
                    row.email,
                ),
                "Parents of a class",
            )
            for row in rows
        ]

    @staticmethod
    async def _students_without_parents_count(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> int:
        active_parent_link = (
            select(StudentParentLink.student_id)
            .where(
                StudentParentLink.tenant_id == tenant_id,
                StudentParentLink.status.in_(
                    [StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY]
                ),
            )
            .subquery()
        )
        return int(
            (
                await db.execute(
                    select(func.count())
                    .select_from(Student)
                    .where(
                        Student.tenant_id == tenant_id,
                        Student.class_id == class_id,
                        Student.status == AcademicStatus.ACTIVE,
                        Student.is_archived.is_(False),
                        Student.id.not_in(select(active_parent_link.c.student_id)),
                    )
                )
            ).scalar_one()
        )
