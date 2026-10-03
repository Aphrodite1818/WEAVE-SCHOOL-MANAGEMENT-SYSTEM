from pathlib import Path


def test_initial_baseline_includes_cbt_actor_authorization() -> None:
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20260911_initial_schema_initial_production_schema.py"
    )
    source = migration_path.read_text(encoding="utf-8")

    assert 'revision: str = "20260911_initial_schema"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = None' in source
    assert '"cbt_actor_authorizations"' in source
    assert '"cbt_actor_refresh_tokens"' in source
