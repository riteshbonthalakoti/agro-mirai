"""Module 19: read-only Admin dashboard route tests. Non-admin gets 403,
admin sees everything, and — per the module spec's "don't just trust
the routing" instruction — a direct assertion that no write method is
registered under /v2/admin at all.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app_and_client():
    store = SQLiteDataStore(":memory:")
    app = create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})
    return app, app.test_client()


def _register_and_login(client, phone, name="Someone"):
    from _otp_helpers import register_and_login

    assert register_and_login(client, phone, name=name).status_code == 200


def test_admin_routes_expose_exactly_the_documented_write_methods():
    # Flask's @bp.patch/@bp.delete shortcuts each register their own Rule
    # (one method per rule, same path) rather than merging into a single
    # multi-method rule, so methods are aggregated per path before
    # comparing against what's expected.
    app, _ = _app_and_client()
    expected_writes = {
        "/v2/admin/farmers/<farmer_id>": {"PATCH", "DELETE"},
        "/v2/admin/fields/<field_id>": {"PATCH", "DELETE"},
        "/v2/admin/bug-reports/<bug_report_id>": {"PATCH", "DELETE"},
    }
    methods_by_path: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith("/v2/admin"):
            continue
        methods_by_path.setdefault(rule.rule, set()).update(rule.methods - {"HEAD", "OPTIONS"})

    for path, methods in methods_by_path.items():
        if path in expected_writes:
            assert methods == expected_writes[path], path
        else:
            assert methods <= {"GET"}, f"{path} exposes unexpected methods: {methods}"


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

    from _otp_helpers import register_and_login

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


def test_admin_scans_and_advisories():
    from datetime import datetime, timezone

    from agro_mirai.persistence.models import Advisory, DiseaseRiskAlert

    app, client = _app_and_client()
    store = app.extensions["data_store"]
    _register_and_login(client, "+919000000031", name="Farmer")
    field_id = client.post(
        "/v2/fields", json={"name": "Plot S", "latitude": 1.0, "longitude": 1.0, "area_ha": 1.0}
    ).get_json()["id"]
    farmer = store.get_farmer_by_phone("+919000000031")
    now = datetime.now(timezone.utc)

    def alert(id_, source):
        return DiseaseRiskAlert(
            id=id_, field_id=field_id, created_at=now, disease="d", risk_level="low",
            confidence=0.5, recommended_action="a", window_start_at=now, window_end_at=now,
            source=source,
        )

    for id_, source in [("a1", "cnn"), ("a2", "environmental_fallback"), ("a3", "environmental")]:
        store.save_disease_risk_alert(farmer.id, alert(id_, source))
    store.save_advisory(
        farmer.id,
        Advisory(
            id="adv1", field_id=field_id, created_at=now, title="t", body="b",
            severity="low", language="en",
        ),
    )
    client.post("/v2/auth/logout")

    farmer.role = "admin"
    store.save_farmer(farmer)
    _register_and_login(client, "+919000000031", name="Farmer")

    scans = client.get("/v2/admin/scans").get_json()["items"]
    assert {s["id"] for s in scans} == {"a1", "a2"}
    assert all(s["farmer_id"] == farmer.id and s["field_name"] == "Plot S" for s in scans)

    advisories = client.get("/v2/admin/advisories").get_json()["items"]
    assert [a["id"] for a in advisories] == ["adv1"]
    assert advisories[0]["field_name"] == "Plot S"


def test_admin_scans_and_advisories_require_admin():
    app, client = _app_and_client()
    assert client.get("/v2/admin/scans").status_code == 401
    _register_and_login(client, "+919000000032")
    assert client.get("/v2/admin/scans").status_code == 403
    assert client.get("/v2/admin/advisories").status_code == 403


def test_admin_overview_requires_admin():
    app, client = _app_and_client()
    assert client.get("/v2/admin/overview").status_code == 401
    _register_and_login(client, "+919000000040")
    assert client.get("/v2/admin/overview").status_code == 403


def test_admin_overview_aggregates_totals_and_distributions():
    from datetime import datetime, timezone

    from agro_mirai.persistence.models import Advisory, DiseaseRiskAlert

    app, client = _app_and_client()
    store = app.extensions["data_store"]

    _register_and_login(client, "+919000000041", name="Farmer A")
    field_id = client.post(
        "/v2/fields",
        json={
            "name": "Plot O",
            "latitude": 1.0,
            "longitude": 1.0,
            "area_ha": 1.0,
            "current_crop": "cotton",
        },
    ).get_json()["id"]
    farmer = store.get_farmer_by_phone("+919000000041")
    now = datetime.now(timezone.utc)

    store.save_disease_risk_alert(
        farmer.id,
        DiseaseRiskAlert(
            id="ov1", field_id=field_id, created_at=now, disease="blight", risk_level="high",
            confidence=0.9, source="cnn",
        ),
    )
    store.save_advisory(
        farmer.id,
        Advisory(
            id="ov-adv1", field_id=field_id, created_at=now, title="t", body="b",
            severity="high", language="en",
        ),
    )
    client.post("/v2/auth/logout")

    farmer.role = "admin"
    store.save_farmer(farmer)
    _register_and_login(client, "+919000000041", name="Farmer A")

    resp = client.get("/v2/admin/overview")
    assert resp.status_code == 200
    body = resp.get_json()

    assert body["total_farmers"] == 1
    assert body["total_fields"] == 1
    assert body["total_scans"] == 1
    assert body["language_distribution"] == {"en": 1}
    assert body["crop_distribution"] == {"cotton": 1}
    recent_ids = {(r["type"], r["detail"]) for r in body["recent_activity"]}
    assert ("scan", "blight") in recent_ids
    assert ("advisory", "high") in recent_ids
