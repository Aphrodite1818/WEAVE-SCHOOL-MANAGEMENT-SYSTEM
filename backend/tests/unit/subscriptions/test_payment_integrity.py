from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.config.settings import settings
from app.modules.subscriptions.payment_integrity import (
    _transaction_integrity_failures,
)
from app.modules.subscriptions.subscription_enums import BillingInterval
from app.tenant_management.models import SubscriptionPlan


def build_transaction() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        reference="sub_test_reference",
        amount_kobo=1_500_000,
        currency="NGN",
        plan_code=SubscriptionPlan.PLUS,
        billing_interval=BillingInterval.MONTHLY,
    )


def build_provider_data(transaction: SimpleNamespace) -> dict:
    return {
        "status": "success",
        "reference": transaction.reference,
        "amount": transaction.amount_kobo,
        "currency": transaction.currency,
        "plan": {"plan_code": settings.PAYSTACK_PLUS_MONTHLY_PLAN_CODE},
        "metadata": {
            "tenant_id": str(transaction.tenant_id),
            "plan_code": "plus",
            "billing_interval": "monthly",
            "transaction_id": str(transaction.id),
        },
    }


def test_payment_integrity_accepts_exact_checkout(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_plus")
    transaction = build_transaction()
    data = build_provider_data(transaction)

    assert _transaction_integrity_failures(transaction, data) == []


def test_payment_integrity_rejects_underpayment(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_plus")
    transaction = build_transaction()
    data = build_provider_data(transaction)
    data["amount"] = transaction.amount_kobo - 100

    assert "amount" in _transaction_integrity_failures(transaction, data)


def test_payment_integrity_rejects_wrong_metadata_and_currency(monkeypatch):
    monkeypatch.setattr(settings, "PAYSTACK_PLUS_MONTHLY_PLAN_CODE", "PLN_plus")
    transaction = build_transaction()
    data = build_provider_data(transaction)
    data["currency"] = "USD"
    data["metadata"]["tenant_id"] = str(uuid.uuid4())
    data["metadata"]["plan_code"] = "professional"

    failures = _transaction_integrity_failures(transaction, data)

    assert "currency" in failures
    assert "tenant_id" in failures
    assert "plan_code" in failures
