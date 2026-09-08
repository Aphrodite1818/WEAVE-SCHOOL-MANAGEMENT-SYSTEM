"""Hierarchy-aware recipient resolution for messages and notices."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException
from app.modules.classes.models import ClassRoom
from app.modules.communications.enums import CommunicationActorType, NoticeAudienceType
from app.modules.communications.schemas import ActorIdentity, NoticeAudienceCreate
from app.modules.parents.models import (
    Parent,
    ParentAccount,
    ParentAccountStatus,
    ParentMembershipStatus,
)
from app.modules.student_academics.curriculum_models import CurriculumSubject
from app.modules.student_academics.models import TeacherAssignment
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
    result: list[ResolvedRecipient] = []
    for recipient in recipients:
        key = (recipient.actor_type, recipient.actor_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(recipient)
    return result


class RecipientResolver:
    @staticmethod
    async def _superadmins(db: AsyncSession, *, group: str) -> list[ResolvedRecipient]:
        rows = (
            (await db.execute(select(SuperAdmin).where(SuperAdmin.is_active.is_(True))))
            .scalars()
            .all()
        )
        return [
            ResolvedRecipient(CommunicationActorType.SUPERADMIN, row.id, None, row.email, group)
            for row in rows
        ]

    @staticmethod
    async def _tenant_admins(
        db: AsyncSession,
        *,
        tenant_id: uuid.UUID | None = None,
        group: str = "School administrators",
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
        if exclude_id is not None:
            stmt = stmt.where(Teacher.id != exclude_id)
        rows = (await db.execute(stmt)).all()
        return [
            ResolvedRecipient(
                CommunicationActorType.TEACHER,
                row.id,
                tenant_id,
                _label_with_identifier(
                    _name(row.first_name, row.last_name, fallback=row.email), row.staff_id
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
                        [ParentMembershipStatus.ACTIVE, ParentMembershipStatus.READ_ONLY]
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
                    _name(row.first_name, row.last_name, fallback=row.email), row.email
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
                    ClassRoom.is_active.is_(True),
                    ClassRoom.archived_at.is_(None),
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
                    _name(row.first_name, row.last_name, fallback=row.email), row.staff_id
                ),
                group,
            )
        ]

    @staticmethod
    async def _parent_child_class_ids(db: AsyncSession, parent: Parent) -> set[uuid.UUID]:
        rows = (
            (
                await db.execute(
                    select(Student.class_id)
                    .join(StudentParentLink, StudentParentLink.student_id == Student.id)
                    .where(
                        StudentParentLink.tenant_id == parent.tenant_id,
                        StudentParentLink.parent_membership_id == parent.id,
                        StudentParentLink.status.in_(
                            [StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY]
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
        return {row for row in rows if row is not None}

    @staticmethod
    async def _students_for_class(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        class_id: uuid.UUID,
        *,
        group: str,
    ) -> list[ResolvedRecipient]:
        rows = (
            (
                await db.execute(
                    select(Student).where(
                        Student.tenant_id == tenant_id,
                        Student.class_id == class_id,
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
                .join(StudentParentLink, StudentParentLink.parent_membership_id == Parent.id)
                .join(Student, Student.id == StudentParentLink.student_id)
                .join(ParentAccount, ParentAccount.id == Parent.parent_account_id)
                .where(
                    Parent.tenant_id == tenant_id,
                    Student.tenant_id == tenant_id,
                    Student.class_id == class_id,
                    Student.status == AcademicStatus.ACTIVE,
                    Student.is_archived.is_(False),
                    StudentParentLink.status.in_(
                        [StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY]
                    ),
                    Parent.status.in_(
                        [ParentMembershipStatus.ACTIVE, ParentMembershipStatus.READ_ONLY]
                    ),
                    ParentAccount.is_active.is_(True),
                    ParentAccount.is_verified.is_(True),
                    ParentAccount.account_status == ParentAccountStatus.ACTIVE,
                )
            )
        ).all()
        return _dedupe(
            [
                ResolvedRecipient(
                    CommunicationActorType.PARENT,
                    row.id,
                    tenant_id,
                    _label_with_identifier(
                        _name(row.first_name, row.last_name, fallback=row.email), row.email
                    ),
                    "Parents of class",
                )
                for row in rows
            ]
        )

    @staticmethod
    async def _students_without_parents_count(
        db: AsyncSession, tenant_id: uuid.UUID, class_id: uuid.UUID
    ) -> int:
        linked_student_ids = select(StudentParentLink.student_id).where(
            StudentParentLink.tenant_id == tenant_id,
            StudentParentLink.status.in_(
                [StudentParentLinkStatus.ACTIVE, StudentParentLinkStatus.READ_ONLY]
            ),
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
                        Student.id.not_in(linked_student_ids),
                    )
                )
            ).scalar_one()
        )

    @staticmethod
    async def _teacher_class_teacher_ids(db: AsyncSession, teacher: Teacher) -> set[uuid.UUID]:
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
    async def _teacher_subject_class_ids(db: AsyncSession, teacher: Teacher) -> set[uuid.UUID]:
        rows = (
            (
                await db.execute(
                    select(TeacherAssignment.class_id)
                    .join(
                        CurriculumSubject,
                        CurriculumSubject.id == TeacherAssignment.curriculum_subject_id,
                    )
                    .join(ClassRoom, ClassRoom.id == TeacherAssignment.class_id)
                    .where(
                        TeacherAssignment.tenant_id == teacher.tenant_id,
                        TeacherAssignment.teacher_membership_id == teacher.id,
                        TeacherAssignment.is_active.is_(True),
                        CurriculumSubject.is_active.is_(True),
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
    def _audience_type(value: NoticeAudienceType | str) -> NoticeAudienceType:
        return value if isinstance(value, NoticeAudienceType) else NoticeAudienceType(value)

    @staticmethod
    async def resolve_notice_audience(
        db: AsyncSession,
        *,
        sender,
        audiences: list[NoticeAudienceCreate],
    ) -> tuple[list[ResolvedRecipient], list[str]]:
        recipients: list[ResolvedRecipient] = []
        excluded: list[str] = []

        if isinstance(sender, SuperAdmin):
            for audience in audiences:
                audience_type = RecipientResolver._audience_type(audience.audience_type)
                if audience_type == NoticeAudienceType.ALL_TENANT_ADMINS:
                    recipients.extend(await RecipientResolver._tenant_admins(db))
                elif audience_type == NoticeAudienceType.SELECTED_TENANT_ADMINS:
                    if audience.actor_id is None:
                        raise BadRequestException("Choose a tenant admin")
                    recipients.extend(
                        row
                        for row in await RecipientResolver._tenant_admins(db)
                        if row.actor_id == audience.actor_id
                    )
                elif audience_type == NoticeAudienceType.TENANT_ADMINS_OF_TENANTS:
                    if audience.tenant_target_id is None:
                        raise BadRequestException("Choose a tenant")
                    recipients.extend(
                        await RecipientResolver._tenant_admins(
                            db, tenant_id=audience.tenant_target_id
                        )
                    )
                else:
                    raise ForbiddenException("WEAVE notices can target tenant admins only")

        elif isinstance(sender, TenantAdmin):
            for audience in audiences:
                audience_type = RecipientResolver._audience_type(audience.audience_type)
                if audience_type == NoticeAudienceType.ALL_TEACHERS:
                    recipients.extend(
                        await RecipientResolver._teachers(db, sender.tenant_id, group="Teachers")
                    )
                elif audience_type == NoticeAudienceType.SELECTED_TEACHERS:
                    if audience.actor_id is None:
                        raise BadRequestException("Choose a teacher")
                    recipients.extend(
                        row
                        for row in await RecipientResolver._teachers(
                            db, sender.tenant_id, group="Selected teachers"
                        )
                        if row.actor_id == audience.actor_id
                    )
                elif audience_type == NoticeAudienceType.ALL_STUDENTS:
                    recipients.extend(
                        await RecipientResolver._students(db, sender.tenant_id, group="Students")
                    )
                elif audience_type == NoticeAudienceType.SELECTED_STUDENTS:
                    if audience.actor_id is None:
                        raise BadRequestException("Choose a student")
                    recipients.extend(
                        row
                        for row in await RecipientResolver._students(
                            db, sender.tenant_id, group="Selected students"
                        )
                        if row.actor_id == audience.actor_id
                    )
                elif audience_type == NoticeAudienceType.ALL_PARENTS:
                    recipients.extend(
                        await RecipientResolver._parents(db, sender.tenant_id, group="Parents")
                    )
                elif audience_type == NoticeAudienceType.SELECTED_PARENTS:
                    if audience.actor_id is None:
                        raise BadRequestException("Choose a parent")
                    recipients.extend(
                        row
                        for row in await RecipientResolver._parents(
                            db, sender.tenant_id, group="Selected parents"
                        )
                        if row.actor_id == audience.actor_id
                    )
                elif audience_type == NoticeAudienceType.CLASS_STUDENTS:
                    if audience.class_id is None:
                        raise BadRequestException("Choose a class")
                    recipients.extend(
                        await RecipientResolver._students_for_class(
                            db,
                            sender.tenant_id,
                            audience.class_id,
                            group="Students in class",
                        )
                    )
                elif audience_type == NoticeAudienceType.CLASS_PARENTS:
                    if audience.class_id is None:
                        raise BadRequestException("Choose a class")
                    recipients.extend(
                        await RecipientResolver._parents_for_class(
                            db, sender.tenant_id, audience.class_id
                        )
                    )
                    missing = await RecipientResolver._students_without_parents_count(
                        db, sender.tenant_id, audience.class_id
                    )
                    if missing:
                        excluded.append(f"{missing} student(s) without a linked parent")
                else:
                    raise ForbiddenException(
                        "School administrators cannot use this notice audience"
                    )

        elif isinstance(sender, Teacher):
            class_teacher_ids = await RecipientResolver._teacher_class_teacher_ids(db, sender)
            subject_class_ids = await RecipientResolver._teacher_subject_class_ids(db, sender)
            for audience in audiences:
                audience_type = RecipientResolver._audience_type(audience.audience_type)
                if audience.class_id is None:
                    raise BadRequestException("Choose a class for a teacher notice")
                if audience_type == NoticeAudienceType.CLASS_STUDENTS:
                    if audience.class_id not in class_teacher_ids | subject_class_ids:
                        raise ForbiddenException("You are not currently assigned to this class")
                    recipients.extend(
                        await RecipientResolver._students_for_class(
                            db,
                            sender.tenant_id,
                            audience.class_id,
                            group="Students in assigned class",
                        )
                    )
                elif audience_type == NoticeAudienceType.CLASS_PARENTS:
                    if audience.class_id not in class_teacher_ids:
                        raise ForbiddenException(
                            "Only the current class teacher can send notices to class parents"
                        )
                    recipients.extend(
                        await RecipientResolver._parents_for_class(
                            db, sender.tenant_id, audience.class_id
                        )
                    )
                    missing = await RecipientResolver._students_without_parents_count(
                        db, sender.tenant_id, audience.class_id
                    )
                    if missing:
                        excluded.append(f"{missing} student(s) without a linked parent")
                else:
                    raise ForbiddenException(
                        "Teachers can send notices only to students in assigned classes or parents of their class-teacher class"
                    )
        else:
            raise ForbiddenException("This actor cannot create notices")

        recipients = _dedupe(recipients)
        if not recipients:
            raise BadRequestException("No active recipients match this notice audience")
        return recipients, excluded
