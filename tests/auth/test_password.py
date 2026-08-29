from __future__ import annotations

from agro_mirai.auth.password import hash_password, verify_password


def test_hash_is_not_plaintext():
    h = hash_password("Sup3rSecret!")
    assert h != "Sup3rSecret!"
    assert h.startswith("$2b$") or h.startswith("$2a$")


def test_verify_correct_password_true():
    h = hash_password("Sup3rSecret!")
    assert verify_password("Sup3rSecret!", h) is True


def test_verify_wrong_password_false():
    h = hash_password("Sup3rSecret!")
    assert verify_password("wrong-password", h) is False


def test_hash_is_salted_differs_each_call():
    h1 = hash_password("Sup3rSecret!")
    h2 = hash_password("Sup3rSecret!")
    assert h1 != h2
    assert verify_password("Sup3rSecret!", h1)
    assert verify_password("Sup3rSecret!", h2)


def test_verify_against_missing_hash_false():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "") is False


def test_verify_against_malformed_hash_false():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False
