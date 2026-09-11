"""Module 26 integration: Supabase-JWT-authenticated access -> profile
auto-provisioning -> own-data access -> CANNOT access another farmer's
data -> invalid/expired token rejected. Real Flask test client, real
SQLiteDataStore (:memory:), real JWT verification (jwt_auth.verify_token)
through the HS256 test-secret path (see conftest.py's make_jwt/
jwt_headers) — no mocked auth decorator, no mocked DataStore.

There is no /v2/auth/register or /v2/auth/login any more (Module 26 —
registration/login happen entirely against Supabase Auth from the
client; see decisions/0022-supabase-auth-migration.md). "Registering" a
farmer here means minting a JWT for a new `sub` (a fresh Supabase user
id) and calling any /v2 route with it — Flask auto-provisions the
Farmer profile row on first sight, which is exactly what
test_profile_auto_provisioned_on_first_request below proves directly.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)

from conftest import jwt_headers, make_jwt

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)

FARMER_1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FARMER_2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


def test_profile_auto_provisioned_on_first_request():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/farmers/me", headers=jwt_headers(FARMER_1, email="alice@example.com"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == FARMER_1
    assert body["email"] == "alice@example.com"
    assert "password_hash" not in body


def test_second_request_reuses_existing_profile_not_recreated():
    app = _app()
    client = app.test_client()
    headers = jwt_headers(FARMER_1, email="alice@example.com")
    first = client.get("/v2/farmers/me", headers=headers)
    client.patch("/v2/farmers/me", json={"name": "Alice K"}, headers=headers)
    second = client.get("/v2/farmers/me", headers=headers)
    assert first.get_json()["created_at"] == second.get_json()["created_at"]
    assert second.get_json()["name"] == "Alice K"


def test_tampered_token_rejected():
    app = _app()
    client = app.test_client()
    token = make_jwt(FARMER_1)
    resp = client.get("/v2/fields", headers={"Authorization": f"Bearer {token}x"})
    assert resp.status_code == 401


def test_missing_authorization_header_401():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/fields")
    assert resp.status_code == 401


def test_full_cross_tenant_isolation_flow():
    app = _app()
    client = app.test_client()

    headers1 = jwt_headers(FARMER_1, email="farmer1@example.com")
    headers2 = jwt_headers(FARMER_2, email="farmer2@example.com")

    # --- Farmer 1 creates a field, can read it back.
    create = client.post(
        "/v2/fields",
        json={"name": "F1 Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
        headers=headers1,
    )
    assert create.status_code == 201
    field_id = create.get_json()["id"]

    get_own = client.get(f"/v2/fields/{field_id}", headers=headers1)
    assert get_own.status_code == 200
    assert get_own.get_json()["id"] == field_id

    list_own = client.get("/v2/fields", headers=headers1)
    assert list_own.status_code == 200
    assert len(list_own.get_json()["items"]) == 1

    # A request with no token at all is rejected.
    assert client.get("/v2/fields").status_code == 401

    # --- Farmer 2: CANNOT see or fetch farmer 1's field.
    list_other = client.get("/v2/fields", headers=headers2)
    assert list_other.status_code == 200
    assert list_other.get_json()["items"] == []

    get_other = client.get(f"/v2/fields/{field_id}", headers=headers2)
    assert get_other.status_code == 404  # not owned -> not found, not leaked


def test_unauthenticated_v2_request_401():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/fields")
    assert resp.status_code == 401


def test_v2_farmers_me_matches_authenticated_farmer():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/farmers/me", headers=jwt_headers(FARMER_1, email="carol@example.com"))
    assert resp.status_code == 200
    assert resp.get_json()["email"] == "carol@example.com"


def test_admin_role_comes_from_token_not_stored_farmer_row():
    """A farmer's stored `role` column is display-only (Module 26) — the
    authoritative source for authorization is always the verified JWT's
    app_metadata.role, checked fresh on every request. A farmer whose
    token says "admin" gets into /v2/admin even before any Farmer row
    exists for them (auto-provisioned inline)."""
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/admin/farmers", headers=jwt_headers(FARMER_1, role="admin"))
    assert resp.status_code == 200


def test_non_admin_role_gets_403_on_admin_routes():
    app = _app()
    client = app.test_client()
    resp = client.get("/v2/admin/farmers", headers=jwt_headers(FARMER_1, role="farmer"))
    assert resp.status_code == 403
