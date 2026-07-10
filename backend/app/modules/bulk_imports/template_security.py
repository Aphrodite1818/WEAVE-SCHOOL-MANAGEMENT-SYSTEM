# ===================================== #
#   bulk_imports_template_security.py   #
# ===================================== #

"""Signing helpers for bulk import templates."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from uuid import UUID

from app.config.settings import settings
from app.modules.bulk_imports.models import ImportResourceType


def normalize_header(header: str) -> str:
    """Normalize one template header for stable hashing."""

    return str(header).strip().lower()


def build_headers_hash(headers: Iterable[str]) -> str:
    """Build a stable hash for ordered template headers."""

    canonical_headers = [normalize_header(header) for header in headers]
    payload = "|".join(canonical_headers)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_template_signature_payload(
    *,
    tenant_id: UUID,
    resource_type: ImportResourceType,
    template_version: str,
    headers_hash: str,
) -> str:
    """Build the signed payload for one tenant-scoped import template."""

    return "|".join(
        [
            str(tenant_id),
            resource_type.value,
            template_version,
            headers_hash,
        ]
    )


def sign_template_payload(payload: str) -> str:
    """Create an HMAC signature for a template payload."""

    secret = settings.SECRET_KEY
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_template_signature(
    *,
    tenant_id: UUID,
    resource_type: ImportResourceType,
    template_version: str,
    headers_hash: str,
    signature: str,
) -> bool:
    """Verify a submitted template signature."""

    payload = build_template_signature_payload(
        tenant_id=tenant_id,
        resource_type=resource_type,
        template_version=template_version,
        headers_hash=headers_hash,
    )
    expected_signature = sign_template_payload(payload)

    return hmac.compare_digest(expected_signature, str(signature))
