"""Module 19 integration: register -> login -> access own data -> CANNOT
access another farmer's data -> logout -> session invalidated. Real
Flask test client, real SQLiteDataStore (:memory:), real session
cookies (no mocked auth) — this is the genuine cross-tenant isolation
proof the module spec asks for, not just a happy-path test.
"""
from __future__ import annotations

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
import pytest

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)


def _app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


def _register(client, email, password="Sup3rSecret1", name="Farmer"):
    return client.post(
        "/v2/auth/register",
        json={"email": email, "password": password, "name": name, "preferred_language": "en"},
    )


def test_register_creates_farmer_without_leaking_hash():
    app = _app()
    client = app.test_client()
    resp = _register(client, "alice@example.com")
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body


def test_register_rejects_weak_password():
    app = _app()
    client = app.test_client()
    resp = _register(client, "weak@example.com", password="short")
    assert resp.status_code == 400


def test_register_rejects_duplicate_email():
    app = _app()
    client = app.test_client()
    _register(client, "dup@example.com")
    resp = _register(client, "dup@example.com")
    assert resp.status_code == 409


def test_login_wrong_password_401():
    app = _app()
    client = app.test_client()
    _register(client, "bob@example.com", password="Sup3rSecret1")
    resp = client.post(
        "/v2/auth/login", json={"email": "bob@example.com", "password": "WrongPass1"}
    )
    assert resp.status_code == 401


def test_full_cross_tenant_isolation_flow():
    app = _app()
    client = app.test_client()

    # Register two farmers.
    r1 = _register(client, "farmer1@example.com", password="Sup3rSecret1")
    r2 = _register(client, "farmer2@example.com", password="Sup3rSecret2")
    assert r1.status_code == 201 and r2.status_code == 201

    # --- Farmer 1 logs in, creates a field, can read it back.
    login1 = client.post(
        "/v2/auth/login", json={"email": "farmer1@example.com", "password": "Sup3rSecret1"}
    )
    assert login1.status_code == 200

    create = client.post(
        "/v2/fields",
        json={"name": "F1 Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert create.status_code == 201
    field_id = create.get_json()["id"]

    get_own = client.get(f"/v2/fields/{field_id}")
    assert get_own.status_code == 200
    assert get_own.get_json()["id"] == field_id

    list_own = client.get("/v2/fields")
    assert list_own.status_code == 200
    assert len(list_own.get_json()["items"]) == 1

    # Log farmer 1 out before farmer 2 logs in — Flask test client keeps
    # a single cookie jar, sessions are mutually exclusive here.
    logout1 = client.post("/v2/auth/logout")
    assert logout1.status_code == 200

    # A request after logout with no new login is rejected.
    denied_after_logout = client.get("/v2/fields")
    assert denied_after_logout.status_code == 401

    # --- Farmer 2 logs in: CANNOT see or fetch farmer 1's field.
    login2 = client.post(
        "/v2/auth/login", json={"email": "farmer2@example.com", "password": "Sup3rSecret2"}
    )
    assert login2.status_code == 200

    list_other = client.get("/v2/fields")
    assert list_other.status_code == 200
    assert list_other.get_json()["items"] == []

    get_other = client.get(f"/v2/fields/{field_id}")
    assert get_other.status_code == 404  # not owned -> not found, not leaked

    # --- Logout invalidates the session for good.
    logout2 = client.post("/v2/auth/logout")
    assert logout2.status_code == 200
    denied = client.get("/v2/fields")
    assert denied.status_code == 401


def test_unauthenticated_v2_request_401():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/fields")
    assert resp.status_code == 401


def test_v2_farmers_me_matches_logged_in_farmer():
    app = _app()
    client = app.test_client()
    _register(client, "carol@example.com", password="Sup3rSecret1")
    client.post("/v2/auth/login", json={"email": "carol@example.com", "password": "Sup3rSecret1"})
    resp = client.get("/v2/farmers/me")
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "carol@example.com"
