"""Business logic for tenant branding."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.modules.parents.models import Parent
from app.modules.students.models import Student
from app.modules.teachers.models import Teacher
from app.modules.tenant_admins.models import TenantAdmin
from app.modules.tenant_branding.cache import (
    get_cached_branding,
    invalidate_tenant_branding,
    set_cached_branding,
)
from app.modules.tenant_branding.models import TenantBranding, TenantBrandingThemeMode
from app.modules.tenant_branding.repository import TenantBrandingRepository
from app.modules.tenant_branding.schemas import (
    TenantBrandingEffectiveResponse,
    TenantBrandingResetResponse,
    TenantBrandingResponse,
    TenantBrandingUpdate,
)
from app.modules.tenant_branding.theme_builder import (
    DEFAULT_ACCENT_COLOR,
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_BRAND_NAME,
    DEFAULT_HEADER_COLOR,
    DEFAULT_PRIMARY_COLOR,
    DEFAULT_SIDEBAR_COLOR,
    DEFAULT_THEME_MODE,
    build_default_theme_tokens,
    build_theme_tokens,
    channels_to_hex,
    get_default_background_color,
    get_default_header_color,
    is_complete_theme_token_set,
    normalize_hex_color,
)
from app.tenant_management.models import Tenant
from app.tenant_management.repository import TenantRepository

TenantActor = TenantAdmin | Teacher | Student | Parent


class TenantBrandingService:
    """Business rules for tenant branding configuration and resolution."""

    @staticmethod
    def _ensure_tenant_admin(actor: TenantAdmin) -> UUID:
        """Ensure the actor is an attached tenant admin."""

        if not isinstance(actor, TenantAdmin):
            raise ForbiddenException(detail="Only tenant admins can manage tenant branding.")

        if not actor.tenant_id:
            raise ForbiddenException(detail="Tenant admin is not attached to a tenant.")

        return actor.tenant_id

    @staticmethod
    def _resolve_effective_tenant_id(
        *,
        actor: TenantActor | None,
        tenant_id: UUID | None,
    ) -> UUID:
        """Resolve the tenant ID for effective-branding lookups."""

        if actor is not None:
            if not isinstance(actor, (TenantAdmin, Teacher, Student, Parent)):
                raise ForbiddenException(detail="Unsupported actor type for tenant branding.")

            if not actor.tenant_id:
                raise ForbiddenException(detail="Actor is not attached to a tenant.")

            if tenant_id is not None and tenant_id != actor.tenant_id:
                raise ForbiddenException(detail="You are not allowed to access another tenant's branding.")

            return actor.tenant_id

        if tenant_id is None:
            raise BadRequestException(detail="A tenant actor or tenant_id is required.")

        return tenant_id

    @staticmethod
    async def _get_tenant_or_raise(
        db: AsyncSession,
        *,
        tenant_id: UUID,
    ) -> Tenant:
        """Load a tenant or raise a not-found error."""

        tenant = await TenantRepository.get_by_id(db=db, tenant_id=tenant_id)
        if tenant is None:
            raise NotFoundException(detail="Tenant not found.")
        return tenant

    @staticmethod
    def _default_branding_values(
        *,
        logo_url: str | None,
    ) -> dict[str, object]:
        """Return the default stored branding values."""

        return {
            "brand_name": DEFAULT_BRAND_NAME,
            "logo_url": logo_url,
            "primary_color": DEFAULT_PRIMARY_COLOR,
            "accent_color": DEFAULT_ACCENT_COLOR,
            "sidebar_color": DEFAULT_SIDEBAR_COLOR,
            "theme_mode": DEFAULT_THEME_MODE,
            "tokens": build_default_theme_tokens(),
            "is_enabled": False,
        }

    @staticmethod
    def _ensure_tokens(branding: TenantBranding) -> dict[str, str]:
        """Return a complete token set for a branding row."""

        if is_complete_theme_token_set(branding.tokens):
            return dict(branding.tokens)

        return build_theme_tokens(
            primary_color=branding.primary_color,
            accent_color=branding.accent_color,
            sidebar_color=branding.sidebar_color,
            theme_mode=branding.theme_mode,
        )

    @staticmethod
    def _resolve_header_color(
        *,
        theme_mode: TenantBrandingThemeMode,
        tokens: dict[str, str] | None,
    ) -> str:
        """Resolve a header color from tokens with a safe theme-mode fallback."""

        fallback = get_default_header_color(theme_mode)
        token_value = (tokens or {}).get("--color-header-background")
        if not token_value:
            return fallback

        try:
            return channels_to_hex(token_value)
        except ValueError:
            return fallback

    @staticmethod
    def _resolve_background_color(
        *,
        theme_mode: TenantBrandingThemeMode,
        tokens: dict[str, str] | None,
    ) -> str:
        """Resolve a workspace background color from tokens with a safe fallback."""

        fallback = get_default_background_color(theme_mode)
        token_value = (tokens or {}).get("--color-workspace-background")
        if not token_value:
            return fallback

        try:
            return channels_to_hex(token_value)
        except ValueError:
            return fallback

    @staticmethod
    def _build_admin_response(
        *,
        tenant_id: UUID,
        logo_url: str | None,
        branding: TenantBranding | None,
    ) -> TenantBrandingResponse:
        """Build the admin-facing branding response."""

        if branding is None:
            return TenantBrandingResponse(
                id=None,
                tenant_id=tenant_id,
                brand_name=DEFAULT_BRAND_NAME,
                logo_url=logo_url,
                primary_color=DEFAULT_PRIMARY_COLOR,
                accent_color=DEFAULT_ACCENT_COLOR,
                sidebar_color=DEFAULT_SIDEBAR_COLOR,
                header_color=DEFAULT_HEADER_COLOR,
                background_color=DEFAULT_BACKGROUND_COLOR,
                theme_mode=DEFAULT_THEME_MODE,
                tokens=build_default_theme_tokens(),
                is_enabled=False,
                theme_version=0,
                updated_by_admin_id=None,
                created_at=None,
                updated_at=None,
            )

        tokens = TenantBrandingService._ensure_tokens(branding)
        return TenantBrandingResponse(
            id=branding.id,
            tenant_id=branding.tenant_id,
            brand_name=branding.brand_name,
            logo_url=logo_url,
            primary_color=branding.primary_color,
            accent_color=branding.accent_color,
            sidebar_color=branding.sidebar_color,
            header_color=TenantBrandingService._resolve_header_color(
                theme_mode=branding.theme_mode,
                tokens=tokens,
            ),
            background_color=TenantBrandingService._resolve_background_color(
                theme_mode=branding.theme_mode,
                tokens=tokens,
            ),
            theme_mode=branding.theme_mode,
            tokens=tokens,
            is_enabled=branding.is_enabled,
            theme_version=branding.theme_version,
            updated_by_admin_id=branding.updated_by_admin_id,
            created_at=branding.created_at,
            updated_at=branding.updated_at,
        )

    @staticmethod
    def _build_effective_default_response(
        *,
        tenant_id: UUID,
        logo_url: str | None,
        theme_version: int = 0,
    ) -> TenantBrandingEffectiveResponse:
        """Build the default Weave effective-branding response."""

        return TenantBrandingEffectiveResponse(
            tenant_id=tenant_id,
            brand_name=DEFAULT_BRAND_NAME,
            logo_url=logo_url,
            primary_color=DEFAULT_PRIMARY_COLOR,
            accent_color=DEFAULT_ACCENT_COLOR,
            sidebar_color=DEFAULT_SIDEBAR_COLOR,
            header_color=DEFAULT_HEADER_COLOR,
            background_color=DEFAULT_BACKGROUND_COLOR,
            theme_mode=DEFAULT_THEME_MODE,
            tokens=build_default_theme_tokens(),
            is_enabled=False,
            theme_version=theme_version,
            is_default_theme=True,
        )

    @staticmethod
    def _build_effective_branding_response(
        *,
        tenant: Tenant,
        branding: TenantBranding | None,
    ) -> TenantBrandingEffectiveResponse:
        """Build the effective branding response for authenticated tenant users."""

        if branding is None:
            return TenantBrandingService._build_effective_default_response(
                tenant_id=tenant.id,
                logo_url=tenant.logo_url,
            )

        if not branding.is_enabled:
            return TenantBrandingService._build_effective_default_response(
                tenant_id=tenant.id,
                logo_url=tenant.logo_url,
                theme_version=branding.theme_version,
            )

        tokens = TenantBrandingService._ensure_tokens(branding)
        return TenantBrandingEffectiveResponse(
            tenant_id=tenant.id,
            brand_name=branding.brand_name,
            logo_url=tenant.logo_url,
            primary_color=branding.primary_color,
            accent_color=branding.accent_color,
            sidebar_color=branding.sidebar_color,
            header_color=TenantBrandingService._resolve_header_color(
                theme_mode=branding.theme_mode,
                tokens=tokens,
            ),
            background_color=TenantBrandingService._resolve_background_color(
                theme_mode=branding.theme_mode,
                tokens=tokens,
            ),
            theme_mode=branding.theme_mode,
            tokens=tokens,
            is_enabled=True,
            theme_version=branding.theme_version,
            is_default_theme=False,
        )

    @staticmethod
    def _normalize_update_values(
        *,
        current_brand_name: str,
        current_primary_color: str,
        current_accent_color: str,
        current_sidebar_color: str,
        current_header_color: str,
        current_background_color: str,
        current_theme_mode: TenantBrandingThemeMode,
        current_is_enabled: bool,
        payload: TenantBrandingUpdate,
    ) -> dict[str, object]:
        """Merge and normalize a partial branding update against current values."""

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            raise BadRequestException(detail="No branding update data provided.")

        next_brand_name = current_brand_name
        if "brand_name" in update_data:
            next_brand_name = update_data["brand_name"] or DEFAULT_BRAND_NAME

        next_primary_color = current_primary_color
        if "primary_color" in update_data:
            next_primary_color = normalize_hex_color(
                update_data["primary_color"] or DEFAULT_PRIMARY_COLOR
            )

        next_accent_color = current_accent_color
        if "accent_color" in update_data:
            next_accent_color = normalize_hex_color(
                update_data["accent_color"] or DEFAULT_ACCENT_COLOR
            )

        next_sidebar_color = current_sidebar_color
        if "sidebar_color" in update_data:
            next_sidebar_color = normalize_hex_color(
                update_data["sidebar_color"] or DEFAULT_SIDEBAR_COLOR
            )

        next_header_color = current_header_color
        if "header_color" in update_data:
            next_header_color = normalize_hex_color(
                update_data["header_color"] or get_default_header_color(current_theme_mode)
            )

        next_background_color = current_background_color
        if "background_color" in update_data:
            next_background_color = normalize_hex_color(
                update_data["background_color"] or get_default_background_color(current_theme_mode)
            )

        next_theme_mode = current_theme_mode
        if "theme_mode" in update_data and update_data["theme_mode"] is not None:
            next_theme_mode = TenantBrandingThemeMode(update_data["theme_mode"])

        if "header_color" not in update_data:
            next_header_color = (
                get_default_header_color(next_theme_mode)
                if current_header_color == get_default_header_color(current_theme_mode)
                else current_header_color
            )
        if "background_color" not in update_data:
            next_background_color = (
                get_default_background_color(next_theme_mode)
                if current_background_color == get_default_background_color(current_theme_mode)
                else current_background_color
            )

        next_is_enabled = current_is_enabled
        if "is_enabled" in update_data and update_data["is_enabled"] is not None:
            next_is_enabled = bool(update_data["is_enabled"])

        return {
            "brand_name": next_brand_name,
            "primary_color": next_primary_color,
            "accent_color": next_accent_color,
            "sidebar_color": next_sidebar_color,
            "header_color": next_header_color,
            "background_color": next_background_color,
            "theme_mode": next_theme_mode,
            "is_enabled": next_is_enabled,
        }

    @staticmethod
    def _validate_logo_url_input(
        *,
        tenant_logo_url: str | None,
        payload: TenantBrandingUpdate,
    ) -> None:
        """Only allow logo references that already belong to the tenant media flow."""

        update_data = payload.model_dump(exclude_unset=True)
        if "logo_url" not in update_data:
            return

        if update_data["logo_url"] != tenant_logo_url:
            raise BadRequestException(
                detail=(
                    "logo_url must match the tenant's uploaded school logo. "
                    "Use the media upload endpoint to change the logo."
                )
            )

    @staticmethod
    async def get_admin_branding(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
    ) -> TenantBrandingResponse:
        """Return the tenant admin view of current branding settings."""

        tenant_id = TenantBrandingService._ensure_tenant_admin(actor)
        tenant = await TenantBrandingService._get_tenant_or_raise(
            db=db,
            tenant_id=tenant_id,
        )
        branding = await TenantBrandingRepository.get_by_tenant_id(
            db=db,
            tenant_id=tenant_id,
        )
        return TenantBrandingService._build_admin_response(
            tenant_id=tenant_id,
            logo_url=tenant.logo_url,
            branding=branding,
        )

    @staticmethod
    async def get_effective_tenant_branding(
        db: AsyncSession,
        *,
        actor: TenantActor | None = None,
        tenant_id: UUID | None = None,
    ) -> TenantBrandingEffectiveResponse:
        """Return the effective branding for authenticated tenant workspace users."""

        resolved_tenant_id = TenantBrandingService._resolve_effective_tenant_id(
            actor=actor,
            tenant_id=tenant_id,
        )

        cached_response = await get_cached_branding(resolved_tenant_id)
        if cached_response is not None:
            return TenantBrandingEffectiveResponse.model_validate(cached_response)

        tenant = await TenantBrandingService._get_tenant_or_raise(
            db=db,
            tenant_id=resolved_tenant_id,
        )
        branding = await TenantBrandingRepository.get_by_tenant_id(
            db=db,
            tenant_id=resolved_tenant_id,
        )
        response = TenantBrandingService._build_effective_branding_response(
            tenant=tenant,
            branding=branding,
        )
        await set_cached_branding(resolved_tenant_id, response)
        return response

    @staticmethod
    async def update_tenant_branding(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
        payload: TenantBrandingUpdate,
    ) -> TenantBrandingResponse:
        """Update tenant branding using safe backend-generated theme tokens."""

        tenant_id = TenantBrandingService._ensure_tenant_admin(actor)
        tenant = await TenantBrandingService._get_tenant_or_raise(
            db=db,
            tenant_id=tenant_id,
        )
        TenantBrandingService._validate_logo_url_input(
            tenant_logo_url=tenant.logo_url,
            payload=payload,
        )

        branding = await TenantBrandingRepository.get_by_tenant_id_for_update(
            db=db,
            tenant_id=tenant_id,
        )

        current_brand_name = branding.brand_name if branding is not None else DEFAULT_BRAND_NAME
        current_primary_color = branding.primary_color if branding is not None else DEFAULT_PRIMARY_COLOR
        current_accent_color = branding.accent_color if branding is not None else DEFAULT_ACCENT_COLOR
        current_sidebar_color = branding.sidebar_color if branding is not None else DEFAULT_SIDEBAR_COLOR
        current_theme_mode = branding.theme_mode if branding is not None else DEFAULT_THEME_MODE
        current_is_enabled = branding.is_enabled if branding is not None else False
        current_tokens = (
            TenantBrandingService._ensure_tokens(branding)
            if branding is not None
            else build_default_theme_tokens()
        )
        current_header_color = TenantBrandingService._resolve_header_color(
            theme_mode=current_theme_mode,
            tokens=current_tokens,
        )
        current_background_color = TenantBrandingService._resolve_background_color(
            theme_mode=current_theme_mode,
            tokens=current_tokens,
        )

        try:
            next_values = TenantBrandingService._normalize_update_values(
                current_brand_name=current_brand_name,
                current_primary_color=current_primary_color,
                current_accent_color=current_accent_color,
                current_sidebar_color=current_sidebar_color,
                current_header_color=current_header_color,
                current_background_color=current_background_color,
                current_theme_mode=current_theme_mode,
                current_is_enabled=current_is_enabled,
                payload=payload,
            )
            next_values["tokens"] = build_theme_tokens(
                primary_color=next_values["primary_color"],
                accent_color=next_values["accent_color"],
                sidebar_color=next_values["sidebar_color"],
                header_color=next_values["header_color"],
                background_color=next_values["background_color"],
                theme_mode=next_values["theme_mode"],
            )
        except ValueError as exc:
            raise BadRequestException(detail=str(exc)) from exc

        persisted_values = {
            "brand_name": next_values["brand_name"],
            "primary_color": next_values["primary_color"],
            "accent_color": next_values["accent_color"],
            "sidebar_color": next_values["sidebar_color"],
            "theme_mode": next_values["theme_mode"],
            "tokens": next_values["tokens"],
            "is_enabled": next_values["is_enabled"],
            "logo_url": tenant.logo_url,
            "updated_by_admin_id": actor.id,
        }

        if branding is None:
            if persisted_values == {
                **TenantBrandingService._default_branding_values(logo_url=tenant.logo_url),
                "updated_by_admin_id": actor.id,
            }:
                return TenantBrandingService._build_admin_response(
                    tenant_id=tenant_id,
                    logo_url=tenant.logo_url,
                    branding=None,
                )

            created_branding = await TenantBrandingRepository.create_branding(
                db=db,
                branding=TenantBranding(
                    tenant_id=tenant_id,
                    theme_version=1,
                    **persisted_values,
                ),
            )
            await db.commit()
            await invalidate_tenant_branding(tenant_id)
            return TenantBrandingService._build_admin_response(
                tenant_id=tenant_id,
                logo_url=tenant.logo_url,
                branding=created_branding,
            )

        has_changes = any(
            (
                branding.brand_name != persisted_values["brand_name"],
                branding.primary_color != persisted_values["primary_color"],
                branding.accent_color != persisted_values["accent_color"],
                branding.sidebar_color != persisted_values["sidebar_color"],
                branding.theme_mode != persisted_values["theme_mode"],
                branding.is_enabled != persisted_values["is_enabled"],
                current_tokens != persisted_values["tokens"],
                branding.logo_url != persisted_values["logo_url"],
                branding.updated_by_admin_id != persisted_values["updated_by_admin_id"],
            )
        )

        if not has_changes:
            return TenantBrandingService._build_admin_response(
                tenant_id=tenant_id,
                logo_url=tenant.logo_url,
                branding=branding,
            )

        updated_branding = await TenantBrandingRepository.update_branding(
            db=db,
            branding=branding,
            updates={
                **persisted_values,
                "theme_version": branding.theme_version + 1,
            },
        )
        await db.commit()
        await invalidate_tenant_branding(tenant_id)
        return TenantBrandingService._build_admin_response(
            tenant_id=tenant_id,
            logo_url=tenant.logo_url,
            branding=updated_branding,
        )

    @staticmethod
    async def reset_tenant_branding(
        db: AsyncSession,
        *,
        actor: TenantAdmin,
    ) -> TenantBrandingResetResponse:
        """Reset tenant branding back to default Weave values and disable it."""

        tenant_id = TenantBrandingService._ensure_tenant_admin(actor)
        tenant = await TenantBrandingService._get_tenant_or_raise(
            db=db,
            tenant_id=tenant_id,
        )

        reset_values = {
            **TenantBrandingService._default_branding_values(logo_url=tenant.logo_url),
            "updated_by_admin_id": actor.id,
        }

        branding = await TenantBrandingRepository.get_by_tenant_id_for_update(
            db=db,
            tenant_id=tenant_id,
        )

        if branding is None:
            branding = await TenantBrandingRepository.create_branding(
                db=db,
                branding=TenantBranding(
                    tenant_id=tenant_id,
                    theme_version=1,
                    **reset_values,
                ),
            )
        else:
            branding = await TenantBrandingRepository.reset_branding(
                db=db,
                branding=branding,
                defaults={
                    **reset_values,
                    "theme_version": branding.theme_version + 1,
                },
            )

        await db.commit()
        await invalidate_tenant_branding(tenant_id)

        return TenantBrandingResetResponse(
            branding=TenantBrandingService._build_admin_response(
                tenant_id=tenant_id,
                logo_url=tenant.logo_url,
                branding=branding,
            )
        )
