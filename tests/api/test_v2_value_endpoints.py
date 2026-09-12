"""Module 23 Part A: the six new /v2 value endpoints
(recommendation/irrigation/disease-risk/disease-risk-image/advisories/
feedback), session-authenticated.

This closes the specific coverage blind spot that let Blocker A ship
unnoticed: Module 19's ``test_full_cross_tenant_isolation_flow`` only
ever exercised ``/v2/fields`` — never the endpoints that actually carry
the product's value. Every endpoint here gets its own cross-tenant
(404-not-403-not-leaked) proof and its own no-session 401 proof, plus a
check that the shared ``value_endpoints.py`` refactor kept Module 22's
degrade-not-fail contracts (422 on exhausted weather,
``environmental_fallback`` on an unreachable CNN service) intact on the
/v2 copies specifically, not just on /v1.

Real Flask test client + real ``SQLiteDataStore`` (``:memory:``) + real
session cookies (no mocked auth), same as
``test_v2_auth_integration.py``. The crop/irrigation/disease/
decision-engine models are mocked (same style as ``conftest.py``'s ``app``
fixture) so this doesn't need ``models/*.joblib`` on disk.
"""
from __future__ import annotations

import dataclasses
import io
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import (
    Advisory,
    CropRecommendation,
    DiseaseRiskAlert,
    IrrigationAdvice,
)
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.processing.feature_builder import FeatureVector

_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)

_VECTOR = FeatureVector(
    field_id="placeholder",
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


def _png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def app(monkeypatch):
    store = SQLiteDataStore(":memory:")

    crop_model = MagicMock()
    crop_model.predict.side_effect = lambda features: CropRecommendation(
        id="c1", field_id=features.field_id, created_at=_NOW,
        recommended_crop="cotton", confidence=0.9,
    )
    irrigation_model = MagicMock()
    irrigation_model.predict.side_effect = lambda features: IrrigationAdvice(
        id="i1", field_id=features.field_id, created_at=_NOW,
        recommended_depth_mm=12.0, window_start_at=_NOW, window_end_at=_NOW,
        urgency="moderate",
    )
    disease_model = MagicMock()
    disease_model.predict.side_effect = lambda features: DiseaseRiskAlert(
        id="d1", field_id=features.field_id, created_at=_NOW,
        disease="fungal_generic", risk_level="low", confidence=0.8,
    )
    decision_engine = MagicMock()
    decision_engine.recommend.side_effect = lambda field, features: Advisory(
        id="a1", field_id=field.id, created_at=_NOW,
        language="en", title="Advisory", body="body text",
        severity="moderate", source_refs=["c1", "i1", "d1"],
    )

    application = create_app({
        "TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y",
        "CROP_MODEL": crop_model, "IRRIGATION_MODEL": irrigation_model,
        "DISEASE_MODEL": disease_model, "DECISION_ENGINE": decision_engine,
    })
    # The store's own ownership check keys off the *real* field_id on
    # whatever record a model returns, so the stub feature vector must
    # carry that field's real id — not a fixed placeholder — or every
    # save_*() call below fails a genuine NotFoundError, not the
    # cross-tenant check this test suite is trying to isolate.
    monkeypatch.setattr(
        "agro_mirai.api.value_endpoints.build_features_for_field",
        lambda store, farmer_id, field, *a, **k: dataclasses.replace(_VECTOR, field_id=field.id),
    )
    monkeypatch.setattr("agro_mirai.api.cnn_client.call_cnn_service", lambda *a, **k: None)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, phone: str):
    from _otp_helpers import register_and_login

    r = register_and_login(client, phone)
    assert r.status_code == 200


def _create_field(client) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


# --- Session-required (401 with no session) on every new endpoint ---

def test_recommendation_requires_session(client):
    resp = client.get("/v2/fields/does-not-matter/recommendation")
    assert resp.status_code == 401


def test_irrigation_requires_session(client):
    resp = client.get("/v2/fields/does-not-matter/irrigation")
    assert resp.status_code == 401


def test_disease_risk_requires_session(client):
    resp = client.get("/v2/fields/does-not-matter/disease-risk")
    assert resp.status_code == 401


def test_disease_risk_image_requires_session(client):
    resp = client.post(
        "/v2/fields/does-not-matter/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 401


def test_advisories_requires_session(client):
    resp = client.get("/v2/fields/does-not-matter/advisories")
    assert resp.status_code == 401


def test_feedback_requires_session(client):
    resp = client.post("/v2/feedback", json={"advisory_id": "x", "rating": 5, "helpful": True})
    assert resp.status_code == 401


# --- Success paths (proves the six endpoints actually exist and work) ---

def test_recommendation_success(client):
    _register_and_login(client, "+919000000001")
    field_id = _create_field(client)
    resp = client.get(f"/v2/fields/{field_id}/recommendation")
    assert resp.status_code == 200
    assert resp.get_json()["recommended_crop"] == "cotton"


def test_irrigation_success(client):
    _register_and_login(client, "+919000000002")
    field_id = _create_field(client)
    resp = client.get(f"/v2/fields/{field_id}/irrigation")
    assert resp.status_code == 200
    assert resp.get_json()["urgency"] == "moderate"


def test_disease_risk_success(client):
    _register_and_login(client, "+919000000003")
    field_id = _create_field(client)
    resp = client.get(f"/v2/fields/{field_id}/disease-risk")
    assert resp.status_code == 200
    assert "items" in resp.get_json()


def test_disease_risk_image_falls_back_to_environmental_never_500(client):
    # cnn_client.call_cnn_service is monkeypatched to return None (no CNN
    # service configured) — this is the exact Module 21/22 hard-fallback
    # contract, verified on the /v2 copy specifically.
    _register_and_login(client, "+919000000004")
    field_id = _create_field(client)
    resp = client.post(
        f"/v2/fields/{field_id}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source"] == "environmental_fallback"


def test_advisories_success(client):
    _register_and_login(client, "+919000000005")
    field_id = _create_field(client)
    resp = client.get(f"/v2/fields/{field_id}/advisories")
    assert resp.status_code == 200
    assert len(resp.get_json()["items"]) >= 1


def test_feedback_success(client):
    _register_and_login(client, "+919000000006")
    field_id = _create_field(client)
    advisories = client.get(f"/v2/fields/{field_id}/advisories").get_json()["items"]
    advisory_id = advisories[0]["id"]
    resp = client.post(
        "/v2/feedback",
        json={"advisory_id": advisory_id, "rating": 4, "helpful": True},
    )
    assert resp.status_code == 201
    assert resp.get_json()["rating"] == 4


# --- Module 22 behaviour preserved: 422 on exhausted weather ---

def test_irrigation_returns_422_not_500_when_no_weather_data(client, monkeypatch):
    _register_and_login(client, "+919000000007")
    field_id = _create_field(client)

    def _raise(*args, **kwargs):
        raise ValueError("no temperature data available in any window")

    monkeypatch.setattr("agro_mirai.api.value_endpoints.build_features_for_field", _raise)
    resp = client.get(f"/v2/fields/{field_id}/irrigation")
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "NO_WEATHER_DATA"


# --- Cross-tenant isolation: farmer B must get 404, never 403/leak, on
# every one of farmer A's fields/advisories, across every new endpoint. ---

@pytest.fixture
def two_farmers(client):
    _register_and_login(client, "+919111111111")
    field_id = _create_field(client)
    advisories = client.get(f"/v2/fields/{field_id}/advisories").get_json()["items"]
    advisory_id = advisories[0]["id"]
    client.post("/v2/auth/logout")

    _register_and_login(client, "+919222222222")
    return field_id, advisory_id


def test_recommendation_cross_tenant_404(client, two_farmers):
    field_id, _ = two_farmers
    resp = client.get(f"/v2/fields/{field_id}/recommendation")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "NOT_FOUND"


def test_irrigation_cross_tenant_404(client, two_farmers):
    field_id, _ = two_farmers
    resp = client.get(f"/v2/fields/{field_id}/irrigation")
    assert resp.status_code == 404


def test_disease_risk_cross_tenant_404(client, two_farmers):
    field_id, _ = two_farmers
    resp = client.get(f"/v2/fields/{field_id}/disease-risk")
    assert resp.status_code == 404


def test_disease_risk_image_cross_tenant_404(client, two_farmers):
    field_id, _ = two_farmers
    resp = client.post(
        f"/v2/fields/{field_id}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_advisories_cross_tenant_404(client, two_farmers):
    field_id, _ = two_farmers
    resp = client.get(f"/v2/fields/{field_id}/advisories")
    assert resp.status_code == 404


def test_feedback_cross_tenant_404(client, two_farmers):
    _, advisory_id = two_farmers
    resp = client.post(
        "/v2/feedback",
        json={"advisory_id": advisory_id, "rating": 3, "helpful": True},
    )
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "NOT_FOUND"
