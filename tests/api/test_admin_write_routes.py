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


def test_patch_farmer_ignores_non_whitelisted_fields():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000095", name="Target")
    target = store.get_farmer_by_phone("+919000000095")
    register_and_login(client, "+919000000090", name="Admin")

    resp = client.patch(
        f"/v2/admin/farmers/{target.id}",
        json={"district": "Bellary", "role": "admin", "id": "something-else"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["district"] == "Bellary"

    reloaded = store.get_farmer(target.id)
    assert reloaded is not None
    assert reloaded.role != "admin"
    assert reloaded.id == target.id


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


_VALID_STATUSES = {"open", "triaged", "in_progress", "resolved"}


def test_list_bug_reports():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b1", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    resp = client.get("/v2/admin/bug-reports")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert any(i["id"] == "b1" and i["status"] == "open" for i in items)


def test_patch_bug_report_status_valid_and_invalid():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)
    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b2", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    resp = client.patch("/v2/admin/bug-reports/b2", json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "resolved"

    resp = client.patch("/v2/admin/bug-reports/b2", json={"status": "not-a-real-status"})
    assert resp.status_code == 400

    resp = client.patch("/v2/admin/bug-reports/does-not-exist", json={"status": "resolved"})
    assert resp.status_code == 404


def test_delete_bug_report():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)
    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b3", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    assert client.delete("/v2/admin/bug-reports/b3").status_code == 200
    assert client.delete("/v2/admin/bug-reports/b3").status_code == 404
    audit = [a for a in store.list_audit_log() if a.action == "bug_report.delete"]
    assert len(audit) == 1


def test_audit_log_read_route_returns_entries():
    app, client = _app_and_client()
    store = app.extensions["data_store"]
    admin = _admin_session(client, store)

    from datetime import datetime, timezone
    from agro_mirai.persistence.models import BugReport
    store.save_bug_report(admin.id, BugReport(id="b4", farmer_id=admin.id,
                                               created_at=datetime.now(timezone.utc)))

    # Perform a write action that creates an audit log entry
    resp = client.patch("/v2/admin/bug-reports/b4", json={"status": "triaged"})
    assert resp.status_code == 200

    # Fetch audit log and verify the entry is there
    resp = client.get("/v2/admin/audit-log")
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert len(items) > 0
    status_entry = next(
        (e for e in items if e["action"] == "bug_report.status" and e["target_id"] == "b4"),
        None
    )
    assert status_entry is not None
    assert status_entry["target_type"] == "bug_report"


def test_audit_log_requires_admin():
    app, client = _app_and_client()
    from _otp_helpers import register_and_login
    register_and_login(client, "+919000000099", name="Plain")
    resp = client.get("/v2/admin/audit-log")
    assert resp.status_code == 403
