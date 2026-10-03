from app.modules.cbt.auth.security import (
    ACTOR_ACCESS_TOKEN_PREFIX,
    ACTOR_REFRESH_TOKEN_PREFIX,
    generate_actor_access_token,
    generate_actor_refresh_token,
    hash_actor_token,
)


def test_actor_tokens_are_high_entropy_and_use_distinct_prefixes() -> None:
    access_a = generate_actor_access_token()
    access_b = generate_actor_access_token()
    refresh = generate_actor_refresh_token()

    assert access_a.startswith(ACTOR_ACCESS_TOKEN_PREFIX)
    assert refresh.startswith(ACTOR_REFRESH_TOKEN_PREFIX)
    assert access_a != access_b
    assert access_a != refresh


def test_actor_token_hash_is_deterministic_fixed_length_fingerprint() -> None:
    token = generate_actor_access_token()

    first = hash_actor_token(token)
    second = hash_actor_token(token)

    assert first == second
    assert len(first) == 64
    assert first != token
