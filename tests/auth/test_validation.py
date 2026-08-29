from __future__ import annotations

import pytest

from agro_mirai.auth.validation import validate_email, validate_name, validate_password_strength


@pytest.mark.parametrize("email", ["a@b.com", "ritesh@dharanova.com", "x.y+z@sub.domain.co"])
def test_valid_emails_pass(email):
    validate_email(email)  # no raise


@pytest.mark.parametrize("email", ["", "not-an-email", "a@b", "@b.com", "a@.com", None])
def test_invalid_emails_raise(email):
    with pytest.raises(ValueError):
        validate_email(email)


@pytest.mark.parametrize(
    "password", ["Sup3rSecret!", "Abcdefg1", "Zz9zzzzz"]
)
def test_strong_passwords_pass(password):
    validate_password_strength(password)  # no raise


@pytest.mark.parametrize(
    "password",
    [
        "a",  # too short, the module spec's explicit "don't accept 'a'" case
        "short1A",  # < 8 chars
        "alllowercase1",  # no uppercase
        "ALLUPPERCASE1",  # no lowercase
        "NoDigitsHere",  # no digit
        "",
        None,
    ],
)
def test_weak_passwords_raise(password):
    with pytest.raises(ValueError):
        validate_password_strength(password)


def test_validate_name_requires_non_blank():
    validate_name("Ravi Kumar")
    with pytest.raises(ValueError):
        validate_name("")
    with pytest.raises(ValueError):
        validate_name("   ")
