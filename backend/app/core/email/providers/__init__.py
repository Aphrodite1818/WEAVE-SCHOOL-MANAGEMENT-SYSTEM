"""Concrete email provider adapters."""



from app.core.email.providers.base import EmailProviderAdapter
from app.core.email.providers import LegacyEmailProvider



__all__ = [
    "EmailProviderAdapter",
    "LegacyEmailProvider"
]