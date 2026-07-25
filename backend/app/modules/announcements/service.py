import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.settings import settings
from app.core.cache.events import flush_cache_invalidation_events
from app.core.cache.manager import CacheManager
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.announcements.cache import (
    announcement_detail_cache_key,
    announcement_feed_cache_key,
    announcement_manageable_cache_key,
    invalidate_announcement_actor_cache,
    invalidate_announcement_tenant_cache,
)
from app.modules.announcements.models import (
    Announcement,
    AnnouncementActorType,
    AnnouncementCategory,
    AnnouncementPriority,
    AnnouncementRead,
    AnnouncementReadStatus,
    AnnouncementRecipientRole,
    AnnouncementStatus,
    AnnouncementTarget,
    AnnouncementTargetType,
)
from app.modules.announcements.repository import (
    AnnouncementReadRepository,
    AnnouncementRepository,
)
from app.modules.announcements.schemas import (
    AnnouncementCreate,
    AnnouncementFeedItemResponse,
    AnnouncementFeedResponse,
    AnnouncementListResponse,
    AnnouncementResponse,
    AnnouncementTargetCreate,
    AnnouncementUpdate,
)
from app.modules.metrics.cache import (
    invalidate_parent_dashboard_cache,
    invalidate_student_dashboard_cache,
    invalidate_teacher_dashboard_cache,
    invalidate_tenant_admin_dashboard_cache,
)
from app.modules.classes.models import ClassRoom
from app.modules.parents.models import Parent
from app.modules.students.models import Student, StudentParentLink
from app.modules.superadmin.models import SuperAdmin
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.tenant_management.models import Tenant


class AnnouncementService:
    """Business rules for creating, managing, and resolving announcements."""

    TENANT_ADMIN_TARGETS = {
        AnnouncementTargetType.ALL,
        AnnouncementTargetType.ROLE,
        AnnouncementTargetType.CLASS,
        AnnouncementTargetType.SPECIFIC_PARENT,
        AnnouncementTargetType.SPECIFIC_STUDENT,
        AnnouncementTargetType.SPECIFIC_TEACHER,
        AnnouncementTargetType.PARENTS_OF_STUDENT,
        AnnouncementTargetType.PARENTS_OF_CLASS,
    }
    TEACHER_TARGETS = {
        AnnouncementTargetType.CLASS,
        AnnouncementTargetType.SPECIFIC_STUDENT,
        AnnouncementTargetType.PARENTS_OF_STUDENT,
        AnnouncementTargetType.PARENTS_OF_CLASS,
    }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _coerce_target_type(value: AnnouncementTargetType | str) -> AnnouncementTargetType:
        return value if isinstance(value, AnnouncementTargetType) else AnnouncementTargetType(value)

    @staticmethod
    def _coerce_role(value: AnnouncementRecipientRole | str | None) -> AnnouncementRecipientRole | None:
        if value is None:
            return None
        return value if isinstance(value, AnnouncementRecipientRole) else AnnouncementRecipientRole(value)

    @staticmethod
    def _coerce_category(value: AnnouncementCategory | str) -> AnnouncementCategory:
        return value if isinstance(value, AnnouncementCategory) else AnnouncementCategory(value)

    @staticmethod
    def _coerce_priority(value: AnnouncementPriority | str) -> AnnouncementPriority:
        return value if isinstance(value, AnnouncementPriority) else AnnouncementPriority(value)

    @staticmethod
    def _actor_type(actor: SuperAdmin | TenantAdmin | Teacher) -> AnnouncementActorType:
        if isinstance(actor, SuperAdmin):
            return AnnouncementActorType.SUPERADMIN
        if isinstance(actor, TenantAdmin):
            return AnnouncementActorType.TENANT_ADMIN
        if isinstance(actor, Teacher):
            return AnnouncementActorType.TEACHER
        raise ForbiddenException("Unsupported announcement creator")

    @staticmethod
    def _recipient_type(actor: TenantAdmin | Teacher | Parent | Student) -> AnnouncementRecipientRole | None:
        if isinstance(actor, TenantAdmin):
            return AnnouncementRecipientRole.TENANT_ADMIN
        if isinstance(actor, Teacher):
            return AnnouncementRecipientRole.TEACHER
        if isinstance(actor, Parent):
            return AnnouncementRecipientRole.PARENT
        if isinstance(actor, Student):
            return AnnouncementRecipientRole.STUDENT
        return None

    @staticmethod
    def _actor_cache_type(actor: SuperAdmin | TenantAdmin | Teacher | Parent | Student) -> str:
        if isinstance(actor, SuperAdmin):
            return AnnouncementActorType.SUPERADMIN.value
        if isinstance(actor, TenantAdmin):
            return AnnouncementActorType.TENANT_ADMIN.value
        if isinstance(actor, Teacher):
            return AnnouncementActorType.TEACHER.value
        if isinstance(actor, Parent):
            return AnnouncementRecipientRole.PARENT.value
        if isinstance(actor, Student):
            return AnnouncementRecipientRole.STUDENT.value
        raise ForbiddenException("Unsupported announcement actor")

    @staticmethod
    def _manageable_cache_scope(actor: SuperAdmin | TenantAdmin | Teacher) -> uuid.UUID | str:
        return "global" if isinstance(actor, SuperAdmin) else actor.tenant_id

    @staticmethod
    async def _invalidate_dashboard_for_creator(
        db: AsyncSession,
        announcement: Announcement,
    ) -> None:
        await invalidate_tenant_admin_dashboard_cache(announcement.tenant_id, db=db)
        if announcement.created_by_actor_type == AnnouncementActorType.TEACHER:
            await invalidate_teacher_dashboard_cache(
                announcement.tenant_id,
                announcement.created_by_actor_id,
                db=db,
            )

    @staticmethod
    async def _invalidate_after_announcement_write(
        db: AsyncSession,
        announcement: Announcement,
    ) -> None:
        await invalidate_announcement_tenant_cache(announcement.tenant_id, db=db)
        if announcement.created_by_actor_type == AnnouncementActorType.SUPERADMIN:
            await invalidate_announcement_tenant_cache("global", db=db)
        await AnnouncementService._invalidate_dashboard_for_creator(db, announcement)

    @staticmethod
    async def _invalidate_after_read(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Parent | Student,
    ) -> None:
        actor_type = AnnouncementService._actor_cache_type(actor)
        await invalidate_announcement_actor_cache(
            actor.tenant_id,
            actor_type,
            actor.id,
            db=db,
        )
        if isinstance(actor, Parent):
            await invalidate_parent_dashboard_cache(actor.tenant_id, actor.id, db=db)
        elif isinstance(actor, Student):
            await invalidate_student_dashboard_cache(actor.tenant_id, actor.id, db=db)

    @staticmethod
    def _validate_target_shape(target: AnnouncementTargetCreate) -> None:
        target_type = AnnouncementService._coerce_target_type(target.target_type)
        role = AnnouncementService._coerce_role(target.role)
        values = {
            "role": role,
            "class_id": target.class_id,
            "student_id": target.student_id,
            "parent_membership_id": target.parent_membership_id,
            "teacher_membership_id": target.teacher_membership_id,
        }
        expected = {
            AnnouncementTargetType.ALL: set(),
            AnnouncementTargetType.ROLE: {"role"},
            AnnouncementTargetType.CLASS: {"class_id"},
            AnnouncementTargetType.SPECIFIC_PARENT: {"parent_membership_id"},
            AnnouncementTargetType.SPECIFIC_STUDENT: {"student_id"},
            AnnouncementTargetType.SPECIFIC_TEACHER: {"teacher_membership_id"},
            AnnouncementTargetType.PARENTS_OF_STUDENT: {"student_id"},
            AnnouncementTargetType.PARENTS_OF_CLASS: {"class_id"},
        }[target_type]
        provided = {key for key, value in values.items() if value is not None}
        if provided != expected:
            raise BadRequestException(f"Invalid target fields for {target_type.value}")

    @staticmethod
    async def _ensure_targets_exist(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        targets: list[AnnouncementTargetCreate],
    ) -> None:
        class_ids = {target.class_id for target in targets if target.class_id}
        student_ids = {target.student_id for target in targets if target.student_id}
        parent_ids = {
            target.parent_membership_id
            for target in targets
            if target.parent_membership_id
        }
        teacher_ids = {
            target.teacher_membership_id
            for target in targets
            if target.teacher_membership_id
        }

        checks = [
            (ClassRoom, class_ids, "class"),
            (Student, student_ids, "student"),
            (Parent, parent_ids, "parent"),
            (Teacher, teacher_ids, "teacher"),
        ]
        for model, ids, label in checks:
            if not ids:
                continue
            count = (
                await db.execute(
                    select(func.count()).select_from(model).where(
                        model.tenant_id == tenant_id,
                        model.id.in_(ids),
                    )
                )
            ).scalar_one()
            if count != len(ids):
                raise BadRequestException(f"One or more target {label}s do not exist in this tenant")

    @staticmethod
    async def _ensure_teacher_scope(
        db: AsyncSession,
        teacher: Teacher,
        targets: list[AnnouncementTargetCreate],
    ) -> None:
        class_ids = {target.class_id for target in targets if target.class_id}
        student_ids = {target.student_id for target in targets if target.student_id}

        if class_ids:
            count = (
                await db.execute(
                    select(func.count()).select_from(ClassRoom).where(
                        ClassRoom.tenant_id == teacher.tenant_id,
                        ClassRoom.id.in_(class_ids),
                        ClassRoom.teacher_membership_id == teacher.id,
                    )
                )
            ).scalar_one()
            if count != len(class_ids):
                raise ForbiddenException("Teachers may only target classes assigned to them")

        if student_ids:
            count = (
                await db.execute(
                    select(func.count()).select_from(Student).join(
                        ClassRoom,
                        and_(
                            ClassRoom.id == Student.class_id,
                            ClassRoom.tenant_id == Student.tenant_id,
                        ),
                    ).where(
                        Student.tenant_id == teacher.tenant_id,
                        Student.id.in_(student_ids),
                        ClassRoom.teacher_membership_id == teacher.id,
                    )
                )
            ).scalar_one()
            if count != len(student_ids):
                raise ForbiddenException("Teachers may only target students in their classes")

    @staticmethod
    async def _validate_targets(
        db: AsyncSession,
        actor: SuperAdmin | TenantAdmin | Teacher,
        tenant_id: uuid.UUID,
        targets: list[AnnouncementTargetCreate],
    ) -> None:
        if not targets:
            raise BadRequestException("At least one target is required")

        for target in targets:
            AnnouncementService._validate_target_shape(target)
            if AnnouncementService._coerce_role(target.role) == AnnouncementRecipientRole.TENANT_ADMIN:
                raise ForbiddenException("School announcements cannot target tenant admins")

        if isinstance(actor, SuperAdmin):
            raise ForbiddenException("Superadmin announcements are created through platform helpers only")

        allowed = (
            AnnouncementService.TEACHER_TARGETS
            if isinstance(actor, Teacher)
            else AnnouncementService.TENANT_ADMIN_TARGETS
        )
        target_types = {AnnouncementService._coerce_target_type(target.target_type) for target in targets}
        if not target_types.issubset(allowed):
            raise ForbiddenException("This actor cannot use one or more announcement targets")

        await AnnouncementService._ensure_targets_exist(db, tenant_id, targets)
        if isinstance(actor, Teacher):
            await AnnouncementService._ensure_teacher_scope(db, actor, targets)

    @staticmethod
    def _build_targets(
        tenant_id: uuid.UUID,
        announcement_id: uuid.UUID,
        targets: list[AnnouncementTargetCreate],
    ) -> list[AnnouncementTarget]:
        return [
            AnnouncementTarget(
                tenant_id=tenant_id,
                announcement_id=announcement_id,
                target_type=AnnouncementService._coerce_target_type(target.target_type),
                role=AnnouncementService._coerce_role(target.role),
                class_id=target.class_id,
                student_id=target.student_id,
                parent_membership_id=target.parent_membership_id,
                teacher_membership_id=target.teacher_membership_id,
            )
            for target in targets
        ]

    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher,
        payload: AnnouncementCreate,
    ) -> Announcement:
        tenant_id = actor.tenant_id
        await AnnouncementService._validate_targets(db, actor, tenant_id, payload.targets)
        announcement = Announcement(
            tenant_id=tenant_id,
            title=payload.title,
            body=payload.body,
            category=AnnouncementService._coerce_category(payload.category),
            priority=AnnouncementService._coerce_priority(payload.priority),
            status=AnnouncementStatus.DRAFT,
            created_by_actor_type=AnnouncementService._actor_type(actor),
            created_by_actor_id=actor.id,
            publish_at=payload.publish_at,
            expires_at=payload.expires_at,
            is_pinned=payload.is_pinned,
        )
        await AnnouncementRepository.create_announcement(db, announcement)
        targets = AnnouncementService._build_targets(
            tenant_id,
            announcement.id,
            payload.targets,
        )
        db.add_all(targets)
        await db.flush()
        await db.refresh(announcement, ["targets"])
        await AnnouncementService._invalidate_after_announcement_write(db, announcement)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return announcement

    @staticmethod
    async def create_platform(
        db: AsyncSession,
        *,
        actor: SuperAdmin,
        payload: AnnouncementCreate,
    ) -> list[Announcement]:
        for target in payload.targets:
            AnnouncementService._validate_target_shape(target)
        if any(AnnouncementService._coerce_target_type(target.target_type) != AnnouncementTargetType.ALL for target in payload.targets):
            raise ForbiddenException("Superadmin announcements are only delivered to tenant admins")

        tenants = (
            await db.execute(select(Tenant).where(Tenant.is_deleted.is_(False)))
        ).scalars().all()
        announcements: list[Announcement] = []
        for tenant in tenants:
            announcement = Announcement(
                tenant_id=tenant.id,
                title=payload.title,
                body=payload.body,
                category=AnnouncementService._coerce_category(payload.category),
                priority=AnnouncementService._coerce_priority(payload.priority),
                status=AnnouncementStatus.DRAFT,
                created_by_actor_type=AnnouncementActorType.SUPERADMIN,
                created_by_actor_id=actor.id,
                publish_at=payload.publish_at,
                expires_at=payload.expires_at,
                is_pinned=payload.is_pinned,
            )
            await AnnouncementRepository.create_announcement(db, announcement)
            targets = [
                AnnouncementTarget(
                    tenant_id=tenant.id,
                    announcement_id=announcement.id,
                    target_type=AnnouncementTargetType.ALL,
                )
            ]
            db.add_all(targets)
            await db.flush()
            await db.refresh(announcement, ["targets"])
            announcements.append(announcement)
            await AnnouncementService._invalidate_after_announcement_write(db, announcement)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return announcements

    @staticmethod
    async def _get_manageable(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
        tenant_id: uuid.UUID | None = None,
    ) -> Announcement:
        if isinstance(actor, SuperAdmin):
            stmt = (
                select(Announcement)
                .options(selectinload(Announcement.targets))
                .where(
                    Announcement.id == announcement_id,
                    Announcement.created_by_actor_type == AnnouncementActorType.SUPERADMIN,
                )
            )
        else:
            stmt = (
                select(Announcement)
                .options(selectinload(Announcement.targets))
                .where(
                    Announcement.id == announcement_id,
                    Announcement.tenant_id == actor.tenant_id,
                )
            )
            if isinstance(actor, Teacher):
                stmt = stmt.where(
                    Announcement.created_by_actor_type == AnnouncementActorType.TEACHER,
                    Announcement.created_by_actor_id == actor.id,
                )
        result = await db.execute(stmt)
        announcement = result.scalar_one_or_none()
        if announcement is None:
            raise NotFoundException("Announcement not found")
        if tenant_id is not None and announcement.tenant_id != tenant_id:
            raise NotFoundException("Announcement not found")
        return announcement

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
        payload: AnnouncementUpdate,
    ) -> Announcement:
        announcement = await AnnouncementService._get_manageable(
            db,
            actor=actor,
            announcement_id=announcement_id,
        )
        update_data = payload.model_dump(exclude_unset=True, exclude_none=True)
        targets = update_data.pop("targets", None)
        if "category" in update_data and update_data["category"] is not None:
            update_data["category"] = AnnouncementService._coerce_category(update_data["category"])
        if "priority" in update_data and update_data["priority"] is not None:
            update_data["priority"] = AnnouncementService._coerce_priority(update_data["priority"])
        for field, value in update_data.items():
            setattr(announcement, field, value)
        if targets is not None:
            for target in targets:
                AnnouncementService._validate_target_shape(target)
            if isinstance(actor, SuperAdmin):
                if any(AnnouncementService._coerce_target_type(target.target_type) != AnnouncementTargetType.ALL for target in targets):
                    raise ForbiddenException("Superadmin announcements are only delivered to tenant admins")
            else:
                await AnnouncementService._validate_targets(db, actor, announcement.tenant_id, targets)
            await AnnouncementRepository.replace_targets(
                db,
                announcement.tenant_id,
                announcement.id,
                AnnouncementService._build_targets(announcement.tenant_id, announcement.id, targets),
            )
        saved = await AnnouncementRepository.save(db, announcement)
        await AnnouncementService._invalidate_after_announcement_write(db, saved)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return saved

    @staticmethod
    async def publish(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
        publish_at: datetime | None = None,
    ) -> Announcement:
        announcement = await AnnouncementService._get_manageable(db, actor=actor, announcement_id=announcement_id)
        announcement.status = AnnouncementStatus.PUBLISHED
        announcement.publish_at = publish_at or announcement.publish_at or AnnouncementService._now()
        saved = await AnnouncementRepository.save(db, announcement)
        await AnnouncementService._invalidate_after_announcement_write(db, saved)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return saved

    @staticmethod
    async def archive(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
    ) -> Announcement:
        announcement = await AnnouncementService._get_manageable(db, actor=actor, announcement_id=announcement_id)
        announcement.status = AnnouncementStatus.ARCHIVED
        saved = await AnnouncementRepository.save(db, announcement)
        await AnnouncementService._invalidate_after_announcement_write(db, saved)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return saved

    @staticmethod
    async def delete(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
    ) -> None:
        announcement = await AnnouncementService._get_manageable(db, actor=actor, announcement_id=announcement_id)
        tenant_id = announcement.tenant_id
        await AnnouncementRepository.delete_announcement(db, announcement)
        await invalidate_announcement_tenant_cache(tenant_id, db=db)
        if announcement.created_by_actor_type == AnnouncementActorType.SUPERADMIN:
            await invalidate_announcement_tenant_cache("global", db=db)
        await invalidate_tenant_admin_dashboard_cache(tenant_id, db=db)
        await db.commit()
        await flush_cache_invalidation_events(db)

    @staticmethod
    async def list_manageable(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        status: AnnouncementStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Announcement], int]:
        filters = []
        if isinstance(actor, SuperAdmin):
            filters.append(Announcement.created_by_actor_type == AnnouncementActorType.SUPERADMIN)
        else:
            filters.append(Announcement.tenant_id == actor.tenant_id)
            if isinstance(actor, Teacher):
                filters.extend(
                    [
                        Announcement.created_by_actor_type == AnnouncementActorType.TEACHER,
                        Announcement.created_by_actor_id == actor.id,
                    ]
                )
        if status is not None:
            filters.append(Announcement.status == status)

        total = (
            await db.execute(select(func.count()).select_from(Announcement).where(*filters))
        ).scalar_one()
        items = (
            await db.execute(
                select(Announcement)
                .options(selectinload(Announcement.targets))
                .where(*filters)
                .order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        ).scalars().unique().all()
        return list(items), int(total)

    @staticmethod
    async def list_manageable_response(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        status: AnnouncementStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AnnouncementListResponse:
        params = {
            "status": status.value if hasattr(status, "value") else status,
            "limit": limit,
            "offset": offset,
        }
        key = announcement_manageable_cache_key(
            AnnouncementService._manageable_cache_scope(actor),
            AnnouncementService._actor_cache_type(actor),
            actor.id,
            params,
        )

        async def fetch_list() -> AnnouncementListResponse:
            items, total = await AnnouncementService.list_manageable(
                db,
                actor=actor,
                status=status,
                limit=limit,
                offset=offset,
            )
            return AnnouncementListResponse(
                items=[AnnouncementResponse.model_validate(item) for item in items],
                total=total,
            )

        cached = await CacheManager.get_or_set(
            key=key,
            fetcher=fetch_list,
            ttl=settings.CACHE_SHORT_TTL_SECONDS,
        )
        return AnnouncementListResponse.model_validate(cached)

    @staticmethod
    async def get_details(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
    ) -> Announcement:
        return await AnnouncementService._get_manageable(db, actor=actor, announcement_id=announcement_id)

    @staticmethod
    async def get_details_response(
        db: AsyncSession,
        *,
        actor: SuperAdmin | TenantAdmin | Teacher,
        announcement_id: uuid.UUID,
    ) -> AnnouncementResponse:
        cached_scope = AnnouncementService._manageable_cache_scope(actor)
        key = announcement_detail_cache_key(
            cached_scope,
            AnnouncementService._actor_cache_type(actor),
            actor.id,
            announcement_id,
        )

        async def fetch_detail() -> AnnouncementResponse:
            announcement = await AnnouncementService.get_details(
                db,
                actor=actor,
                announcement_id=announcement_id,
            )
            return AnnouncementResponse.model_validate(announcement)

        cached = await CacheManager.get_or_set(
            key=key,
            fetcher=fetch_detail,
            ttl=settings.CACHE_SHORT_TTL_SECONDS,
        )
        return AnnouncementResponse.model_validate(cached)

    @staticmethod
    async def _parent_student_ids(db: AsyncSession, parent: Parent) -> list[uuid.UUID]:
        rows = (
            await db.execute(
                select(StudentParentLink.student_id).where(
                    StudentParentLink.tenant_id == parent.tenant_id,
                    StudentParentLink.parent_membership_id == parent.id,
                )
            )
        ).scalars().all()
        return list(rows)

    @staticmethod
    def _base_feed_filters(tenant_id: uuid.UUID) -> list:
        now = AnnouncementService._now()
        return [
            Announcement.tenant_id == tenant_id,
            Announcement.status == AnnouncementStatus.PUBLISHED,
            or_(Announcement.publish_at.is_(None), Announcement.publish_at <= now),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        ]

    @staticmethod
    async def feed(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Parent | Student,
        delivery_kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> AnnouncementFeedResponse:
        params = {
            "delivery_kind": delivery_kind,
            "limit": limit,
            "offset": offset,
        }
        key = announcement_feed_cache_key(
            actor.tenant_id,
            AnnouncementService._actor_cache_type(actor),
            actor.id,
            params,
        )

        async def fetch_feed() -> AnnouncementFeedResponse:
            base, tenant_id, recipient_type = await AnnouncementService._feed_base_query(
                db,
                actor,
                delivery_kind=delivery_kind,
            )
            total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
            announcements = (
                await db.execute(
                    base.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).scalars().unique().all()

            read_by_id = {}
            if announcements:
                reads = (
                    await db.execute(
                        select(AnnouncementRead).where(
                            AnnouncementRead.tenant_id == tenant_id,
                            AnnouncementRead.actor_type == recipient_type,
                            AnnouncementRead.actor_id == actor.id,
                            AnnouncementRead.announcement_id.in_([item.id for item in announcements]),
                        )
                    )
                ).scalars().all()
                read_by_id = {read.announcement_id: read for read in reads}

            items = []
            unread_count = 0
            for announcement in announcements:
                read = read_by_id.get(announcement.id)
                is_read = read is not None and read.status in {
                    AnnouncementReadStatus.READ,
                    AnnouncementReadStatus.ACKNOWLEDGED,
                }
                is_acknowledged = read is not None and read.status == AnnouncementReadStatus.ACKNOWLEDGED
                if not is_read:
                    unread_count += 1
                items.append(
                    AnnouncementFeedItemResponse(
                        **{
                            "id": announcement.id,
                            "title": announcement.title,
                            "body": announcement.body,
                            "category": announcement.category,
                            "priority": announcement.priority,
                            "status": announcement.status,
                            "publish_at": announcement.publish_at,
                            "expires_at": announcement.expires_at,
                            "is_pinned": announcement.is_pinned,
                            "is_read": is_read,
                            "is_acknowledged": is_acknowledged,
                            "read_at": read.read_at if read else None,
                            "acknowledged_at": read.acknowledged_at if read else None,
                            "created_at": announcement.created_at,
                            "updated_at": announcement.updated_at,
                        }
                    )
                )
            return AnnouncementFeedResponse(items=items, total=int(total), unread_count=unread_count)

        cached = await CacheManager.get_or_set(
            key=key,
            fetcher=fetch_feed,
            ttl=settings.CACHE_SHORT_TTL_SECONDS,
        )
        return AnnouncementFeedResponse.model_validate(cached)

    @staticmethod
    async def _feed_base_query(
        db: AsyncSession,
        actor: TenantAdmin | Teacher | Parent | Student,
        delivery_kind: str | None = None,
    ):
        tenant_id = actor.tenant_id
        filters = AnnouncementService._base_feed_filters(tenant_id)
        recipient_type = AnnouncementService._recipient_type(actor)

        if isinstance(actor, TenantAdmin):
            filters.append(Announcement.created_by_actor_type == AnnouncementActorType.SUPERADMIN)
        else:
            notice_filters = [
                AnnouncementTarget.target_type == AnnouncementTargetType.ALL,
                and_(
                    AnnouncementTarget.target_type == AnnouncementTargetType.ROLE,
                    AnnouncementTarget.role == recipient_type,
                ),
            ]
            direct_filters = []

            if isinstance(actor, Teacher):
                direct_filters = []
            elif isinstance(actor, Student):
                notice_filters.append(
                    and_(
                        AnnouncementTarget.target_type == AnnouncementTargetType.CLASS,
                        AnnouncementTarget.class_id == actor.class_id,
                    )
                )
                direct_filters.append(
                    and_(
                        AnnouncementTarget.target_type == AnnouncementTargetType.SPECIFIC_STUDENT,
                        AnnouncementTarget.student_id == actor.id,
                    )
                )
            elif isinstance(actor, Parent):
                direct_filters.append(
                    and_(
                        AnnouncementTarget.target_type == AnnouncementTargetType.SPECIFIC_PARENT,
                        AnnouncementTarget.parent_membership_id == actor.id,
                    )
                )
                student_ids = await AnnouncementService._parent_student_ids(db, actor)
                if student_ids:
                    class_ids = (
                        await db.execute(
                            select(Student.class_id).where(
                                Student.tenant_id == tenant_id,
                                Student.id.in_(student_ids),
                                Student.class_id.is_not(None),
                            )
                        )
                    ).scalars().all()
                    notice_filters.extend(
                        [
                            and_(
                                AnnouncementTarget.target_type == AnnouncementTargetType.PARENTS_OF_STUDENT,
                                AnnouncementTarget.student_id.in_(student_ids),
                            ),
                            and_(
                                AnnouncementTarget.target_type == AnnouncementTargetType.PARENTS_OF_CLASS,
                                AnnouncementTarget.class_id.in_(class_ids),
                            ),
                        ]
                    )

            if delivery_kind == "message":
                target_filters = direct_filters
            elif delivery_kind == "notice":
                target_filters = notice_filters
            else:
                target_filters = notice_filters + direct_filters

            if delivery_kind == "message" and not target_filters:
                filters.append(false())
            elif not target_filters:
                target_filters = notice_filters

            filters.append(Announcement.created_by_actor_type != AnnouncementActorType.SUPERADMIN)
            if target_filters:
                filters.append(or_(*target_filters))

        base = (
            select(Announcement)
            .join(AnnouncementTarget, AnnouncementTarget.announcement_id == Announcement.id)
            .options(selectinload(Announcement.reads), selectinload(Announcement.targets))
            .where(*filters)
            .distinct()
        )
        return base, tenant_id, recipient_type

    @staticmethod
    async def feed_summary(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Parent | Student,
    ) -> tuple[int, int, dict[str, int]]:
        base, tenant_id, recipient_type = await AnnouncementService._feed_base_query(db, actor)
        rows = (await db.execute(base.with_only_columns(Announcement.id, Announcement.category))).all()
        announcement_ids = [row.id for row in rows]
        category_counts: dict[str, int] = {}
        for row in rows:
            label = row.category.value if hasattr(row.category, "value") else str(row.category)
            category_counts[label] = category_counts.get(label, 0) + 1

        read_count = 0
        if announcement_ids:
            read_count = (
                await db.execute(
                    select(func.count()).select_from(AnnouncementRead).where(
                        AnnouncementRead.tenant_id == tenant_id,
                        AnnouncementRead.actor_type == recipient_type,
                        AnnouncementRead.actor_id == actor.id,
                        AnnouncementRead.announcement_id.in_(announcement_ids),
                        AnnouncementRead.status.in_([AnnouncementReadStatus.READ, AnnouncementReadStatus.ACKNOWLEDGED]),
                    )
                )
            ).scalar_one()

        return len(announcement_ids), int(read_count), category_counts

    @staticmethod
    async def mark_read(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Parent | Student,
        announcement_id: uuid.UUID,
        status: AnnouncementReadStatus,
    ) -> AnnouncementRead:
        feed = await AnnouncementService.feed(db, actor=actor, limit=100, offset=0)
        if announcement_id not in {item.id for item in feed.items}:
            raise NotFoundException("Announcement not found")
        actor_type = AnnouncementService._recipient_type(actor)
        read = await AnnouncementReadRepository.upsert_read_state(
            db,
            tenant_id=actor.tenant_id,
            announcement_id=announcement_id,
            actor_type=actor_type,
            actor_id=actor.id,
            status=status,
        )
        await AnnouncementService._invalidate_after_read(db, actor)
        await db.commit()
        await flush_cache_invalidation_events(db)
        return read
