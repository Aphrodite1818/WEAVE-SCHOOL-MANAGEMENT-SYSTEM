from __future__ import annotations

from app.config.settings import settings
from app.core.middleware.trusted_proxy import TrustedProxyHeadersMiddleware


def _scope(forwarded_for: str, *, client_ip: str = "10.0.0.5") -> dict:
    return {
        "type": "http",
        "client": (client_ip, 12345),
        "headers": [(b"x-forwarded-for", forwarded_for.encode("ascii"))],
    }


def test_single_trusted_proxy_uses_rightmost_forwarded_address(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)

    resolved = TrustedProxyHeadersMiddleware._resolved_ip(
        _scope("192.0.2.99, 203.0.113.9")
    )

    assert resolved == "203.0.113.9"


def test_multiple_trusted_hops_are_skipped_from_the_right(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 2)

    resolved = TrustedProxyHeadersMiddleware._resolved_ip(
        _scope("203.0.113.9, 198.51.100.10")
    )

    assert resolved == "203.0.113.9"


def test_untrusted_forwarding_header_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)

    resolved = TrustedProxyHeadersMiddleware._resolved_ip(
        _scope("203.0.113.9", client_ip="10.0.0.5")
    )

    assert resolved == "10.0.0.5"


def test_invalid_selected_forwarded_address_falls_back_to_socket_client(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)

    resolved = TrustedProxyHeadersMiddleware._resolved_ip(
        _scope("203.0.113.9, not-an-ip", client_ip="10.0.0.5")
    )

    assert resolved == "10.0.0.5"
