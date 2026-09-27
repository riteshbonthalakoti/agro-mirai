"""Module 50: farmer/field write routes under /v2/admin — PATCH/DELETE
behind @require_admin, each writing an audit_log row via
api/audit.write_audit_log. See decisions/0030-admin-write-actions.md.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def _admin_session(client, store, phone="+919000000090"):
    from _otp_helpers import register_and_login

    register_and_login(client, phone, name="Admin")
    admin = store.get_farmer_by_phone(phone)
    admin.role = "admin"
    store.save_farmer(admin)
    register_and_login(client, phone, name="Admin")
    return admin


def test_patch_farmer_updates_fields_and_writes_audit_log():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    resp = client.patch(f"/v2/admin/farmers/{admin.id}", json={"district": "Bellary"})
    assert resp.status_code == 200
    assert resp.get_json()["district"] == "Bellary"

    audit = store.list_audit_log()
    assert len(audit) == 1
    assert audit[0].action == "farmer.update"
    assert audit[0].target_id == admin.id


def test_patch_farmer_404_when_not_found():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _admin_session(client, store)
    resp = client.patch("/v2/admin/farmers/does-not-exist", json={"district": "X"})
    assert resp.status_code == 404


def test_delete_farmer_removes_and_audits():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000091", name="Victim")
    victim = store.get_farmer_by_phone("+919000000091")
    register_and_login(client, "+919000000090", name="Admin")

    resp = client.delete(f"/v2/admin/farmers/{victim.id}")
    assert resp.status_code == 200
    assert store.get_farmer(victim.id) is None

    audit = [a for a in store.list_audit_log() if a.action == "farmer.delete"]
    assert len(audit) == 1
    assert audit[0].target_id == victim.id
    assert audit[0].after_json is None


def test_delete_farmer_404_second_time():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000092", name="Victim2")
    victim = store.get_farmer_by_phone("+919000000092")
    register_and_login(client, "+919000000090", name="Admin")

    assert client.delete(f"/v2/admin/farmers/{victim.id}").status_code == 200
    assert client.delete(f"/v2/admin/farmers/{victim.id}").status_code == 404


def test_non_admin_gets_403_on_write_routes():
    app, client = _app_and_client()
    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000093", name="Plain")
    resp = client.patch("/v2/admin/farmers/whatever", json={"district": "X"})
    assert resp.status_code == 403


def test_patch_field_and_delete_field():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000094", name="Owner")
    field_id = client.post(
        "/v2/fields", json={"name": "Plot", "latitude": 1.0, "longitude": 1.0, "area_ha": 1.0}
    ).get_json()["id"]
    register_and_login(client, "+919000000090", name="Admin")

    resp = client.patch(f"/v2/admin/fields/{field_id}", json={"current_crop": "cotton"})
    assert resp.status_code == 200
    assert resp.get_json()["current_crop"] == "cotton"

    resp = client.delete(f"/v2/admin/fields/{field_id}")
    assert resp.status_code == 200
    assert store.get_field_by_id(field_id) is None


def test_patch_field_404_when_not_found():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _admin_session(client, store)
    resp = client.patch("/v2/admin/fields/nope", json={"current_crop": "x"})
    assert resp.status_code == 404
