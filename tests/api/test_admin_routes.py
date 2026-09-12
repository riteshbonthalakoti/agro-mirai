"""Module 19: read-only Admin dashboard route tests. Non-admin gets 403,
admin sees everything, and — per the module spec's "don't just trust
the routing" instruction — a direct assertion that no write method is
registered under /v2/admin at all.
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

pytestmark = pytest.mark.skipif(
    not CROP_MODEL_PATH.exists() or not IRRIGATION_MODEL_PATH.exists(),
    reason="models/*.joblib not present — run tools/train_*.py first",
)


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def _register_and_login(client, phone, name="Someone"):
    from tests.api._otp_helpers import register_and_login

    assert register_and_login(client, phone, name=name).status_code == 200


def test_admin_routes_are_read_only_no_write_methods_registered():
    app, _ = _app_and_client()
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/v2/admin"):
            methods = rule.methods - {"HEAD", "OPTIONS"}
            assert methods <= {"GET"}, f"{rule.rule} exposes non-GET methods: {methods}"


def test_non_admin_gets_403():
    app, client = _app_and_client()
    _register_and_login(client, "+919000000021")
    resp = client.get("/v2/admin/farmers")
    assert resp.status_code == 403


def test_unauthenticated_gets_401_not_403():
    app, client = _app_and_client()
    resp = client.get("/v2/admin/farmers")
    assert resp.status_code == 401


def test_admin_sees_all_farmers_and_fields():
    app, client = _app_and_client()
    store = app.extensions["data_store"]

    _register_and_login(client, "+919000000022", name="A")
    client.post(
        "/v2/fields", json={"name": "Plot A", "latitude": 1.0, "longitude": 1.0, "area_ha": 1.0}
    )
    client.post("/v2/auth/logout")

    _register_and_login(client, "+919000000023", name="B")
    client.post(
        "/v2/fields", json={"name": "Plot B", "latitude": 2.0, "longitude": 2.0, "area_ha": 2.0}
    )
    client.post("/v2/auth/logout")

    # Promote farmer B to admin directly via the store (no admin-signup
    # endpoint exists — provisioning an admin is an out-of-band step,
    # documented as a known limitation, see decisions/0023).
    admin_farmer = store.get_farmer_by_phone("+919000000023")
    admin_farmer.role = "admin"
    store.save_farmer(admin_farmer)

    from tests.api._otp_helpers import register_and_login

    assert register_and_login(client, "+919000000023", name="B").status_code == 200

    farmers_resp = client.get("/v2/admin/farmers")
    assert farmers_resp.status_code == 200
    farmers = farmers_resp.get_json()["items"]
    phones = {f["phone"] for f in farmers}
    assert {"+919000000022", "+919000000023"} <= phones
    assert all("password_hash" not in f for f in farmers)
    assert all("field_count" in f for f in farmers)

    fields_resp = client.get("/v2/admin/fields")
    assert fields_resp.status_code == 200
    names = {f["name"] for f in fields_resp.get_json()["items"]}
    assert {"Plot A", "Plot B"} <= names

    feedback_resp = client.get("/v2/admin/feedback")
    assert feedback_resp.status_code == 200
    body = feedback_resp.get_json()
    assert "total_entries" in body
