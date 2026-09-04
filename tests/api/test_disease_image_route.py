"""Tests for POST /fields/{field_id}/disease-risk/image (Module 21):
upload validation and the CNN-vs-fallback choice, with the CNN HTTP call
mocked at the boundary (agro_mirai.api.cnn_client.call_cnn_service) — no
real network call, no torch/CNN service needed.
"""
from __future__ import annotations

import io

from conftest import FIELD_ID, _auth_headers

import agro_mirai.api.value_endpoints as value_endpoints


def _png_bytes() -> bytes:
    # A real (tiny, valid) 1x1 PNG, built at import time via Pillow — a
    # genuine decodable image, not just bytes with a .png filename, so
    # the content-sniffing check is exercised honestly.
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


def _patch_features(monkeypatch):
    from conftest import _VECTOR

    # Module 23: moved to value_endpoints.py, shared by /v1 and /v2.
    monkeypatch.setattr(value_endpoints, "build_features_for_field", lambda *a, **k: _VECTOR)


def test_missing_image_returns_400(client, monkeypatch):
    _patch_features(monkeypatch)
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "BAD_REQUEST"


def test_non_image_bytes_rejected_400(client, monkeypatch):
    _patch_features(monkeypatch)
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={"image": (io.BytesIO(b"not-an-image-at-all"), "leaf.jpg")},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert "not a valid image" in resp.get_json()["error"]["message"]


def test_oversized_image_rejected_400(client, monkeypatch):
    _patch_features(monkeypatch)
    from agro_mirai.api import image_validation

    monkeypatch.setattr(image_validation, "MAX_IMAGE_BYTES", 10)
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 400
    assert "size limit" in resp.get_json()["error"]["message"]


def test_cnn_service_success_path(client, monkeypatch):
    _patch_features(monkeypatch)

    def fake_call(image_bytes, field_id):
        return {
            "id": "cnn-alert-1",
            "field_id": field_id,
            "created_at": "2026-09-01T00:00:00Z",
            "disease": "Apple Scab",
            "risk_level": "moderate",
            "confidence": 0.81,
            "window_start_at": "2026-09-01T00:00:00Z",
            "window_end_at": "2026-09-06T00:00:00Z",
            "recommended_action": "Scout within 5 days.",
        }

    monkeypatch.setattr(
        "agro_mirai.api.cnn_client.call_cnn_service", fake_call
    )
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source"] == "cnn"
    assert body["disease"] == "Apple Scab"


def test_cnn_service_unreachable_falls_back_never_500(client, monkeypatch):
    _patch_features(monkeypatch)

    def fake_call(image_bytes, field_id):
        return None  # unreachable/timeout/error

    monkeypatch.setattr(
        "agro_mirai.api.cnn_client.call_cnn_service", fake_call
    )
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source"] == "environmental_fallback"
    # the rule-based DISEASE_MODEL mock from conftest.py's `app` fixture
    assert body["disease"] == "fungal_generic"


def test_unknown_field_404(app, monkeypatch):
    _patch_features(monkeypatch)
    app.extensions["store_mock"].get_field.return_value = None
    client = app.test_client()
    resp = client.post(
        f"/fields/{FIELD_ID}/disease-risk/image",
        data={"image": (io.BytesIO(_png_bytes()), "leaf.png")},
        content_type="multipart/form-data",
        headers=_auth_headers(),
    )
    assert resp.status_code == 404
