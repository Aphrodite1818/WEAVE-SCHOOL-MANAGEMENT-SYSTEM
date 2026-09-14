"""Build the tenant-branding projection consumed by paired CBT servers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.branding.schemas import CBTBrandingProjectionResponse
from app.modules.media.models import MediaOwnerType, MediaPurpose
from app.modules.media.repository import MediaAssetRepository
from app.modules.tenant_branding.service import TenantBrandingService


class CBTBrandingProjectionService:
    """Project effective Weave tenant branding into the CBT contract."""

    @staticmethod
    async def build_projection(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTBrandingProjectionResponse:
        tenant_id = current_server.tenant_id

        effective = await TenantBrandingService.get_effective_tenant_branding(
            db,
            tenant_id=tenant_id,
        )

        logo_asset = await MediaAssetRepository.get_current_for_owner(
            db,
            tenant_id=tenant_id,
            owner_type=MediaOwnerType.TENANT,
            owner_id=tenant_id,
            purpose=MediaPurpose.SCHOOL_LOGO,
        )

        return CBTBrandingProjectionResponse(
            tenant_id=effective.tenant_id,
            school_name=effective.school_name,
            logo_url=effective.logo_url,
            logo_revision=(logo_asset.id if logo_asset is not None else None),
            is_enabled=effective.is_enabled,
            is_default_theme=effective.is_default_theme,
            theme_version=effective.theme_version,
            token_schema_version=effective.token_schema_version,
            light_tokens=effective.light_tokens,
            dark_tokens=effective.dark_tokens,
        )
