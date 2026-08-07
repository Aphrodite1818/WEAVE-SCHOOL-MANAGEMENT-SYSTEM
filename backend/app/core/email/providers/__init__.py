"""Concrete email provider adapters."""

from app.core.email.providers.base import EmailProviderAdapter
from app.core.email.providers.legacy import LegacyEmailProvider
from app.core.email.providers.resend import ResendEmailProvider
from app.core.email.providers.ses import SESEmailProvider


__all__ = [
    "EmailProviderAdapter",
    "LegacyEmailProvider",
    "ResendEmailProvider",
    "SESEmailProvider",
]
