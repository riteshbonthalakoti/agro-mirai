from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agro_mirai.auth.otp import OTP_TTL, OtpStore


def test_issued_code_is_six_digits():
    store = OtpStore()
    code = store.issue("+919000000001")
    assert len(code) == 6
    assert code.isdigit()


def test_correct_code_verifies_once_then_fails():
    store = OtpStore()
    code = store.issue("+919000000002")
    assert store.verify("+919000000002", code) is True
    # One-shot: the same code cannot be replayed.
    assert store.verify("+919000000002", code) is False


def test_wrong_code_fails_without_consuming_pending_otp(monkeypatch):
    monkeypatch.setattr("agro_mirai.auth.otp.secrets.randbelow", lambda _n: 123456)

    store = OtpStore()
    code = store.issue("+919000000003")
    assert store.verify("+919000000003", "654321") is False
    # The real code still works afterward -- a wrong guess doesn't burn it.
    assert store.verify("+919000000003", code) is True


def test_expired_code_fails():
    store = OtpStore()
    now = datetime.now(timezone.utc)
    code = store.issue("+919000000004", now=now)
    later = now + OTP_TTL + timedelta(seconds=1)
    assert store.verify("+919000000004", code, now=later) is False


def test_verify_unknown_phone_fails():
    store = OtpStore()
    assert store.verify("+919000000005", "123456") is False


def test_requesting_a_new_code_invalidates_the_old_one(monkeypatch):
    codes = iter([111111, 222222])
    monkeypatch.setattr("agro_mirai.auth.otp.secrets.randbelow", lambda _n: next(codes))

    store = OtpStore()
    old_code = store.issue("+919000000006")
    new_code = store.issue("+919000000006")
    assert old_code == "111111"
    assert new_code == "222222"
    assert store.verify("+919000000006", old_code) is False
    assert store.verify("+919000000006", new_code) is True


def test_too_many_wrong_attempts_locks_out_even_the_correct_code(monkeypatch):
    from agro_mirai.auth.otp import MAX_VERIFY_ATTEMPTS

    monkeypatch.setattr("agro_mirai.auth.otp.secrets.randbelow", lambda _n: 123456)

    store = OtpStore()
    code = store.issue("+919000000009")
    for _ in range(MAX_VERIFY_ATTEMPTS):
        assert store.verify("+919000000009", "000000") is False
    # Attempts exhausted -- even the correct code no longer works.
    assert store.verify("+919000000009", code) is False
