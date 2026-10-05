from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agro_mirai.api.app import create_app
from agro_mirai.api.session_auth import SESSION_LIFETIME, decode_token, is_expired, issue_session


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


def test_issue_session_returns_a_token_that_decodes_back():
    app = create_app({"TESTING": True})
    with app.test_request_context():
        token = issue_session("farmer-1", "farmer")
        data = decode_token(token)
        assert data["farmer_id"] == "farmer-1"
        assert data["role"] == "farmer"
        assert "issued_at" in data


def test_decode_token_rejects_garbage():
    app = create_app({"TESTING": True})
    with app.test_request_context():
        assert decode_token("not-a-real-token") is None
        assert decode_token("") is None


def test_decode_token_rejects_token_signed_with_a_different_key():
    app_a = create_app({"TESTING": True})
    app_a.secret_key = "key-a"
    app_b = create_app({"TESTING": True})
    app_b.secret_key = "key-b"
    with app_a.test_request_context():
        token = issue_session("farmer-1", "farmer")
    with app_b.test_request_context():
        assert decode_token(token) is None
