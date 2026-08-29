"""Unit tests: each route handler's response shape, mocking DecisionEngine
and DataStore. Confirms status codes, JSON structure, and auth rejection.

Fixtures (``app``, ``client``) and shared constants live in conftest.py so
other test modules (e.g. test_request_logging.py) can reuse them.
"""
from __future__ import annotations

from conftest import _NOW, FARMER_ID, FIELD_ID, _auth_headers

from agro_mirai.persistence.models import Advisory


def test_health_no_auth_required(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_missing_auth_header_rejected(client):
    resp = client.get("/farmers/me")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_wrong_auth_key_rejected(client):
    resp = client.get("/farmers/me", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


def test_get_me_returns_farmer(client):
    resp = client.get("/farmers/me", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == FARMER_ID
    assert body["name"] == "Ravi Kumar"


def test_list_fields(client):
    resp = client.get("/fields", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["items"][0]["id"] == FIELD_ID


def test_create_field_missing_required_returns_400(client):
    resp = client.post("/fields", json={"name": "X"}, headers=_auth_headers())
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_REQUEST"


def test_create_field_success(client):
    resp = client.post(
        "/fields",
        json={"name": "South Plot", "latitude": 15.0, "longitude": 77.0, "area_ha": 2.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    assert resp.get_json()["name"] == "South Plot"


def test_create_field_non_numeric_latitude_returns_400(client):
    resp = client.post(
        "/fields",
        json={"name": "X", "latitude": "not-a-number", "longitude": 77.0, "area_ha": 2.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_REQUEST"


def test_create_field_out_of_range_latitude_returns_400(client):
    resp = client.post(
        "/fields",
        json={"name": "X", "latitude": 91.0, "longitude": 77.0, "area_ha": 2.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_field_out_of_range_longitude_returns_400(client):
    resp = client.post(
        "/fields",
        json={"name": "X", "latitude": 15.0, "longitude": -181.0, "area_ha": 2.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_field_negative_area_ha_returns_400(client):
    resp = client.post(
        "/fields",
        json={"name": "X", "latitude": 15.0, "longitude": 77.0, "area_ha": -1.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_field_invalid_soil_type_returns_400(client):
    resp = client.post(
        "/fields",
        json={
            "name": "X", "latitude": 15.0, "longitude": 77.0, "area_ha": 2.0,
            "soil_type": "moon-dust",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_field_invalid_current_crop_returns_400(client):
    resp = client.post(
        "/fields",
        json={
            "name": "X", "latitude": 15.0, "longitude": 77.0, "area_ha": 2.0,
            "current_crop": "unobtainium",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_create_field_malformed_sown_on_returns_400_not_500(client):
    resp = client.post(
        "/fields",
        json={
            "name": "X", "latitude": 15.0, "longitude": 77.0, "area_ha": 2.0,
            "sown_on": "not-a-date",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_REQUEST"


def test_create_field_non_string_name_returns_400(client):
    resp = client.post(
        "/fields",
        json={"name": 12345, "latitude": 15.0, "longitude": 77.0, "area_ha": 2.0},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_get_field_unknown_id_returns_404(app, client):
    app.extensions["store_mock"].get_field.return_value = None
    resp = client.get("/fields/does-not-exist", headers=_auth_headers())
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "NOT_FOUND"


def test_get_recommendation(client):
    resp = client.get(f"/fields/{FIELD_ID}/recommendation", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["recommended_crop"] == "cotton"
    assert body["confidence"] == 0.9


def test_get_irrigation(client):
    resp = client.get(f"/fields/{FIELD_ID}/irrigation", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.get_json()["urgency"] == "moderate"


def test_get_disease_risk_returns_items_list(app, client):
    resp = client.get(f"/fields/{FIELD_ID}/disease-risk", headers=_auth_headers())
    assert resp.status_code == 200
    assert "items" in resp.get_json()


def test_get_advisories_returns_items_list(client):
    resp = client.get(f"/fields/{FIELD_ID}/advisories", headers=_auth_headers())
    assert resp.status_code == 200
    assert "items" in resp.get_json()


def test_recommendation_unknown_field_returns_404(app, client):
    app.extensions["store_mock"].get_field.return_value = None
    resp = client.get(f"/fields/{FIELD_ID}/recommendation", headers=_auth_headers())
    assert resp.status_code == 404


def test_submit_feedback_success(app, client):
    app.extensions["store_mock"].get_advisory.return_value = Advisory(
        id="a1", field_id=FIELD_ID, created_at=_NOW, language="en",
        title="t", body="b", severity="low",
    )
    app.extensions["store_mock"].save_feedback_entry.side_effect = lambda farmer_id, e: e
    resp = client.post(
        "/feedback",
        json={"advisory_id": "a1", "rating": 5, "helpful": True},
        headers=_auth_headers(),
    )
    assert resp.status_code == 201
    assert resp.get_json()["rating"] == 5


def test_submit_feedback_unknown_advisory_returns_404(app, client):
    app.extensions["store_mock"].get_advisory.return_value = None
    resp = client.post(
        "/feedback",
        json={"advisory_id": "does-not-exist", "rating": 3, "helpful": False},
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


def test_submit_feedback_bad_rating_returns_400(client):
    resp = client.post(
        "/feedback",
        json={"advisory_id": "a1", "rating": 9, "helpful": False},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400


def test_submit_feedback_non_bool_helpful_returns_400(client):
    resp = client.post(
        "/feedback",
        json={"advisory_id": "a1", "rating": 3, "helpful": "yes"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_REQUEST"


def test_submit_feedback_non_string_comment_returns_400(client):
    resp = client.post(
        "/feedback",
        json={"advisory_id": "a1", "rating": 3, "helpful": True, "comment": 123},
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
