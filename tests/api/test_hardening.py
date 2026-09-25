"""Module 43 security pass: secret key, request size cap, tabular service token."""
from __future__ import annotations

import io

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _cfg():
    return {"TESTING": True, "DATA_STORE": SQLiteDataStore(":memory:"), "API_KEY": "x", "FARMER_ID": "y"}


def test_no_secret_key_env_gives_a_random_key_not_the_public_default(monkeypatch):
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    a, b = create_app(_cfg()), create_app(_cfg())
    assert a.secret_key != "dev-only-secret-not-for-prod"
    assert len(a.secret_key) >= 32 and a.secret_key != b.secret_key


def test_secret_key_env_is_used_when_set(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "from-env-123")
    assert create_app(_cfg()).secret_key == "from-env-123"


def test_oversized_body_is_rejected_with_json_413():
    app = create_app(_cfg())
    big = io.BytesIO(b"x" * (21 * 1024 * 1024))
    resp = app.test_client().post("/v2/auth/request-otp", data=big, content_type="application/json")
    assert resp.status_code == 413
    assert "error" in resp.get_json()
