"""Module 23: ``/v2/advisories/{id}/audio`` and ``/v2/stt`` each have
their own rate limit, tighter than and independent of the general
per-API-key limit — same pattern as ``test_login_rate_limit.py``.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import Advisory
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from _otp_helpers import register_and_login

_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)


def _app(**rate_limits):
    store = SQLiteDataStore(":memory:")
    config = {"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"}
    config.update(rate_limits)
    return create_app(config)


def _login_and_seed_advisory(client, app):
    assert register_and_login(client, "+919000000010").status_code == 200
    field_id = client.post(
        "/v2/fields", json={"name": "P", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0}
    ).get_json()["id"]
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]

    store = app.extensions["data_store"]
    advisory = Advisory(
        id="adv-1", field_id=field_id, created_at=_NOW, language="en",
        title="t", body="b", severity="low",
    )
    store.save_advisory(farmer_id, advisory)
    return advisory.id


def test_tts_within_limit_ok(monkeypatch):
    app = _app(TTS_RATE_LIMIT="3 per minute")
    client = app.test_client()
    advisory_id = _login_and_seed_advisory(client, app)

    fake_service = MagicMock()
    fake_service.text_to_speech.return_value = b"ogg"
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service)

    for _ in range(3):
        resp = client.get(f"/v2/advisories/{advisory_id}/audio")
        assert resp.status_code == 200


def test_tts_exceeding_limit_returns_429(monkeypatch):
    app = _app(TTS_RATE_LIMIT="2 per minute")
    client = app.test_client()
    advisory_id = _login_and_seed_advisory(client, app)

    fake_service = MagicMock()
    fake_service.text_to_speech.return_value = b"ogg"
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service)

    for _ in range(2):
        client.get(f"/v2/advisories/{advisory_id}/audio")
    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 429
    assert resp.get_json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_stt_exceeding_limit_returns_429(monkeypatch):
    app = _app(STT_RATE_LIMIT="2 per minute")
    client = app.test_client()
    register_and_login(client, "+919000000011")

    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: None)

    def _post():
        return client.post(
            "/v2/stt",
            data={"audio": (io.BytesIO(b"RIFF....WAVE"), "c.wav")},
            content_type="multipart/form-data",
        )

    for _ in range(2):
        _post()
    resp = _post()
    assert resp.status_code == 429


def test_voice_rate_limit_independent_of_general_rate_limit(monkeypatch):
    app = _app(RATE_LIMIT="1000 per minute", TTS_RATE_LIMIT="1 per minute")
    client = app.test_client()
    advisory_id = _login_and_seed_advisory(client, app)

    fake_service = MagicMock()
    fake_service.text_to_speech.return_value = b"ogg"
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service)

    client.get(f"/v2/advisories/{advisory_id}/audio")
    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 429
