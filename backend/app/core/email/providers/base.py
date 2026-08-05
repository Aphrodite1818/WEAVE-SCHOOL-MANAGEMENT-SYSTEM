"""Shared provider interface for email delivery adapters."""




from abc import ABC, abstractmethod
from app.core.email.contracts import(
    EmailRequest,
    EmailDeliveryResult,
    EmailRoute
)
from app.core.email.enums import EmailProvider


class EmailProviderAdapter(ABC):
    """Base interface for email delivery providers."""



    @property
    @abstractmethod
    def provider(self) -> EmailProvider:
        """Return the provider represented by the Base Adapter (e.g. EmailProvider.SES)
        """



    @abstractmethod
    async def send(
        self,
        *,
        request : EmailRequest,
        route : EmailRoute,
    )-> EmailDeliveryResult:
        """Submit one email to the external delivery provider """