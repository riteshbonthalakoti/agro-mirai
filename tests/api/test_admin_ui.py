"""Module 19/26: server-rendered /admin dashboard (Jinja2, ADR 0013
pattern). Module 26: login posts email/password to Flask, which makes a
server-side Supabase Auth password-grant call (routes/admin_ui.py) — here
that call is mocked (no live network dependency in the main test suite;
a real end-to-end round trip against the live Supabase project was
verified manually, see decisions/0022's handoff notes), returning a JWT
minted the same way conftest.py's make_jwt does, so the rest of the
request goes through real verification.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

from conftest import make_jwt

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)

_KNOWN_USERS = {
    ("farmer@example.com", "Sup3rSecret1"): ("11111111-0000-4000-8000-000000000001", "farmer"),
    ("admin@example.com", "Sup3rSecret1"): ("22222222-0000-4000-8000-000000000002", "admin"),
}


def _fake_create_client(url, key):
    client = MagicMock()

    def _sign_in(creds):
        key_tuple = (creds["email"], creds["password"])
        if key_tuple not in _KNOWN_USERS:
            raise Exception("Invalid login credentials")
        user_id, role = _KNOWN_USERS[key_tuple]
        token = make_jwt(user_id, role=role, email=creds["email"])
        return SimpleNamespace(session=SimpleNamespace(access_token=token))

    client.auth.sign_in_with_password.side_effect = _sign_in
    return client


@pytest.fixture(autouse=True)
def _mock_supabase_client(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-anon-key")
    monkeypatch.setattr("supabase.create_client", _fake_create_client)
    # jwt_auth would otherwise try a real JWKS fetch against the fake
    # SUPABASE_URL above (needed only to satisfy admin_ui's own
    # "is Supabase configured" check) — force the HS256 test-secret path
    # (see conftest.py's _supabase_jwt_secret) instead of a network call.
    monkeypatch.setattr("agro_mirai.api.jwt_auth._jwks_client", lambda: None)


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def test_admin_dashboard_redirects_when_not_logged_in():
    app, client = _app_and_client()
    resp = client.get("/admin", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Admin login" in resp.data


def test_admin_login_rejects_wrong_password():
    app, client = _app_and_client()
    resp = client.post(
        "/admin/login",
        data={"email": "farmer@example.com", "password": "WrongPass1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin login" in resp.data


def test_admin_login_rejects_non_admin_account():
    app, client = _app_and_client()
    resp = client.post(
        "/admin/login",
        data={"email": "farmer@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin login" in resp.data  # bounced back, not the dashboard


def test_admin_login_and_dashboard_render():
    app, client = _app_and_client()
    resp = client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Admin dashboard" in resp.data
    assert b"admin@example.com" in resp.data


def test_admin_logout_clears_session():
    app, client = _app_and_client()
    client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "Sup3rSecret1"},
        follow_redirects=True,
    )
    client.post("/admin/logout")
    resp = client.get("/admin", follow_redirects=True)
    assert b"Admin login" in resp.data
