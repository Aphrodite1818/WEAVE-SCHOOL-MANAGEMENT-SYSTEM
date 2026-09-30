import app.models  # noqa: F401
from app.modules.cbt.auth.models import CBTActorAuthorization, CBTActorRefreshToken
from app.shared.base_model import Base


def test_cbt_actor_authorization_models_are_registered_in_global_metadata() -> None:
    table_names = {table.name for table in Base.metadata.tables.values()}

    assert "cbt_actor_authorizations" in table_names
    assert "cbt_actor_refresh_tokens" in table_names


def test_authorization_keeps_only_one_current_access_token_hash() -> None:
    table = CBTActorAuthorization.__table__

    assert table.c.access_token_hash.unique is True
    assert table.c.access_token_hash.nullable is False
    assert table.c.access_token_expires_at.nullable is False
    assert table.c.absolute_expires_at.nullable is False
    assert table.c.revoked_at.nullable is True


def test_refresh_token_model_retains_rotation_history() -> None:
    table = CBTActorRefreshToken.__table__

    assert table.c.token_hash.unique is True
    assert table.c.authorization_id.nullable is False
    assert table.c.consumed_at.nullable is True
    assert table.c.reuse_detected_at.nullable is True
    assert table.c.replaced_by_token_id.nullable is True
