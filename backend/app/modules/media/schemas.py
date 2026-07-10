#==========================#
#      media.schemas       #
#==========================#
"""Pydantic schemas for the media module.

This file will define request and response shapes used by the API layer
when media resources are created, updated, or returned.
"""





from __future__ import annotations
from pydantic import BaseModel , ConfigDict , Field , field_validator
from datetime import datetime 
from typing import Any
import uuid

from app.modules.media.models import(
    MediaOwnerType,
    MediaPurpose,
    MediaStatus,
    MediaStorageProvider,
    MediaUploadedByActorType,
    MediaVisibility
)



class InputBase(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace= True ,
        extra="forbid"
    )



class OutputBase(BaseModel):
    model_config = ConfigDict(
        from_attributes = True,
        use_enum_values=True ,
        populate_by_name=True
    )



class MediaAssetResponse(OutputBase):
    """full media asset respons returned afrer upload or direct lookup"""



    id : uuid.UUID  #id of the media file
    tenant_id : uuid.UUID

    owner_type : MediaOwnerType
    owner_id : uuid.UUID    #id of the owner of the media file
    purpose : MediaPurpose


    visibility : MediaVisibility
    status : MediaStatus
    storage_provider :  MediaStorageProvider

    bucket : str 
    object_key : str


    public_url : str | None = None 
    cdn_url : str | None = None
    signed_url : str | None = Field(
        default = None,
        description = (
            "Temporary URL for private media. this should ony be returned when"
            "the current actor is allowed to view the file"
        )
    )


    original_filename : str | None = None
    content_type : str 
    extension : str | None = None
    size_bytes : int


    checksum_sha256 : str | None = None



    etag: str | None = Field(
        default=None,
        description="Cloudflare R2/S3-compatible ETag returned after upload.",
    )
    cache_control: str | None = Field(
        default=None,
        description="Cache-Control value applied to the stored object.",
    )

    width_px: int | None = None
    height_px: int | None = None

    metadata_json: dict[str, Any] | None = None

    uploaded_by_actor_type: MediaUploadedByActorType | None = None
    uploaded_by_actor_id: uuid.UUID | None = None

    is_current: bool
    replaced_by_media_asset_id: uuid.UUID | None = None
    deleted_at: datetime | None = None

    created_at: datetime
    updated_at: datetime





class MediaAssetSummaryResponse(OutputBase):
    """Compact media response for embedded responses and list views."""

    id: uuid.UUID
    tenant_id: uuid.UUID

    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose

    visibility: MediaVisibility
    status: MediaStatus

    public_url: str | None = None
    cdn_url: str | None = None
    signed_url: str | None = None
    signed_url_expires_at: datetime | None = None

    content_type: str
    size_bytes: int
    width_px: int | None = None
    height_px: int | None = None

    is_current: bool
    created_at: datetime
    updated_at: datetime





class MediaUploadResponse(OutputBase):
    """Response returned after a successful media upload."""

    media_asset: MediaAssetResponse
    render_url: str | None = Field(
        default=None,
        description=(
            "Best URL for immediate frontend rendering. For public assets this is "
            "usually cdn_url or public_url. For private assets this may be signed_url."
        ),
    )
    message: str = "Media uploaded successfully."





class MediaDeleteResponse(OutputBase):
    """Response returned after a media asset is deleted/detached."""

    media_asset_id: uuid.UUID
    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose
    deleted: bool = True
    message: str = "Media deleted successfully."




class MediaAssetListResponse(OutputBase):
    """Paginated media asset list response."""

    items: list[MediaAssetSummaryResponse]
    total: int





class MediaAssetFilter(InputBase):
    """Filters for listing media assets."""

    owner_type: MediaOwnerType | None = None
    owner_id: uuid.UUID | None = None
    purpose: MediaPurpose | None = None
    visibility: MediaVisibility | None = None
    status: MediaStatus | None = None
    current_only: bool = True






class MediaUploadContext(BaseModel):
    """Internal context used by the media service during uploads.

    This is not a public request schema. Upload endpoints receive UploadFile,
    then the router/service builds this context from the authenticated actor.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tenant_id: uuid.UUID
    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose
    visibility: MediaVisibility

    uploaded_by_actor_type: MediaUploadedByActorType
    uploaded_by_actor_id: uuid.UUID

    metadata_json: dict[str, Any] | None = None


class MediaCreateData(BaseModel):
    """Internal payload used to persist a MediaAsset after storage upload."""
    id : uuid.UUID
    tenant_id: uuid.UUID

    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose

    visibility: MediaVisibility
    status: MediaStatus = MediaStatus.ACTIVE
    storage_provider: MediaStorageProvider

    bucket: str
    object_key: str

    public_url: str | None = None
    cdn_url: str | None = None
    signed_url: str | None = None
    signed_url_expires_at: datetime | None = None

    original_filename: str | None = None
    content_type: str
    extension: str | None = None
    size_bytes: int = Field(..., ge=0)

    checksum_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    etag: str | None = None
    cache_control: str | None = None

    width_px: int | None = Field(default=None, ge=1)
    height_px: int | None = Field(default=None, ge=1)

    metadata_json: dict[str, Any] | None = None

    uploaded_by_actor_type: MediaUploadedByActorType | None = None
    uploaded_by_actor_id: uuid.UUID | None = None

    is_current: bool = True
    replaced_by_media_asset_id: uuid.UUID | None = None

    @field_validator("bucket", "object_key", "content_type", mode="before")
    @classmethod
    def clean_required_text(cls, value: object) -> str:
        """Trim required text fields."""

        if value is None:
            raise ValueError("This field is required.")

        cleaned_value = str(value).strip()
        if not cleaned_value:
            raise ValueError("This field cannot be blank.")

        return cleaned_value

    @field_validator(
        "public_url",
        "cdn_url",
        "signed_url",
        "original_filename",
        "extension",
        "etag",
        "cache_control",
        mode="before",
    )
    @classmethod
    def clean_optional_text(cls, value: object) -> str | None:
        """Trim optional text fields and convert blanks to None."""

        if value is None:
            return None

        cleaned_value = str(value).strip()
        return cleaned_value or None


class MediaSignedUrlResponse(OutputBase):
    """Response for private media signed URL generation."""

    media_asset_id: uuid.UUID
    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose
    signed_url: str
    signed_url_expires_at: datetime


class MediaAttachResponse(OutputBase):
    """Response returned when a media asset is attached to an owner field."""

    media_asset: MediaAssetResponse
    owner_type: MediaOwnerType
    owner_id: uuid.UUID
    purpose: MediaPurpose
    attached: bool = True
    message: str = "Media attached successfully."






