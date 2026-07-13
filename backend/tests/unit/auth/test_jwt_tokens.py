from importlib.metadata import packages_distributions

from jose import JWTError, jwt
import pytest

from app.config.security import create_access_token
from app.config.settings import settings


def test_jose_namespace_is_provided_by_python_jose() -> None:
    owners = packages_distributions().get("jose", [])

    assert "python-jose" in owners
    assert "jose" not in owners


def test_create_access_token() -> None:
    token = create_access_token({"sub": "user-id-123"})

    assert isinstance(token, str)
    assert token
    assert len(token) > 0
    assert token.count(".") == 2


def test_create_access_token_contains_subject_claims() -> None:
    token = create_access_token({"sub": "user-id-123"})

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert payload["sub"] == "user-id-123"


def test_create_access_token_contains_expiration_claim() -> None:
    token = create_access_token({"sub": "user-123-id"})

    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )

    assert "exp" in payload


@pytest.fixture()
def access_token() -> str:
    return create_access_token({"sub": "user-123-id"})


def test_wrong_signature_is_not_allowed(access_token: str) -> None:
    with pytest.raises(JWTError):
        jwt.decode(
            access_token,
            "HFJFFREAWNIOKHOKPKPKPLoooooooooooog",
            algorithms=[settings.ALGORITHM],
        )
