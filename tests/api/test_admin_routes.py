"""Module 19/26: read-only Admin dashboard route tests. Non-admin gets
403, admin sees everything, and — per the module spec's "don't just
trust the routing" instruction — a direct assertion that no write method
is registered under /v2/admin at all.

Module 26: auth is now a Supabase JWT (see conftest.py's jwt_headers);
"admin" is a role claim on the token (app_metadata.role), not a stored
Farmer.role flipped via the store before a session login — see
decisions/0022-supabase-auth-migration.md.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.models.crop_recommendation_model import (
    DEFAULT_MODEL_PATH as CROP_MODEL_PATH,
)
from agro_mirai.models.irrigation_prediction_model import (
    DEFAULT_MODEL_PATH as IRRIGATION_MODEL_PATH,
)
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

from conftest import jwt_headers

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)

FARMER_A = "aaaaaaaa-0000-4000-8000-000000000001"
FARMER_B = "bbbbbbbb-0000-4000-8000-000000000002"


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def test_admin_routes_are_read_only_no_write_methods_registered():
    app, _ = _app_and_client()
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/v2/admin"):
            methods = rule.methods - {"HEAD", "OPTIONS"}
            assert methods <= {"GET"}, f"{rule.rule} exposes non-GET methods: {methods}"


def test_non_admin_gets_403():
    app, client = _app_and_client()
    resp = client.get("/v2/admin/farmers", headers=jwt_headers(FARMER_A, role="farmer"))
    assert resp.status_code == 403


def test_unauthenticated_gets_401_not_403():
    app, client = _app_and_client()
    resp = client.get("/v2/admin/farmers")
    assert resp.status_code == 401


def test_admin_sees_all_farmers_and_fields():
    app, client = _app_and_client()

    client.post(
        "/v2/fields",
        json={"name": "Plot A", "latitude": 1.0, "longitude": 1.0, "area_ha": 1.0},
        headers=jwt_headers(FARMER_A, role="farmer", email="farmer_a@example.com"),
    )
    client.post(
        "/v2/fields",
        json={"name": "Plot B", "latitude": 2.0, "longitude": 2.0, "area_ha": 2.0},
        headers=jwt_headers(FARMER_B, role="farmer", email="farmer_b@example.com"),
    )

    # farmer_b's token now claims "admin" — this is exactly what
    # provisioning an admin looks like post-Module-26: the role lives in
    # Supabase (set via the Admin API, out of band), and any subsequent
    # token for that user carries app_metadata.role="admin".
    admin_headers = jwt_headers(FARMER_B, role="admin", email="farmer_b@example.com")

    farmers_resp = client.get("/v2/admin/farmers", headers=admin_headers)
    assert farmers_resp.status_code == 200
    farmers = farmers_resp.get_json()["items"]
    emails = {f["email"] for f in farmers}
    assert {"farmer_a@example.com", "farmer_b@example.com"} <= emails
    assert all("password_hash" not in f for f in farmers)
    assert all("field_count" in f for f in farmers)

    fields_resp = client.get("/v2/admin/fields", headers=admin_headers)
    assert fields_resp.status_code == 200
    names = {f["name"] for f in fields_resp.get_json()["items"]}
    assert {"Plot A", "Plot B"} <= names

    feedback_resp = client.get("/v2/admin/feedback", headers=admin_headers)
    assert feedback_resp.status_code == 200
    body = feedback_resp.get_json()
    assert "total_entries" in body
