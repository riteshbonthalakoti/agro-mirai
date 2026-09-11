"""Module 23 (A5): ``PATCH /v2/fields/{field_id}`` — partial field update.

Real Flask test client + real ``SQLiteDataStore`` (``:memory:``), same
style as ``test_v2_auth_integration.py``.
"""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

from conftest import jwt_headers

FARMER_A = "aaaaaaaa-1111-4000-8000-0000000000a1"
FARMER_B = "bbbbbbbb-1111-4000-8000-0000000000b1"


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _create_field(client, headers) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
        headers=headers,
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_patch_updates_only_given_fields(client):
    headers = jwt_headers(FARMER_A)
    field_id = _create_field(client, headers)

    resp = client.patch(
        f"/v2/fields/{field_id}",
        json={"current_crop": "rice", "sown_on": "2026-07-01"},
        headers=headers,
    )
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
    headers = jwt_headers(FARMER_A)
    resp = client.patch("/v2/fields/does-not-exist", json={"name": "X"}, headers=headers)
    assert resp.status_code == 404


def test_patch_invalid_current_crop_400(client):
    headers = jwt_headers(FARMER_A)
    field_id = _create_field(client, headers)
    resp = client.patch(f"/v2/fields/{field_id}", json={"current_crop": "unobtainium"}, headers=headers)
    assert resp.status_code == 400


def test_patch_empty_body_400(client):
    headers = jwt_headers(FARMER_A)
    field_id = _create_field(client, headers)
    resp = client.patch(f"/v2/fields/{field_id}", json={}, headers=headers)
    assert resp.status_code == 400


def test_patch_unknown_key_400(client):
    headers = jwt_headers(FARMER_A)
    field_id = _create_field(client, headers)
    resp = client.patch(f"/v2/fields/{field_id}", json={"farmer_id": "hijack-attempt"}, headers=headers)
    assert resp.status_code == 400


def test_patch_cross_tenant_404(client):
    headers_a = jwt_headers(FARMER_A, email="farmerA@example.com")
    field_id = _create_field(client, headers_a)

    headers_b = jwt_headers(FARMER_B, email="farmerB@example.com")
    resp = client.patch(f"/v2/fields/{field_id}", json={"name": "Hijacked"}, headers=headers_b)
    assert resp.status_code == 404
