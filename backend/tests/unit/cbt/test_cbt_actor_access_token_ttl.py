from datetime import timedelta
from types import SimpleNamespace

from app.modules.cbt.auth import service


def test_actor_access_token_ttl_stays_relaxed_in_development(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(is_development=True),
    )

    assert service._actor_access_token_ttl() == timedelta(minutes=60)


def test_actor_access_token_ttl_is_tightened_in_production_like_envs(monkeypatch) -> None:
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(is_development=False),
    )

    assert service._actor_access_token_ttl() == timedelta(minutes=20)
