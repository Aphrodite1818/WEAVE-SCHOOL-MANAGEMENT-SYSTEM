"""Concrete email provider adapters."""



from app.core.email.providers.base import EmailProviderAdapter

__all__ = [
    "EmailProviderAdapter",
    "LegacyEmailProvider"
]