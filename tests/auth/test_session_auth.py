from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agro_mirai.api.session_auth import SESSION_LIFETIME, is_expired


def test_freshly_issued_session_not_expired():
    now = datetime.now(timezone.utc)
    assert is_expired(now.isoformat(), now=now) is False


def test_session_within_lifetime_not_expired():
    now = datetime.now(timezone.utc)
    issued = now - (SESSION_LIFETIME - timedelta(minutes=1))
    assert is_expired(issued.isoformat(), now=now) is False


def test_session_past_lifetime_is_expired():
    now = datetime.now(timezone.utc)
    issued = now - (SESSION_LIFETIME + timedelta(minutes=1))
    assert is_expired(issued.isoformat(), now=now) is True


def test_custom_lifetime_respected():
    now = datetime.now(timezone.utc)
    issued = now - timedelta(minutes=10)
    assert is_expired(issued.isoformat(), lifetime=timedelta(minutes=5), now=now) is True
    assert is_expired(issued.isoformat(), lifetime=timedelta(minutes=20), now=now) is False


def test_malformed_issued_at_treated_as_expired():
    assert is_expired("not-a-timestamp") is True
    assert is_expired("") is True


def test_naive_datetime_issued_at_assumed_utc():
    now = datetime.now(timezone.utc)
    naive_issued = (now - timedelta(minutes=1)).replace(tzinfo=None)
    assert is_expired(naive_issued.isoformat(), now=now) is False
