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
    from datetime import datetime, timedelta, timezone

    t0 = datetime.now(timezone.utc)
    later = t0 + timedelta(seconds=30)  # past the resend cooldown
    old_code = store.issue("+919000000006", now=t0)
    new_code = store.issue("+919000000006", now=later)
    assert old_code == "111111"
    assert new_code == "222222"
    assert store.verify("+919000000006", old_code, now=later) is False
    assert store.verify("+919000000006", new_code, now=later) is True


def test_too_many_wrong_attempts_locks_out_even_the_correct_code(monkeypatch):
    from agro_mirai.auth.otp import MAX_VERIFY_ATTEMPTS

    monkeypatch.setattr("agro_mirai.auth.otp.secrets.randbelow", lambda _n: 123456)

    store = OtpStore()
    code = store.issue("+919000000009")
    for _ in range(MAX_VERIFY_ATTEMPTS):
        assert store.verify("+919000000009", "000000") is False
    # Attempts exhausted -- even the correct code no longer works.
    assert store.verify("+919000000009", code) is False


def test_resending_too_soon_is_refused():
    from datetime import datetime, timedelta, timezone

    import pytest

    from agro_mirai.auth.otp import ResendTooSoon

    store = OtpStore()
    t0 = datetime.now(timezone.utc)
    store.issue("+919000000007", now=t0)
    with pytest.raises(ResendTooSoon):
        store.issue("+919000000007", now=t0 + timedelta(seconds=3))


def test_signup_details_come_back_only_on_a_correct_code():
    store = OtpStore()
    code = store.issue("+919000000008", signup={"name": "Asha"})
    assert store.verify_with_signup("+919000000008", "000000") == (False, None)
    assert store.verify_with_signup("+919000000008", code) == (True, {"name": "Asha"})
    assert store.verify_with_signup("+919000000008", code) == (False, None)


def test_pending_codes_are_capped():
    from datetime import datetime, timezone

    from agro_mirai.auth import otp

    store = OtpStore()
    now = datetime.now(timezone.utc)
    for i in range(otp.MAX_PENDING + 50):
        store.issue(f"+91900{i:07d}", now=now)
    assert len(store._pending) <= otp.MAX_PENDING
