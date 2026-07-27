from app.config.security import hash_password, verify_password


def test_hash_password_returns_different_value_from_plain_password():
    password = "Password123gotyousucker"
    result = hash_password(password)
    assert result != password


def test_verify_password_returns_true_for_correct_password():
    password = "Password123gotyousucker"
    verified = verify_password(password, hash_password(password))
    assert verified is True


def test_verify_password_returns_false_for_wrong_password():
    correct_password = "Password123gotyousucker"
    wrong_password = "Password124gotyousucker"

    assert verify_password(wrong_password, hash_password(correct_password)) is False
