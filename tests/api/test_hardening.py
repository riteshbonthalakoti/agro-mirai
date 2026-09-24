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


def _tabular_client(monkeypatch, token):
    import importlib.util
    import sys
    from pathlib import Path

    if token is None:
        monkeypatch.delenv("TABULAR_SERVICE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TABULAR_SERVICE_TOKEN", token)
    path = Path(__file__).resolve().parents[2] / "services" / "tabular-ml" / "app.py"
    spec = importlib.util.spec_from_file_location("tabular_app_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["tabular_app_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod.create_app().test_client()


def test_tabular_service_open_when_no_token_configured(monkeypatch):
    c = _tabular_client(monkeypatch, None)
    assert c.post("/predict/crop", json={}).status_code != 401


def test_tabular_service_requires_token_when_configured(monkeypatch):
    c = _tabular_client(monkeypatch, "s3cret")
    assert c.post("/predict/crop", json={}).status_code == 401
    assert c.post("/predict/crop", json={}, headers={"X-Service-Token": "wrong"}).status_code == 401
    assert c.post("/predict/crop", json={}, headers={"X-Service-Token": "s3cret"}).status_code != 401
    assert c.get("/health").status_code == 200  # Render health checks stay open
