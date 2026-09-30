from pathlib import Path


def test_cbt_actor_authorization_migration_follows_ai_quota_head() -> None:
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20260930_cbt_actor_auth_add_cbt_actor_authorization.py"
    )
    source = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "20260930_cbt_actor_auth"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = "20260930_cbt_ai_quota"' in source
    assert '"cbt_actor_authorizations"' in source
    assert '"cbt_actor_refresh_tokens"' in source
