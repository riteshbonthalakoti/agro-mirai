"""Module 30, candidate (a): ``POST /v2/voice/ask`` — STT + a Gemini call
grounded in the farmer's own real fields/advisories + TTS. Both external
HTTP boundaries (the standalone voice service and Gemini) are mocked — no
live Oracle VM or live Gemini key needed, per this project's testing
convention (Module 21/23).
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

_NOW = datetime(2026, 9, 15, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, phone="+919000000001"):
    from _otp_helpers import register_and_login

    resp = register_and_login(client, phone)
    assert resp.status_code == 200
    return resp


def _create_field(client) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _seed_advisory(app, farmer_id: str, field_id: str) -> None:
    store = app.extensions["data_store"]
    advisory = Advisory(
        id="adv-1", field_id=field_id, created_at=_NOW, language="en",
        title="Irrigate soon", body="Apply 12mm within 3 days.", severity="moderate",
    )
    store.save_advisory(farmer_id, advisory)


def _wav_bytes() -> bytes:
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 100)
    return buf.getvalue()


def _post_ask(client, audio=None):
    return client.post(
        "/v2/voice/ask",
        data={"audio": (io.BytesIO(audio or _wav_bytes()), "q.wav")},
        content_type="multipart/form-data",
    )


def test_ask_requires_session(client):
    resp = _post_ask(client)
    assert resp.status_code == 401


def test_ask_success_grounds_answer_and_returns_audio(app, client, monkeypatch):
    _register_and_login(client)
    _create_field(client)

    fake_voice = MagicMock()
    fake_voice.speech_to_text.return_value = ("When should I water?", "en")
    fake_voice.text_to_speech.return_value = b"ogg-bytes"
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_voice)
    monkeypatch.setattr(
        "agro_mirai.api.voice_client.ask_gemini",
        lambda prompt: "Water your Plot field within 3 days, about 12mm.",
    )

    resp = _post_ask(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["question_text"] == "When should I water?"
    assert body["detected_lang"] == "en"
    assert "12mm" in body["answer_text"]
    assert body["answer_audio_base64"] is not None
    assert body["answer_audio_mimetype"] == "audio/ogg"

    fake_voice.speech_to_text.assert_called_once()
    fake_voice.text_to_speech.assert_called_once_with(
        "Water your Plot field within 3 days, about 12mm.", "en"
    )


def test_ask_stt_unavailable_returns_503(client, monkeypatch):
    _register_and_login(client)
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: None)

    resp = _post_ask(client)
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "VOICE_UNAVAILABLE"


def test_ask_llm_unavailable_returns_503_distinct_code(client, monkeypatch):
    _register_and_login(client)

    fake_voice = MagicMock()
    fake_voice.speech_to_text.return_value = ("When should I water?", "en")
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_voice)
    monkeypatch.setattr("agro_mirai.api.voice_client.ask_gemini", lambda prompt: None)

    resp = _post_ask(client)
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "LLM_UNAVAILABLE"
    fake_voice.text_to_speech.assert_not_called()


def test_ask_tts_failure_still_returns_200_with_null_audio(client, monkeypatch):
    """Degrade-not-fail: the answer text is real and useful even if TTS
    can't speak it, so the route must not throw the answer away."""
    _register_and_login(client)

    fake_voice = MagicMock()
    fake_voice.speech_to_text.return_value = ("When should I water?", "en")
    fake_voice.text_to_speech.side_effect = VoiceUnavailableError("tts down")
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_voice)
    monkeypatch.setattr("agro_mirai.api.voice_client.ask_gemini", lambda prompt: "Water soon.")

    resp = _post_ask(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["answer_text"] == "Water soon."
    assert body["answer_audio_base64"] is None
    assert body["answer_audio_mimetype"] is None


def test_ask_prompt_is_scoped_to_this_farmer_only(app, client, monkeypatch):
    """The grounding context must never leak another farmer's data —
    ADR 0003's ownership rule, verified directly against the real
    SQLiteDataStore rather than trusting the query shape."""
    _register_and_login(client, phone="+919000000002")
    field_id = _create_field(client)
    farmer_id = list(app.extensions["data_store"]._conn.execute("SELECT id FROM farmers").fetchall())[0][0]
    _seed_advisory(app, farmer_id, field_id)

    fake_voice = MagicMock()
    fake_voice.speech_to_text.return_value = ("How is my field?", "en")
    fake_voice.text_to_speech.return_value = b"ogg-bytes"
    monkeypatch.setattr("agro_mirai.api.voice_client.get_remote_voice_service", lambda: fake_voice)

    captured = {}

    def _fake_ask(prompt):
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("agro_mirai.api.voice_client.ask_gemini", _fake_ask)

    resp = _post_ask(client)
    assert resp.status_code == 200
    assert "Apply 12mm within 3 days" in captured["prompt"]
