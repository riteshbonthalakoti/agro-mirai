"""Module 23 Part B: ``GET /v2/advisories/{id}/audio`` and ``POST
/v2/stt``. The voice service HTTP boundary
(``agro_mirai.api.voice_client.get_remote_voice_service``) is mocked — no
live Oracle VM needed, per this module's own testing requirement.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import Advisory
from agro_mirai.persistence.sqlite_store import SQLiteDataStore
from agro_mirai.voice.interface import VoiceUnavailableError

from conftest import make_jwt

_NOW = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)
_next_farmer_id = iter(
    f"dddddddd-{n:04d}-4000-8000-0000000000d1" for n in range(1, 1000)
)


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, email="farmer@example.com", password="Sup3rSecret1"):
    """Module 26: no more /v2/auth/register|login — mints a JWT for a
    fresh Supabase-user-id and sets it as the test client's default
    Authorization header (Werkzeug's environ_base), so every subsequent
    request from this client authenticates as this farmer without
    threading headers through every call site individually — the same
    "log in once, stay logged in" ergonomics the old cookie-jar gave
    these tests, now backed by a bearer token instead of a session
    cookie."""
    token = make_jwt(next(_next_farmer_id), email=email)
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"


def _create_field(client) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _seed_advisory(app, farmer_id: str, field_id: str) -> str:
    store = app.extensions["data_store"]
    advisory = Advisory(
        id="adv-1", field_id=field_id, created_at=_NOW, language="en",
        title="Irrigate soon", body="Apply 12mm within 3 days.", severity="moderate",
    )
    store.save_advisory(farmer_id, advisory)
    return advisory.id


# --- TTS: GET /v2/advisories/{id}/audio ---

def test_audio_requires_session(client):
    resp = client.get("/v2/advisories/does-not-matter/audio")
    assert resp.status_code == 401


def test_audio_unknown_advisory_404(client):
    _register_and_login(client)
    resp = client.get("/v2/advisories/does-not-exist/audio")
    assert resp.status_code == 404


def test_audio_success_returns_ogg_with_caching_headers(app, client, monkeypatch):
    resp_login = _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    fake_service = MagicMock()
    fake_service.text_to_speech.return_value = b"fake-ogg-bytes"
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 200
    assert resp.content_type == "audio/ogg"
    assert resp.data == b"fake-ogg-bytes"
    assert resp.headers.get("ETag")
    assert "max-age" in resp.headers.get("Cache-Control", "")
    # Advisory is in English; requested language defaults to the farmer's
    # preferred_language (also "en" here), so no translate hop needed.
    fake_service.translate.assert_not_called()
    fake_service.text_to_speech.assert_called_once()
    assert fake_service.text_to_speech.call_args.args[1] == "en"


def test_audio_translates_when_language_override_differs(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    fake_service = MagicMock()
    fake_service.translate.return_value = "ಬೇಗ ನೀರಾವರಿ ಮಾಡಿ."
    fake_service.text_to_speech.return_value = b"fake-kn-ogg-bytes"
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.get(f"/v2/advisories/{advisory_id}/audio?language=kn")
    assert resp.status_code == 200
    fake_service.translate.assert_called_once_with(
        "Irrigate soon. Apply 12mm within 3 days.", "en", "kn"
    )
    fake_service.text_to_speech.assert_called_once_with("ಬೇಗ ನೀರಾವರಿ ಮಾಡಿ.", "kn")


@pytest.mark.parametrize("lang", ["te", "hi"])
def test_audio_translates_for_new_v1_languages(app, client, monkeypatch, lang):
    # Module 25: te/hi weren't valid overrides before V1_LANGUAGES widened.
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    fake_service = MagicMock()
    fake_service.translate.return_value = "translated"
    fake_service.text_to_speech.return_value = b"fake-ogg-bytes"
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.get(f"/v2/advisories/{advisory_id}/audio?language={lang}")
    assert resp.status_code == 200
    fake_service.translate.assert_called_once_with(
        "Irrigate soon. Apply 12mm within 3 days.", "en", lang
    )
    fake_service.text_to_speech.assert_called_once_with("translated", lang)


def test_audio_invalid_language_override_400(app, client):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    resp = client.get(f"/v2/advisories/{advisory_id}/audio?language=fr")
    assert resp.status_code == 400


def test_audio_etag_revalidation_returns_304(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    fake_service = MagicMock()
    fake_service.text_to_speech.return_value = b"fake-ogg-bytes"
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    first = client.get(f"/v2/advisories/{advisory_id}/audio")
    etag = first.headers["ETag"]

    second = client.get(f"/v2/advisories/{advisory_id}/audio", headers={"If-None-Match": etag})
    assert second.status_code == 304
    # Only the first request should have actually called the voice service.
    fake_service.text_to_speech.assert_called_once()


def test_audio_cross_tenant_404(app, client):
    _register_and_login(client, "farmerA@example.com", "Sup3rSecret1")
    field_id = _create_field(client)
    farmer_a_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_a_id, field_id)

    _register_and_login(client, "farmerB@example.com", "Sup3rSecret2")
    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 404


def test_audio_voice_service_unreachable_returns_503_distinguishable_error(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    fake_service = MagicMock()
    fake_service.text_to_speech.side_effect = VoiceUnavailableError("connection refused")
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_audio_no_voice_service_configured_returns_503(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = client.get("/v2/farmers/me").get_json()["id"]
    advisory_id = _seed_advisory(app, farmer_id, field_id)

    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: None)

    resp = client.get(f"/v2/advisories/{advisory_id}/audio")
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "VOICE_UNAVAILABLE"


# --- STT: POST /v2/stt ---

def _wav_bytes() -> bytes:
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def test_stt_requires_session(client):
    resp = client.post("/v2/stt", data={}, content_type="multipart/form-data")
    assert resp.status_code == 401


def test_stt_missing_audio_400(client):
    _register_and_login(client)
    resp = client.post("/v2/stt", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_stt_non_audio_bytes_rejected_400(client):
    _register_and_login(client)
    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(b"not audio at all"), "clip.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_stt_success(client, monkeypatch):
    _register_and_login(client)
    fake_service = MagicMock()
    fake_service.speech_to_text.return_value = ("water the field", "en")
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["text"] == "water the field"
    assert body["detected_lang"] == "en"


@pytest.mark.parametrize("lang", ["te", "hi"])
def test_stt_accepts_new_v1_expected_lang(client, monkeypatch, lang):
    _register_and_login(client)
    fake_service = MagicMock()
    fake_service.speech_to_text.return_value = ("recognized", lang)
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_service
    )

    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav"), "expected_lang": lang},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["detected_lang"] == lang


def test_stt_invalid_expected_lang_400(client):
    _register_and_login(client)
    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav"), "expected_lang": "fr"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_stt_voice_service_unreachable_returns_503(client, monkeypatch):
    _register_and_login(client)
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: None)

    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_stt_oversized_audio_rejected_400(client, monkeypatch):
    _register_and_login(client)
    import agro_mirai.api.stt_validation as stt_validation

    monkeypatch.setattr(stt_validation, "MAX_AUDIO_BYTES", 10)
    resp = client.post(
        "/v2/stt",
        data={"audio": (io.BytesIO(_wav_bytes()), "clip.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "size limit" in resp.get_json()["error"]["message"]
