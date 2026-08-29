"""Unit tests: each route handler's response shape, mocking DecisionEngine
and DataStore. Confirms status codes, JSON structure, and auth rejection.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import (
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    Farmer,
    Field_,
    IrrigationAdvice,
)
from agro_mirai.processing.feature_builder import FeatureVector

API_KEY = "test-secret-key"
FARMER_ID = "11111111-1111-4111-8111-111111111111"
FIELD_ID = "22222222-2222-4222-8222-222222222222"

_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)

_FIELD = Field_(
    id=FIELD_ID,
    farmer_id=FARMER_ID,
    created_at=_NOW,
    updated_at=_NOW,
    name="North Plot",
    latitude=15.1394,
    longitude=76.9214,
    area_ha=1.75,
    elevation_m=449.0,
    soil_type="red",
    current_crop="cotton",
    sown_on=date(2026, 6, 15),
)

_VECTOR = FeatureVector(
    field_id=FIELD_ID,
    as_of=date(2026, 8, 24),
    rainfall_mm_sum_7d=6.6,
    temp_c_mean_7d=25.0,
    humidity_pct_mean_7d=69.0,
    rainfall_mm_sum_14d=10.0,
    temp_c_mean_14d=25.0,
    humidity_pct_mean_14d=69.0,
    rainfall_mm_sum_30d=20.0,
    temp_c_mean_30d=25.0,
    humidity_pct_mean_30d=69.0,
    soil_data_available=True,
)


def _mock_store():
    store = MagicMock()
    store.ping.return_value = True
    store.get_farmer.return_value = Farmer(
        id=FARMER_ID,
        created_at=_NOW,
        updated_at=_NOW,
        name="Ravi Kumar",
        preferred_language="kn",
    )
    store.get_field.return_value = _FIELD
    store.list_fields.return_value = [_FIELD]
    store.list_weather_readings.return_value = ["placeholder"]  # non-empty
    store.list_soil_samples.return_value = []
    store.list_ndvi_readings.return_value = []
    store.save_field.side_effect = lambda farmer_id, field: field
    store.save_crop_recommendation.side_effect = lambda farmer_id, rec: rec
    store.save_irrigation_advice.side_effect = lambda farmer_id, adv: adv
    store.save_disease_risk_alert.side_effect = lambda farmer_id, alert: alert
    store.save_advisory.side_effect = lambda farmer_id, adv: adv
    store.list_disease_risk_alerts.return_value = []
    store.list_advisories_for_field.return_value = []
    return store


@pytest.fixture
def app(monkeypatch):
    store = _mock_store()

    crop_model = MagicMock()
    crop_model.predict.return_value = CropRecommendation(
        id="c1", field_id=FIELD_ID, created_at=_NOW,
        recommended_crop="cotton", confidence=0.9,
    )
    irrigation_model = MagicMock()
    irrigation_model.predict.return_value = IrrigationAdvice(
        id="i1", field_id=FIELD_ID, created_at=_NOW,
        recommended_depth_mm=12.0, window_start_at=_NOW, window_end_at=_NOW,
        urgency="moderate",
    )
    disease_model = MagicMock()
    disease_model.predict.return_value = DiseaseRiskAlert(
        id="d1", field_id=FIELD_ID, created_at=_NOW,
        disease="fungal_generic", risk_level="low", confidence=0.8,
    )
    decision_engine = MagicMock()
    decision_engine.recommend.return_value = Advisory(
        id="a1", field_id=FIELD_ID, created_at=_NOW,
        language="en", title="Advisory for cotton", body="body text",
        severity="moderate", source_refs=["c1", "i1", "d1"],
    )

    monkeypatch.setattr(
        "agro_mirai.api.routes.advisory.build_features_for_field",
        lambda *a, **k: _VECTOR,
    )

    application = create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": FARMER_ID,
            "TESTING": True,
            "DATA_STORE": store,
            "CROP_MODEL": crop_model,
            "IRRIGATION_MODEL": irrigation_model,
            "DISEASE_MODEL": disease_model,
            "DECISION_ENGINE": decision_engine,
        }
    )
    application.extensions["store_mock"] = store
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _auth_headers():
    return {"Authorization": f"Bearer {API_KEY}"}


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
