"""Module 23 (A5): ``PATCH /v2/fields/{field_id}`` — partial field update.

Real Flask test client + real ``SQLiteDataStore`` (``:memory:``), same
style as ``test_v2_auth_integration.py``.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, phone="+919000000001"):
    from _otp_helpers import register_and_login

    assert register_and_login(client, phone).status_code == 200


def _create_field(client) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_patch_updates_only_given_fields(client):
    _register_and_login(client)
    field_id = _create_field(client)

    resp = client.patch(f"/v2/fields/{field_id}", json={"current_crop": "rice", "sown_on": "2026-07-01"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["current_crop"] == "rice"
    assert body["sown_on"] == "2026-07-01"
    assert body["name"] == "Plot"  # unchanged
    assert body["latitude"] == 15.0  # unchanged


def test_patch_requires_session(client):
    resp = client.patch("/v2/fields/does-not-matter", json={"name": "X"})
    assert resp.status_code == 401


def test_patch_unknown_field_404(client):
    _register_and_login(client)
    resp = client.patch("/v2/fields/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404


def test_patch_invalid_current_crop_400(client):
    _register_and_login(client)
    field_id = _create_field(client)
    resp = client.patch(f"/v2/fields/{field_id}", json={"current_crop": "unobtainium"})
    assert resp.status_code == 400


def test_patch_empty_body_400(client):
    _register_and_login(client)
    field_id = _create_field(client)
    resp = client.patch(f"/v2/fields/{field_id}", json={})
    assert resp.status_code == 400


def test_patch_unknown_key_400(client):
    _register_and_login(client)
    field_id = _create_field(client)
    resp = client.patch(f"/v2/fields/{field_id}", json={"farmer_id": "hijack-attempt"})
    assert resp.status_code == 400


def test_patch_cross_tenant_404(client):
    _register_and_login(client, "+919111111111")
    field_id = _create_field(client)
    client.post("/v2/auth/logout")

    _register_and_login(client, "+919222222222")
    resp = client.patch(f"/v2/fields/{field_id}", json={"name": "Hijacked"})
    assert resp.status_code == 404


# --- Module 39: GET /v2/fields/{id}/data-summary -------------------------

def test_data_summary_returns_persisted_rows(app, client):
    from datetime import datetime, timedelta, timezone

    from agro_mirai.persistence.models import NDVIReading, SoilSample, WeatherReading

    from agro_mirai.persistence.models import Field_

    _register_and_login(client)
    store = app.extensions["data_store"]
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    now = datetime.now(timezone.utc)
    # Saved straight to the store (not POST /v2/fields) so the live
    # acquisition adapters don't add their own real rows to the assertions.
    field_id = "f0000000-0000-4000-8000-000000000001"
    store.save_field(farmer_id, Field_(
        id=field_id, farmer_id=farmer_id, created_at=now, updated_at=now,
        name="Plot", latitude=15.0, longitude=76.0, area_ha=1.0))
    store.save_weather_reading(farmer_id, WeatherReading(
        id="w-obs", field_id=field_id, observed_at=now - timedelta(days=1),
        source="open-meteo", temp_c=31.5, is_forecast=False, rainfall_mm=2.0))
    store.save_weather_reading(farmer_id, WeatherReading(
        id="w-fc", field_id=field_id, observed_at=now + timedelta(days=1),
        source="open-meteo", temp_c=33.0, is_forecast=True))
    store.save_soil_sample(farmer_id, SoilSample(
        id="s1", field_id=field_id, observed_at=now, source="soilgrids", ph=6.4))
    store.save_ndvi_reading(farmer_id, NDVIReading(
        id="n1", field_id=field_id, observed_at=now, source="gee", ndvi=0.55))

    body = client.get(f"/v2/fields/{field_id}/data-summary").get_json()
    assert body["weather"]["current"]["id"] == "w-obs"
    assert [w["id"] for w in body["weather"]["forecast"]] == ["w-fc"]
    assert body["soil"]["source"] == "soilgrids"
    assert body["ndvi"]["latest"]["ndvi"] == 0.55


def test_data_summary_empty_is_nulls_not_error(client):
    _register_and_login(client)
    field_id = _create_field(client)
    resp = client.get(f"/v2/fields/{field_id}/data-summary")
    assert resp.status_code == 200
    assert {"field_id", "weather", "soil", "ndvi", "fetched_at", "soil_used"} <= set(resp.get_json())


def test_data_summary_cross_tenant_404(client):
    _register_and_login(client, "+919111111111")
    field_id = _create_field(client)
    client.post("/v2/auth/logout")
    _register_and_login(client, "+919222222222")
    assert client.get(f"/v2/fields/{field_id}/data-summary").status_code == 404


def test_data_summary_requires_session(client):
    assert client.get("/v2/fields/x/data-summary").status_code == 401
