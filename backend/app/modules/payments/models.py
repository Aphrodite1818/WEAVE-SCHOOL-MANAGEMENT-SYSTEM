"""Shared payment model exports.

The webhook event table already exists in the subscription schema history. It is
re-exported here so payment infrastructure owns its usage without redefining the
same SQLAlchemy table during this refactor.
"""

from app.modules.subscriptions.models import PaymentWebhookEvent

__all__ = ["PaymentWebhookEvent"]
