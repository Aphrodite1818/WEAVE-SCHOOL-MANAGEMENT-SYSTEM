"""Application-facing email service and provider selection boundary."""

from __future__ import annotations

from collections.abc import Mapping

from app.config.settings import Settings, settings
from app.core.email.contracts import EmailDeliveryResult, EmailRequest
from app.core.email.enums import EmailProvider
from app.core.email.exceptions import EmailConfigurationError
from app.core.email.providers.base import EmailProviderAdapter
from app.core.email.providers.legacy import LegacyEmailProvider
from app.core.email.providers.ses import SESEmailProvider


class EmailService:
    """Select the configured provider and deliver email requests."""

    def __init__(
        self,
        *,
        config: Settings = settings,
        providers: Mapping[EmailProvider, EmailProviderAdapter] | None = None,
    ) -> None:
        self._config = config
        self._providers = dict(providers or {})

    # ==========================================================
    # PROVIDER RESOLUTION HELPERS
    # ==========================================================

    def _resolve_provider_type(self) -> EmailProvider:
        """Return the configured provider as a validated enum value."""

        try:
            return EmailProvider(self._config.EMAIL_PROVIDER)
        except ValueError as exc:
            raise EmailConfigurationError(
                f"Unsupported email provider: {self._config.EMAIL_PROVIDER!r}."
            ) from exc

    def _build_provider(
        self,
        provider_type: EmailProvider,
    ) -> EmailProviderAdapter:
        """Construct one provider adapter for the active configuration."""

        if provider_type == EmailProvider.LEGACY:
            return LegacyEmailProvider(config=self._config)

        if provider_type == EmailProvider.SES:
            return SESEmailProvider(config=self._config)

        raise EmailConfigurationError(
            f"No email provider adapter exists for {provider_type.value!r}."
        )

    def _get_provider(
        self,
        provider_type: EmailProvider,
    ) -> EmailProviderAdapter:
        """Return a cached or newly constructed provider adapter."""

        provider = self._providers.get(provider_type)

        if provider is None:
            provider = self._build_provider(provider_type)
            self._providers[provider_type] = provider

        if provider.provider != provider_type:
            raise EmailConfigurationError(
                "Email provider registry contains an adapter under the "
                f"wrong key: expected {provider_type.value!r}, got "
                f"{provider.provider.value!r}."
            )

        return provider

    # ==========================================================
    # PUBLIC ENTRY POINT
    # ==========================================================

    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        """Deliver one request through the configured provider."""

        provider_type = self._resolve_provider_type()
        provider = self._get_provider(provider_type)

        return await provider.send(request=request)


email_service = EmailService()
