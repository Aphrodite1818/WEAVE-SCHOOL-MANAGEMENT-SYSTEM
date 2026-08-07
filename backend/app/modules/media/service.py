# ========================== #
#      media/service.py      #
# ========================== #

"""Business logic for tenant-scoped media uploads."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.storage.factory import get_media_storage
from app.core.storage.keys import build_media_object_key
from app.modules.media.models import (
    MediaAsset,
    MediaOwnerType,
    MediaPurpose,
    MediaStatus,
    MediaStorageProvider,
    MediaUploadedByActorType,
    MediaVisibility,
)
from app.modules.media.repository import MediaAssetRepository
from app.modules.media.schemas import (
    MediaAssetFilter,
    MediaAssetListResponse,
    MediaCreateData,
    MediaDeleteResponse,
    MediaSignedUrlResponse,
    MediaUploadResponse,
)
from app.modules.media.validators import (
    MediaValidationError,
    get_cache_control_for_purpose,
    get_visibility_for_purpose,
    validate_school_logo_upload,
    validate_student_passport_upload,
    validate_teacher_passport_upload,
    validate_tenant_admin_passport_upload,
)
from app.modules.students.models import Student
from app.modules.students.repository import StudentRepository
from app.modules.teachers.models import Teacher
from app.modules.teachers.repository import TeacherRepository
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.tenant_admins.repository import TenantAdminRepository
from app.modules.tenant_branding.cache import invalidate_tenant_branding
from app.tenant_management.models import Tenant
from app.tenant_management.repository import TenantRepository


class MediaService:
    """Business logic for media uploads and media owner attachment."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> None:
        """Ensure the authenticated actor is a tenant admin."""

        if actor is None or actor.tenant_id is None:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant")

    @staticmethod
    def _get_uploader_type(
        actor: TenantAdmin | Teacher | Student,
    ) -> MediaUploadedByActorType:
        """Map a supported authenticated media actor to its audit enum."""

        if isinstance(actor, TenantAdmin):
            return MediaUploadedByActorType.TENANT_ADMIN
        if isinstance(actor, Teacher):
            return MediaUploadedByActorType.TEACHER
        if isinstance(actor, Student):
            return MediaUploadedByActorType.STUDENT
        raise ForbiddenException(detail="This account cannot manage passport photos")

    @staticmethod
    def _get_storage_provider() -> MediaStorageProvider:
        """Resolve configured storage provider into the model enum."""

        provider = (
            str(getattr(settings, "MEDIA_STORAGE_PROVIDER", "local")).strip().lower()
        )

        if provider in {"cloudflare_r2", "r2", "cloudflare"}:
            return MediaStorageProvider.R2

        if provider == "local":
            return MediaStorageProvider.LOCAL

        raise BadRequestException(
            detail=f"Unsupported media storage provider: {provider}"
        )

    @staticmethod
    def _get_render_url(media_asset: MediaAsset) -> str | None:
        """Return the best immediately renderable URL for a media asset."""

        return media_asset.cdn_url or media_asset.public_url

    @staticmethod
    async def _get_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> Tenant:
        """Get a tenant by ID."""

        tenant = await TenantRepository.get_by_id(
            db=db,
            tenant_id=tenant_id,
        )

        if tenant is None:
            raise NotFoundException(detail="Tenant not found")

        return tenant

    @staticmethod
    async def _get_student_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        student_id: UUID,
    ) -> Student:
        """Get a student within a tenant."""

        student = await StudentRepository.get_student_by_id(
            db=db,
            tenant_id=tenant_id,
            student_id=student_id,
        )

        if student is None:
            raise NotFoundException(detail="Student not found")

        return student

    @staticmethod
    async def _get_teacher_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        teacher_id: UUID,
    ) -> Teacher:
        """Get a teacher within a tenant."""

        teacher = await TeacherRepository.get_teacher_by_id(
            db=db,
            tenant_id=tenant_id,
            teacher_id=teacher_id,
        )

        if teacher is None:
            raise NotFoundException(detail="Teacher not found")

        return teacher

    @staticmethod
    async def _get_tenant_admin_for_tenant(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        tenant_admin_id: UUID,
    ) -> TenantAdmin:
        """Get a tenant admin within a tenant."""

        tenant_admin = await TenantAdminRepository.get_by_tenant_and_id(
            db=db,
            tenant_id=tenant_id,
            admin_id=tenant_admin_id,
        )

        if tenant_admin is None:
            raise NotFoundException(detail="Tenant admin not found")

        return tenant_admin

    @staticmethod
    def _validate_owner_purpose_pair(
        *,
        owner_type: MediaOwnerType,
        purpose: MediaPurpose,
    ) -> None:
        """Ensure a purpose is valid for an owner type."""

        valid_pairs = {
            MediaOwnerType.TENANT: {MediaPurpose.SCHOOL_LOGO},
            MediaOwnerType.STUDENT: {MediaPurpose.STUDENT_PASSPORT},
            MediaOwnerType.TEACHER: {MediaPurpose.TEACHER_PASSPORT},
            MediaOwnerType.TENANT_ADMIN: {MediaPurpose.TENANT_ADMIN_PASSPORT},
        }

        if purpose not in valid_pairs.get(owner_type, set()):
            raise BadRequestException(
                detail=(
                    f"Media purpose {purpose.value} is not valid for owner type {owner_type.value}"
                )
            )

    @staticmethod
    async def _validate_file_for_purpose(
        *,
        file: UploadFile,
        purpose: MediaPurpose,
    ):
        """Validate uploaded file based on purpose."""

        try:
            if purpose == MediaPurpose.SCHOOL_LOGO:
                return await validate_school_logo_upload(file)

            if purpose == MediaPurpose.STUDENT_PASSPORT:
                return await validate_student_passport_upload(file)

            if purpose == MediaPurpose.TEACHER_PASSPORT:
                return await validate_teacher_passport_upload(file)

            if purpose == MediaPurpose.TENANT_ADMIN_PASSPORT:
                return await validate_tenant_admin_passport_upload(file)

        except MediaValidationError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        raise BadRequestException(detail=f"Unsupported media purpose: {purpose.value}")

    @staticmethod
    def _ensure_owner_has_media_url_field(
        owner: object,
        *,
        field_name: str,
        owner_label: str,
    ) -> None:
        """Fail fast when the owner model cannot persist a convenience URL field."""

        if not hasattr(owner, field_name):
            raise BadRequestException(
                detail=(
                    f"{owner_label} uploads are not fully wired yet because the "
                    f"{owner_label} model does not define `{field_name}`."
                )
            )

    @staticmethod
    def _get_owner_media_url_for_attachment(
        *,
        media_asset: MediaAsset,
        purpose: MediaPurpose,
    ) -> str | None:
        """Return the URL safe to persist on owner convenience URL fields."""

        render_url = MediaService._get_render_url(media_asset)
        if render_url is not None:
            return render_url

        if purpose == MediaPurpose.SCHOOL_LOGO:
            raise BadRequestException(
                detail="Uploaded school logo does not have a renderable URL"
            )

        return None

    @staticmethod
    async def _attach_media_to_owner(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
        media_asset: MediaAsset,
    ) -> None:
        """Update the owner's convenience URL field after media upload."""

        attachment_url = MediaService._get_owner_media_url_for_attachment(
            media_asset=media_asset,
            purpose=purpose,
        )

        if owner_type == MediaOwnerType.TENANT and purpose == MediaPurpose.SCHOOL_LOGO:
            tenant = await MediaService._get_tenant(db=db, tenant_id=tenant_id)
            tenant.logo_url = attachment_url
            await TenantRepository.save(db=db, tenant=tenant)
            await invalidate_tenant_branding(tenant_id, db=db)
            return

        if (
            owner_type == MediaOwnerType.STUDENT
            and purpose == MediaPurpose.STUDENT_PASSPORT
        ):
            student = await MediaService._get_student_for_tenant(
                db=db,
                tenant_id=tenant_id,
                student_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                student,
                field_name="passport_photo_url",
                owner_label="Student passport",
            )
            student.passport_photo_url = attachment_url
            await StudentRepository.save(db=db, student=student)
            return

        if (
            owner_type == MediaOwnerType.TEACHER
            and purpose == MediaPurpose.TEACHER_PASSPORT
        ):
            teacher = await MediaService._get_teacher_for_tenant(
                db=db,
                tenant_id=tenant_id,
                teacher_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                teacher,
                field_name="passport_photo_url",
                owner_label="Teacher passport",
            )
            teacher.passport_photo_url = attachment_url
            await TeacherRepository.save(db=db, teacher=teacher)
            return

        if (
            owner_type == MediaOwnerType.TENANT_ADMIN
            and purpose == MediaPurpose.TENANT_ADMIN_PASSPORT
        ):
            tenant_admin = await MediaService._get_tenant_admin_for_tenant(
                db=db,
                tenant_id=tenant_id,
                tenant_admin_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                tenant_admin,
                field_name="passport_photo_url",
                owner_label="Tenant admin passport",
            )
            tenant_admin.passport_photo_url = attachment_url
            await TenantAdminRepository.save(db=db, admin=tenant_admin)
            return

        raise BadRequestException(detail="Unsupported owner/purpose attachment target")

    @staticmethod
    async def _detach_media_from_owner(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
    ) -> None:
        """Clear the owner's convenience URL field after media deletion."""

        if owner_type == MediaOwnerType.TENANT and purpose == MediaPurpose.SCHOOL_LOGO:
            tenant = await MediaService._get_tenant(db=db, tenant_id=tenant_id)
            tenant.logo_url = None
            await TenantRepository.save(db=db, tenant=tenant)
            await invalidate_tenant_branding(tenant_id, db=db)
            return

        if (
            owner_type == MediaOwnerType.STUDENT
            and purpose == MediaPurpose.STUDENT_PASSPORT
        ):
            student = await MediaService._get_student_for_tenant(
                db=db,
                tenant_id=tenant_id,
                student_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                student,
                field_name="passport_photo_url",
                owner_label="Student passport",
            )
            student.passport_photo_url = None
            await StudentRepository.save(db=db, student=student)
            return

        if (
            owner_type == MediaOwnerType.TEACHER
            and purpose == MediaPurpose.TEACHER_PASSPORT
        ):
            teacher = await MediaService._get_teacher_for_tenant(
                db=db,
                tenant_id=tenant_id,
                teacher_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                teacher,
                field_name="passport_photo_url",
                owner_label="Teacher passport",
            )
            teacher.passport_photo_url = None
            await TeacherRepository.save(db=db, teacher=teacher)
            return

        if (
            owner_type == MediaOwnerType.TENANT_ADMIN
            and purpose == MediaPurpose.TENANT_ADMIN_PASSPORT
        ):
            tenant_admin = await MediaService._get_tenant_admin_for_tenant(
                db=db,
                tenant_id=tenant_id,
                tenant_admin_id=owner_id,
            )
            MediaService._ensure_owner_has_media_url_field(
                tenant_admin,
                field_name="passport_photo_url",
                owner_label="Tenant admin passport",
            )
            tenant_admin.passport_photo_url = None
            await TenantAdminRepository.save(db=db, admin=tenant_admin)
            return

        raise BadRequestException(detail="Unsupported owner/purpose detach target")

    @staticmethod
    async def _create_and_attach_media(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Student,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Validate, upload, persist, and attach a media asset to its owner."""

        if actor is None or actor.tenant_id is None:
            raise ForbiddenException(detail="Actor is not attached to a tenant")
        MediaService._validate_owner_purpose_pair(
            owner_type=owner_type, purpose=purpose
        )

        tenant_id = actor.tenant_id
        media_asset_id = uuid4()

        validated_file = await MediaService._validate_file_for_purpose(
            file=file,
            purpose=purpose,
        )
        visibility = get_visibility_for_purpose(purpose)
        cache_control = get_cache_control_for_purpose(purpose)
        storage_provider = MediaService._get_storage_provider()
        object_key = build_media_object_key(
            tenant_id=tenant_id,
            owner_type=owner_type,
            owner_id=owner_id,
            purpose=purpose,
            media_asset_id=media_asset_id,
            extension=validated_file.extension,
        )

        storage = get_media_storage()
        uploaded_object = None

        try:
            uploaded_object = await storage.upload_object(
                object_key=object_key,
                data=validated_file.data,
                content_type=validated_file.content_type,
                visibility=visibility,
                cache_control=cache_control,
                metadata={
                    "tenant_id": str(tenant_id),
                    "owner_type": owner_type.value,
                    "owner_id": str(owner_id),
                    "purpose": purpose.value,
                    "checksum_sha256": validated_file.checksum_sha256,
                },
            )

            await MediaAssetRepository.mark_current_assets_as_replaced(
                db,
                tenant_id=tenant_id,
                owner_type=owner_type,
                owner_id=owner_id,
                purpose=purpose,
                replaced_by_media_asset_id=media_asset_id,
            )

            media_asset = await MediaAssetRepository.create_asset(
                db,
                asset_data=MediaCreateData(
                    id=media_asset_id,
                    tenant_id=tenant_id,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    purpose=purpose,
                    visibility=visibility,
                    storage_provider=storage_provider,
                    bucket=uploaded_object.bucket,
                    object_key=uploaded_object.object_key,
                    public_url=uploaded_object.public_url,
                    cdn_url=uploaded_object.cdn_url,
                    original_filename=validated_file.original_filename,
                    content_type=validated_file.content_type,
                    extension=validated_file.extension,
                    size_bytes=validated_file.size_bytes,
                    checksum_sha256=validated_file.checksum_sha256,
                    etag=uploaded_object.etag,
                    cache_control=cache_control,
                    width_px=validated_file.width_px,
                    height_px=validated_file.height_px,
                    metadata_json={"storage": uploaded_object.metadata or {}},
                    uploaded_by_actor_type=MediaService._get_uploader_type(actor),
                    uploaded_by_actor_id=actor.id,
                    is_current=True,
                ),
            )

            await MediaService._attach_media_to_owner(
                db=db,
                tenant_id=tenant_id,
                owner_type=owner_type,
                owner_id=owner_id,
                purpose=purpose,
                media_asset=media_asset,
            )

            await db.flush()
            await db.refresh(media_asset)

            return MediaUploadResponse(
                media_asset=media_asset,
                render_url=MediaService._get_render_url(media_asset),
                message="Media uploaded successfully.",
            )

        except Exception:
            if uploaded_object is not None:
                try:
                    await storage.delete_object(object_key=uploaded_object.object_key)
                except Exception:
                    pass
            raise

    @staticmethod
    async def upload_school_logo(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Upload or replace the current tenant school logo."""

        MediaService._ensure_tenant_admin(actor)
        await MediaService._get_tenant(db=db, tenant_id=actor.tenant_id)

        return await MediaService._create_and_attach_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TENANT,
            owner_id=actor.tenant_id,
            purpose=MediaPurpose.SCHOOL_LOGO,
            file=file,
        )

    @staticmethod
    async def upload_student_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Upload or replace a student's passport photo."""

        MediaService._ensure_tenant_admin(actor)
        await MediaService._get_student_for_tenant(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )

        return await MediaService._create_and_attach_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.STUDENT,
            owner_id=student_id,
            purpose=MediaPurpose.STUDENT_PASSPORT,
            file=file,
        )

    @staticmethod
    async def upload_teacher_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        teacher_id: UUID,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Upload or replace a teacher's passport photo."""

        MediaService._ensure_tenant_admin(actor)
        await MediaService._get_teacher_for_tenant(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher_id,
        )

        return await MediaService._create_and_attach_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TEACHER,
            owner_id=teacher_id,
            purpose=MediaPurpose.TEACHER_PASSPORT,
            file=file,
        )

    @staticmethod
    async def upload_tenant_admin_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Upload or replace the current tenant admin's passport photo."""

        MediaService._ensure_tenant_admin(actor)

        return await MediaService._create_and_attach_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TENANT_ADMIN,
            owner_id=actor.id,
            purpose=MediaPurpose.TENANT_ADMIN_PASSPORT,
            file=file,
        )

    @staticmethod
    async def upload_profile_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Student,
        file: UploadFile,
    ) -> MediaUploadResponse:
        """Upload the authenticated actor's own supported passport photo."""

        if isinstance(actor, TenantAdmin):
            owner_type = MediaOwnerType.TENANT_ADMIN
            purpose = MediaPurpose.TENANT_ADMIN_PASSPORT
        elif isinstance(actor, Teacher):
            owner_type = MediaOwnerType.TEACHER
            purpose = MediaPurpose.TEACHER_PASSPORT
        elif isinstance(actor, Student):
            owner_type = MediaOwnerType.STUDENT
            purpose = MediaPurpose.STUDENT_PASSPORT
        else:
            raise ForbiddenException(
                detail="This account does not support passport photos"
            )

        return await MediaService._create_and_attach_media(
            db=db,
            actor=actor,
            owner_type=owner_type,
            owner_id=actor.id,
            purpose=purpose,
            file=file,
        )

    @staticmethod
    async def _delete_current_media(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Student,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Soft-delete current media and optionally delete the physical object."""

        if actor is None or actor.tenant_id is None:
            raise ForbiddenException(detail="Actor is not attached to a tenant")
        MediaService._validate_owner_purpose_pair(
            owner_type=owner_type, purpose=purpose
        )

        media_asset = await MediaAssetRepository.get_current_for_owner(
            db,
            tenant_id=actor.tenant_id,
            owner_type=owner_type,
            owner_id=owner_id,
            purpose=purpose,
            lock=True,
        )

        if media_asset is None:
            raise NotFoundException(detail="Current media asset not found")

        if delete_object:
            storage = get_media_storage()
            await storage.delete_object(object_key=media_asset.object_key)

        deleted_asset = await MediaAssetRepository.soft_delete_asset(
            db,
            media_asset=media_asset,
        )

        await MediaService._detach_media_from_owner(
            db=db,
            tenant_id=actor.tenant_id,
            owner_type=owner_type,
            owner_id=owner_id,
            purpose=purpose,
        )
        await db.flush()

        return MediaDeleteResponse(
            media_asset_id=deleted_asset.id,
            owner_type=owner_type,
            owner_id=owner_id,
            purpose=purpose,
            deleted=True,
            message="Media deleted successfully.",
        )

    @staticmethod
    async def delete_current_school_logo(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Delete/detach the current tenant school logo."""

        return await MediaService._delete_current_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TENANT,
            owner_id=actor.tenant_id,
            purpose=MediaPurpose.SCHOOL_LOGO,
            delete_object=delete_object,
        )

    @staticmethod
    async def delete_current_student_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        student_id: UUID,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Delete/detach the current student passport photo."""

        MediaService._ensure_tenant_admin(actor)
        await MediaService._get_student_for_tenant(
            db=db,
            tenant_id=actor.tenant_id,
            student_id=student_id,
        )

        return await MediaService._delete_current_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.STUDENT,
            owner_id=student_id,
            purpose=MediaPurpose.STUDENT_PASSPORT,
            delete_object=delete_object,
        )

    @staticmethod
    async def delete_current_teacher_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        teacher_id: UUID,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Delete/detach the current teacher passport photo."""

        MediaService._ensure_tenant_admin(actor)
        await MediaService._get_teacher_for_tenant(
            db=db,
            tenant_id=actor.tenant_id,
            teacher_id=teacher_id,
        )

        return await MediaService._delete_current_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TEACHER,
            owner_id=teacher_id,
            purpose=MediaPurpose.TEACHER_PASSPORT,
            delete_object=delete_object,
        )

    @staticmethod
    async def delete_current_tenant_admin_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Delete/detach the current tenant admin passport photo."""

        return await MediaService._delete_current_media(
            db=db,
            actor=actor,
            owner_type=MediaOwnerType.TENANT_ADMIN,
            owner_id=actor.id,
            purpose=MediaPurpose.TENANT_ADMIN_PASSPORT,
            delete_object=delete_object,
        )

    @staticmethod
    async def delete_current_profile_passport(
        db: AsyncSession,
        *,
        actor: TenantAdmin | Teacher | Student,
        delete_object: bool = False,
    ) -> MediaDeleteResponse:
        """Delete the authenticated actor's own supported passport photo."""

        if isinstance(actor, TenantAdmin):
            owner_type = MediaOwnerType.TENANT_ADMIN
            purpose = MediaPurpose.TENANT_ADMIN_PASSPORT
        elif isinstance(actor, Teacher):
            owner_type = MediaOwnerType.TEACHER
            purpose = MediaPurpose.TEACHER_PASSPORT
        elif isinstance(actor, Student):
            owner_type = MediaOwnerType.STUDENT
            purpose = MediaPurpose.STUDENT_PASSPORT
        else:
            raise ForbiddenException(
                detail="This account does not support passport photos"
            )

        return await MediaService._delete_current_media(
            db=db,
            actor=actor,
            owner_type=owner_type,
            owner_id=actor.id,
            purpose=purpose,
            delete_object=delete_object,
        )

    @staticmethod
    async def get_media_asset(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        media_asset_id: UUID,
    ) -> MediaAsset:
        """Get a media asset by ID for the current tenant."""

        MediaService._ensure_tenant_admin(actor)
        media_asset = await MediaAssetRepository.get_by_id(
            db,
            tenant_id=actor.tenant_id,
            media_asset_id=media_asset_id,
        )

        if media_asset is None:
            raise NotFoundException(detail="Media asset not found")

        return media_asset

    @staticmethod
    async def get_current_media_for_owner(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        owner_type: MediaOwnerType,
        owner_id: UUID,
        purpose: MediaPurpose,
    ) -> MediaAsset:
        """Get the current media asset for an owner and purpose."""

        MediaService._ensure_tenant_admin(actor)
        MediaService._validate_owner_purpose_pair(
            owner_type=owner_type, purpose=purpose
        )

        media_asset = await MediaAssetRepository.get_current_for_owner(
            db,
            tenant_id=actor.tenant_id,
            owner_type=owner_type,
            owner_id=owner_id,
            purpose=purpose,
        )

        if media_asset is None:
            raise NotFoundException(detail="Media asset not found")

        return media_asset

    @staticmethod
    async def list_media_assets(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        skip: int = 0,
        limit: int = 50,
        owner_type: MediaOwnerType | None = None,
        owner_id: UUID | None = None,
        purpose: MediaPurpose | None = None,
        visibility: MediaVisibility | None = None,
        status: MediaStatus | None = None,
        current_only: bool = True,
    ) -> MediaAssetListResponse:
        """List media assets for the current tenant."""

        MediaService._ensure_tenant_admin(actor)
        items, total = await MediaAssetRepository.list_assets(
            db,
            tenant_id=actor.tenant_id,
            filters=MediaAssetFilter(
                owner_type=owner_type,
                owner_id=owner_id,
                purpose=purpose,
                visibility=visibility,
                status=status,
                current_only=current_only,
            ),
            skip=skip,
            limit=limit,
        )

        return MediaAssetListResponse(items=items, total=total)

    @staticmethod
    async def create_signed_url_for_asset(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        media_asset_id: UUID,
        expires_in_seconds: int = 300,
    ) -> MediaSignedUrlResponse:
        """Create a temporary signed URL for a private media asset."""

        MediaService._ensure_tenant_admin(actor)

        if expires_in_seconds <= 0:
            raise BadRequestException(
                detail="Signed URL expiry must be greater than zero"
            )

        media_asset = await MediaAssetRepository.get_by_id(
            db,
            tenant_id=actor.tenant_id,
            media_asset_id=media_asset_id,
        )

        if media_asset is None:
            raise NotFoundException(detail="Media asset not found")

        if media_asset.visibility != MediaVisibility.PRIVATE:
            render_url = MediaService._get_render_url(media_asset)
            if render_url is None:
                raise NotFoundException(detail="Media asset URL not found")

            return MediaSignedUrlResponse(
                media_asset_id=media_asset.id,
                owner_type=media_asset.owner_type,
                owner_id=media_asset.owner_id,
                purpose=media_asset.purpose,
                signed_url=render_url,
                signed_url_expires_at=None,
            )

        storage = get_media_storage()
        signed_url = await storage.create_signed_url(
            object_key=media_asset.object_key,
            expires_in_seconds=expires_in_seconds,
        )
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        media_asset.signed_url_expires_at = expires_at
        await MediaAssetRepository.save(db, media_asset=media_asset)

        return MediaSignedUrlResponse(
            media_asset_id=media_asset.id,
            owner_type=media_asset.owner_type,
            owner_id=media_asset.owner_id,
            purpose=media_asset.purpose,
            signed_url=signed_url,
            signed_url_expires_at=expires_at,
        )
