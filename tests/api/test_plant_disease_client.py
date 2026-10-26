"""plant_disease_client.identify_disease's HTTP-level status handling.

Found live (field test, 2026-10-26): Kindwise answers a successful
identification with HTTP 201, not 200 -- a strict == 200 check silently
treated every real success as a failure, so this tier never actually
contributed despite a working key. This locks in the fix."""
from unittest.mock import MagicMock

from agro_mirai.api import plant_disease_client


def _fake_resp(status_code: int, body: dict):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = body
    return r


def _with_fixed_key(monkeypatch):
    # The module-level `_pool` reads its keys from the environment once, at
    # import time -- too early for monkeypatch.setenv to reach it here, same
    # as every other KeyPool-backed client in this codebase. Patch the pool
    # itself instead.
    monkeypatch.setattr(plant_disease_client._pool, "get_key", lambda: "k1")
    monkeypatch.setattr(plant_disease_client._pool, "mark_success", lambda key: None)
    monkeypatch.setattr(plant_disease_client._pool, "mark_rate_limited", lambda key: None)


def test_identify_disease_accepts_201_as_success(monkeypatch):
    _with_fixed_key(monkeypatch)
    body = {"result": {"disease": {"suggestions": [{"name": "leaf curl", "probability": 0.8}]}}}
    monkeypatch.setattr(plant_disease_client.requests, "post", lambda *a, **k: _fake_resp(201, body))

    result = plant_disease_client.identify_disease(b"img", "f1")

    assert result == {"disease": "leaf curl", "confidence": 0.8}


def test_identify_disease_accepts_200_as_success(monkeypatch):
    _with_fixed_key(monkeypatch)
    body = {"result": {"disease": {"suggestions": [{"name": "rust", "probability": 0.5}]}}}
    monkeypatch.setattr(plant_disease_client.requests, "post", lambda *a, **k: _fake_resp(200, body))

    result = plant_disease_client.identify_disease(b"img", "f1")

    assert result == {"disease": "rust", "confidence": 0.5}


def test_identify_disease_rejects_4xx(monkeypatch):
    _with_fixed_key(monkeypatch)
    monkeypatch.setattr(plant_disease_client.requests, "post", lambda *a, **k: _fake_resp(400, {}))

    assert plant_disease_client.identify_disease(b"img", "f1") is None


def test_identify_disease_rejects_5xx(monkeypatch):
    _with_fixed_key(monkeypatch)
    monkeypatch.setattr(plant_disease_client.requests, "post", lambda *a, **k: _fake_resp(503, {}))

    assert plant_disease_client.identify_disease(b"img", "f1") is None
