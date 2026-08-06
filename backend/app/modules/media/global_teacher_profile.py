"""Global teacher-account profile media operations.

Teacher profile photos belong to the global ``TeacherAccount`` identity rather
than an individual tenant membership. This flow stores the current object at a
deterministic global key and persists its render URL on the account, avoiding
ownership by whichever school membership happened to be active during upload.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.core.storage.factory import get_media_storage
from app.modules.media.models import MediaPurpose
from app.modules.media.validators import (
    MediaValidationError,
    get_cache_control_for_purpose,
    get_visibility_for_purpose,
    validate_teacher_passport_upload,
)
from app.modules.teachers.models import (
    TeacherAccount,
    TeacherAccountStatus,
    TeacherMembership,
    TeacherMembershipStatus,
)
from app.modules.teachers.repository import (
    TeacherAccountRepository,
    TeacherMembershipRepository,
)


class GlobalTeacherProfileMediaService:
    """Upload and delete profile photos owned by a global teacher account."""

    @staticmethod
    def _ensure_active_account(account: TeacherAccount) -> TeacherAccount:
        if (
            not account.is_active
            or not account.is_verified
            or account.account_status != TeacherAccountStatus.ACTIVE
        ):
            raise ForbiddenException(detail="Inactive teacher account")
        return account

    @staticmethod
    def _account_from_actor(
        actor: TeacherAccount | TeacherMembership,
    ) -> TeacherAccount:
        if isinstance(actor, TeacherAccount):
            return GlobalTeacherProfileMediaService._ensure_active_account(actor)
        if isinstance(actor, TeacherMembership):
            if actor.status != TeacherMembershipStatus.ACTIVE:
                raise ForbiddenException(detail="Inactive teacher membership")
            return GlobalTeacherProfileMediaService._ensure_active_account(
                actor.teacher_account
            )
        raise ForbiddenException(detail="Teacher account credentials are required.")

    @staticmethod
    def _object_key(account_id: UUID) -> str:
        # A deterministic key makes replacement atomic and deletion independent
        # of tenant membership or the original uploaded file extension.
        return f"global/teacher-accounts/{account_id}/profile/passport-photo"

    @staticmethod
    async def _get_membership_account(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
    ) -> TeacherAccount:
        membership = await TeacherMembershipRepository.get_by_id(
            db,
            membership_id,
            tenant_id=tenant_id,
            load_account=True,
        )
        if membership is None:
            raise NotFoundException(detail="Teacher membership not found")
        return GlobalTeacherProfileMediaService._ensure_active_account(
            membership.teacher_account
        )

    @staticmethod
    async def upload(
        db: AsyncSession,
        *,
        actor: TeacherAccount | TeacherMembership,
        file: UploadFile,
    ) -> dict[str, object]:
        account = GlobalTeacherProfileMediaService._account_from_actor(actor)
        return await GlobalTeacherProfileMediaService._upload_for_account(
            db=db,
            account=account,
            file=file,
        )

    @staticmethod
    async def upload_for_membership(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        file: UploadFile,
    ) -> dict[str, object]:
        account = await GlobalTeacherProfileMediaService._get_membership_account(
            db,
            tenant_id=tenant_id,
            membership_id=membership_id,
        )
        return await GlobalTeacherProfileMediaService._upload_for_account(
            db=db,
            account=account,
            file=file,
        )

    @staticmethod
    async def _upload_for_account(
        db: AsyncSession,
        *,
        account: TeacherAccount,
        file: UploadFile,
    ) -> dict[str, object]:
        try:
            validated = await validate_teacher_passport_upload(file)
        except MediaValidationError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        storage = get_media_storage()
        object_key = GlobalTeacherProfileMediaService._object_key(account.id)
        uploaded = await storage.upload_object(
            object_key=object_key,
            data=validated.data,
            content_type=validated.content_type,
            visibility=get_visibility_for_purpose(MediaPurpose.TEACHER_PASSPORT),
            cache_control=get_cache_control_for_purpose(MediaPurpose.TEACHER_PASSPORT),
            metadata={
                "scope": "global",
                "owner_type": "teacher_account",
                "owner_id": str(account.id),
                "purpose": MediaPurpose.TEACHER_PASSPORT.value,
                "checksum_sha256": validated.checksum_sha256,
            },
        )

        render_url = uploaded.cdn_url or uploaded.public_url
        if not render_url:
            try:
                await storage.delete_object(object_key=object_key)
            except Exception:
                pass
            raise BadRequestException(
                detail="Uploaded teacher profile photo does not have a renderable URL"
            )

        account.passport_photo_url = render_url
        await TeacherAccountRepository.save(db, account)

        return {
            "render_url": render_url,
            "owner_type": "teacher_account",
            "owner_id": account.id,
            "message": "Profile photo uploaded successfully.",
        }

    @staticmethod
    async def delete(
        db: AsyncSession,
        *,
        actor: TeacherAccount | TeacherMembership,
        delete_object: bool = True,
    ) -> dict[str, object]:
        account = GlobalTeacherProfileMediaService._account_from_actor(actor)
        return await GlobalTeacherProfileMediaService._delete_for_account(
            db=db,
            account=account,
            delete_object=delete_object,
        )

    @staticmethod
    async def delete_for_membership(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        membership_id: UUID,
        delete_object: bool = True,
    ) -> dict[str, object]:
        account = await GlobalTeacherProfileMediaService._get_membership_account(
            db,
            tenant_id=tenant_id,
            membership_id=membership_id,
        )
        return await GlobalTeacherProfileMediaService._delete_for_account(
            db=db,
            account=account,
            delete_object=delete_object,
        )

    @staticmethod
    async def _delete_for_account(
        db: AsyncSession,
        *,
        account: TeacherAccount,
        delete_object: bool,
    ) -> dict[str, object]:
        if delete_object:
            storage = get_media_storage()
            try:
                await storage.delete_object(
                    object_key=GlobalTeacherProfileMediaService._object_key(account.id)
                )
            except FileNotFoundError:
                pass

        account.passport_photo_url = None
        await TeacherAccountRepository.save(db, account)

        return {
            "owner_type": "teacher_account",
            "owner_id": account.id,
            "deleted": True,
            "message": "Profile photo removed successfully.",
        }
