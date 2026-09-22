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
    import numpy as np
    from PIL import Image

    # Textured foliage-like image: a flat green one is (correctly) rejected
    # by the leaf gate as NOT_A_LEAF.
    rng = np.random.default_rng(0)
    arr = np.empty((64, 64, 3))
    arr[...] = (50, 130, 40)
    arr += rng.normal(0, 30, arr.shape)
    arr[:, ::8] *= 0.4
    buf = io.BytesIO()
    Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).save(buf, format="PNG")
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


def test_non_leaf_photo_rejected_with_422_not_diagnosed(monkeypatch):
    """Module 39: a white bed-sheet-like image must NOT reach the CNN or get a diagnosis."""
    import io
    from PIL import Image
    from agro_mirai.api import leaf_gate

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(240, 240, 240)).save(buf, format="PNG")
    assert not leaf_gate.looks_like_plant_photo(buf.getvalue())


def test_cnn_client_sends_service_token_when_configured(monkeypatch):
    from unittest.mock import MagicMock

    from agro_mirai.api import cnn_client

    seen = {}

    def fake_post(url, **kw):
        seen.update(kw)
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"ok": True}
        return r

    monkeypatch.setenv("CNN_SERVICE_URL", "http://cnn.example")
    monkeypatch.setattr(cnn_client.requests, "post", fake_post)

    monkeypatch.setenv("CNN_SERVICE_TOKEN", "s3cret")
    assert cnn_client.call_cnn_service(b"x", "f") == {"ok": True}
    assert seen["headers"] == {"X-Service-Token": "s3cret"}

    monkeypatch.delenv("CNN_SERVICE_TOKEN")
    cnn_client.call_cnn_service(b"x", "f")
    assert seen["headers"] == {}


def test_cnn_client_retries_once_on_network_failure_then_succeeds(monkeypatch):
    from agro_mirai.api import cnn_client
    import requests

    calls = {"n": 0}

    def flaky_post(url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.Timeout("cold start")
        r = type("R", (), {"status_code": 200, "json": lambda self: {"ok": True}})()
        return r

    monkeypatch.setenv("CNN_SERVICE_URL", "http://cnn.example")
    monkeypatch.setattr(cnn_client.requests, "post", flaky_post)
    assert cnn_client.call_cnn_service(b"x", "f") == {"ok": True}
    assert calls["n"] == 2


def test_cnn_client_gives_up_after_two_network_failures(monkeypatch):
    from agro_mirai.api import cnn_client
    import requests

    calls = {"n": 0}

    def always_fails(url, **kw):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("still cold")

    monkeypatch.setenv("CNN_SERVICE_URL", "http://cnn.example")
    monkeypatch.setattr(cnn_client.requests, "post", always_fails)
    assert cnn_client.call_cnn_service(b"x", "f") is None
    assert calls["n"] == 2


def test_cnn_client_does_not_retry_on_a_real_error_response(monkeypatch):
    from agro_mirai.api import cnn_client

    calls = {"n": 0}

    def bad_response(url, **kw):
        calls["n"] += 1
        return type("R", (), {"status_code": 422, "json": lambda self: {}})()

    monkeypatch.setenv("CNN_SERVICE_URL", "http://cnn.example")
    monkeypatch.setattr(cnn_client.requests, "post", bad_response)
    assert cnn_client.call_cnn_service(b"x", "f") is None
    assert calls["n"] == 1
