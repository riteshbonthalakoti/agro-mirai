"""Module 19: /v2/auth/login has its own rate limit, tighter than and
on top of the general per-key limit (Module 16).
"""
from __future__ import annotations

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app(login_rate_limit: str):
    store = SQLiteDataStore(":memory:")
    return create_app(
        {
            "TESTING": True,
            "DATA_STORE": store,
            "API_KEY": "x",
            "FARMER_ID": "y",
            "LOGIN_RATE_LIMIT": login_rate_limit,
        }
    )


def test_login_attempts_within_limit_get_401_not_429():
    app = _app("3 per minute")
    client = app.test_client()
    for _ in range(3):
        resp = client.post(
            "/v2/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
        )
        assert resp.status_code == 401


def test_exceeding_login_limit_returns_429():
    app = _app("3 per minute")
    client = app.test_client()
    for _ in range(3):
        client.post("/v2/auth/login", json={"email": "nobody@example.com", "password": "x"})

    resp = client.post("/v2/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert resp.status_code == 429
    assert resp.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_login_rate_limit_is_independent_of_general_rate_limit():
    # A high general RATE_LIMIT should not save a caller from the
    # tighter LOGIN_RATE_LIMIT.
    store = SQLiteDataStore(":memory:")
    app = create_app(
        {
            "TESTING": True,
            "DATA_STORE": store,
            "API_KEY": "x",
            "FARMER_ID": "y",
            "RATE_LIMIT": "1000 per minute",
            "LOGIN_RATE_LIMIT": "2 per minute",
        }
    )
    client = app.test_client()
    for _ in range(2):
        client.post("/v2/auth/login", json={"email": "a@example.com", "password": "x"})
    resp = client.post("/v2/auth/login", json={"email": "a@example.com", "password": "x"})
    assert resp.status_code == 429
