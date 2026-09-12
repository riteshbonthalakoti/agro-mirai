"""Module 27: /v2/auth/request-otp has its own rate limit, tighter than
and on top of the general per-key limit (Module 16). Renamed from
LOGIN_RATE_LIMIT/test_login_rate_limit.py's original email+password
login test (Module 19) — same limiter mechanism, now guarding OTP
requests instead of password login attempts.
"""
from __future__ import annotations

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app(otp_rate_limit: str):
    store = SQLiteDataStore(":memory:")
    return create_app(
        {
            "TESTING": True,
            "DATA_STORE": store,
            "API_KEY": "x",
            "FARMER_ID": "y",
            "OTP_RATE_LIMIT": otp_rate_limit,
        }
    )


def _request_otp(client, phone="+919000000099"):
    return client.post(
        "/v2/auth/request-otp",
        json={"phone": phone, "name": "F", "preferred_language": "en"},
    )


def test_otp_requests_within_limit_get_200_not_429():
    app = _app("3 per minute")
    client = app.test_client()
    for _ in range(3):
        resp = _request_otp(client)
        assert resp.status_code == 200


def test_exceeding_otp_request_limit_returns_429():
    app = _app("3 per minute")
    client = app.test_client()
    for _ in range(3):
        _request_otp(client)

    resp = _request_otp(client)
    assert resp.status_code == 429
    assert resp.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_otp_rate_limit_is_independent_of_general_rate_limit():
    # A high general RATE_LIMIT should not save a caller from the
    # tighter OTP_RATE_LIMIT.
    store = SQLiteDataStore(":memory:")
    app = create_app(
        {
            "TESTING": True,
            "DATA_STORE": store,
            "API_KEY": "x",
            "FARMER_ID": "y",
            "RATE_LIMIT": "1000 per minute",
            "OTP_RATE_LIMIT": "2 per minute",
        }
    )
    client = app.test_client()
    for _ in range(2):
        _request_otp(client)
    resp = _request_otp(client)
    assert resp.status_code == 429
