"""Per-API-key rate limiting: a configurable requests/minute ceiling that
returns a clean 429 (not a crash) once exceeded.
"""
from __future__ import annotations

from agro_mirai.api.app import create_app
from conftest import API_KEY, FARMER_ID, _mock_store


def _make_app(rate_limit: str):
    return create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": FARMER_ID,
            "TESTING": True,
            "DATA_STORE": _mock_store(),
            "RATE_LIMIT": rate_limit,
        }
    )


def test_requests_within_limit_succeed():
    app = _make_app("3 per minute")
    client = app.test_client()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    for _ in range(3):
        resp = client.get("/farmers/me", headers=headers)
        assert resp.status_code == 200


def test_exceeding_limit_returns_429_not_a_crash():
    app = _make_app("3 per minute")
    client = app.test_client()
    headers = {"Authorization": f"Bearer {API_KEY}"}
    for _ in range(3):
        client.get("/farmers/me", headers=headers)

    resp = client.get("/farmers/me", headers=headers)
    assert resp.status_code == 429
    body = resp.get_json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_rate_limit_is_keyed_per_api_key_not_shared():
    app = _make_app("1 per minute")
    client = app.test_client()
    client.get("/farmers/me", headers={"Authorization": f"Bearer {API_KEY}"})
    resp = client.get("/farmers/me", headers={"Authorization": "Bearer wrong-key"})
    # Unauthenticated/other-key traffic isn't blocked by this key's bucket
    # (it still gets its own 401, not a 429 from the first key's usage).
    assert resp.status_code == 401


def test_health_endpoint_is_not_rate_limited():
    app = _make_app("1 per minute")
    client = app.test_client()
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200
