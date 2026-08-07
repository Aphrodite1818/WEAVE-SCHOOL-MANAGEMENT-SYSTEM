from app.config.security import (
    hash_auth_secret,
    hash_otp,
    verify_auth_secret,
    verify_otp,
)


def test_hash_6_digit_otp():
    otp = "123456"
    hashed = hash_otp(otp)
    assert hashed == hashed
    assert hashed != otp
    assert hashed.startswith("otp_sha256$")


def test_verify_otp_returns_true_for_correct_otp():
    otp = "12345"
    hashed_otp = hash_otp(otp)

    assert verify_otp(otp, hashed_otp) == True


def test_verify_otp_returns_false_for_wrong_otp():
    correct_otp = "12345"
    wrong_otp = "12346"
    hashed = hash_otp(correct_otp)

    assert verify_otp(wrong_otp, hashed) is False


def test_hahs_auth_secret_returns_hashed_value():
    secret = "invite-secret-token"
    hashed_secret = hash_auth_secret(secret)

    assert hashed_secret != secret
    assert hashed_secret.startswith("auth_sha256$")


def test_verify_auth_secret_returns_true_for_correct_secret() -> None:
    secret = "invite-secret-token"
    hashed_secret = hash_auth_secret(secret)

    assert verify_auth_secret(secret, hashed_secret) is True


def test_verify_auth_secret_returns_false_for_wrong_secret() -> None:
    secret = "invite-secret-token"
    wrong_secret = "wrong-secret-token"
    hashed_secret = hash_auth_secret(secret)

    assert verify_auth_secret(wrong_secret, hashed_secret) is False


def test_verify_auth_secret_supports_otp_hashes() -> None:
    otp = "123456"
    hashed_otp = hash_otp(otp)

    assert verify_auth_secret(otp, hashed_otp) is True
