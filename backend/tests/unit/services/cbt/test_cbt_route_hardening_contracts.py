from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[4]


def _source(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def test_public_pairing_route_has_abuse_protection_and_usage_invalidation() -> None:
    source = _source("app/modules/cbt/pairing/router.py")

    assert "CBTPairingRateLimiter.check" in source
    assert "invalidate_tenant_subscription_state" in source


def test_server_inventory_read_is_not_feature_gated() -> None:
    source = _source("app/modules/cbt/pairing/router.py")
    list_block = source.split("async def list_cbt_servers", 1)[1].split("@router.get", 1)[0]

    assert "CBTServerRepository.list_for_tenant" in list_block
    assert "ensure_feature_enabled" not in list_block


def test_reactivation_is_feature_gated_but_revocation_invalidates_usage() -> None:
    source = _source("app/modules/cbt/pairing/router.py")
    reactivate_block = source.split("async def reactivate_cbt_server", 1)[1].split("@router.post", 1)[0]
    revoke_block = source.split("async def revoke_cbt_server", 1)[1]

    assert "ensure_feature_enabled" in reactivate_block
    assert "invalidate_tenant_subscription_state" in revoke_block
