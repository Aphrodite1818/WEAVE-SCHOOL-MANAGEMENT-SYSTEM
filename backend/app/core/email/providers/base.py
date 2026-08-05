"""Shared provider interface for email delivery adapters."""

from abc import ABC, abstractmethod

from app.core.email.contracts import EmailDeliveryResult, EmailRequest
from app.core.email.enums import EmailProvider


class EmailProviderAdapter(ABC):
    """Base interface for email delivery providers."""

    @property
    @abstractmethod
    def provider(self) -> EmailProvider:
        """Return the provider represented by this adapter."""

    @abstractmethod
    async def send(
        self,
        *,
        request: EmailRequest,
    ) -> EmailDeliveryResult:
        """Submit one email to the external delivery provider."""
