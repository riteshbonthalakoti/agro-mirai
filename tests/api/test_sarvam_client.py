"""Module 40: Sarvam AI client. The HTTP boundary (``requests.post``) is mocked:
no live Sarvam key or quota is used by the test suite."""
from __future__ import annotations

import base64
from unittest.mock import MagicMock

import pytest
import requests

from agro_mirai.api import sarvam_client as sarvam
from agro_mirai.api import voice_client


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = str(body)
    return r


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY_1", "k1")
    monkeypatch.setenv("SARVAM_API_KEY_2", "k2")


def _patch_post(monkeypatch, *responses):
    calls = []
    queue = list(responses)

    def fake(url, **kw):
        calls.append((url, kw))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(sarvam.requests, "post", fake)
    return calls


def test_no_keys_means_none_and_no_network(monkeypatch):
    calls = _patch_post(monkeypatch)
    assert not sarvam.sarvam_configured()
    assert sarvam.ask_sarvam("s", "q") is None
    assert calls == []


def test_chat_returns_text(keys, monkeypatch):
    calls = _patch_post(monkeypatch, _resp(body={"choices": [{"message": {"content": " ನೀರು ಹಾಕಿ "}}]}))
    assert sarvam.ask_sarvam("sys", "q") == "ನೀರು ಹಾಕಿ"
    url, kw = calls[0]
    assert url.endswith("/v1/chat/completions")
    assert kw["headers"]["api-subscription-key"] == "k1"
    assert kw["json"]["model"] == sarvam.CHAT_MODEL


def test_falls_through_to_second_key_on_429(keys, monkeypatch):
    calls = _patch_post(
        monkeypatch, _resp(429, {"error": "rate"}), _resp(body={"choices": [{"message": {"content": "ok"}}]})
    )
    assert sarvam.ask_sarvam("s", "q") == "ok"
    assert [c[1]["headers"]["api-subscription-key"] for c in calls] == ["k1", "k2"]


def test_network_error_tries_next_key_then_none(keys, monkeypatch):
    _patch_post(monkeypatch, requests.ConnectionError("x"), requests.Timeout("y"))
    assert sarvam.ask_sarvam("s", "q") is None


def test_bad_request_does_not_burn_other_keys(keys, monkeypatch):
    calls = _patch_post(monkeypatch, _resp(400, {"error": "bad"}))
    assert sarvam.ask_sarvam("s", "q") is None
    assert len(calls) == 1


def test_reasoning_only_reply_with_null_content_is_none(keys, monkeypatch):
    _patch_post(monkeypatch, _resp(body={"choices": [{"message": {"content": None}}]}))
    assert sarvam.ask_sarvam("s", "q") is None


def test_transcribe_maps_language_and_sniffs_mime(keys, monkeypatch):
    calls = _patch_post(monkeypatch, _resp(body={"transcript": " ನಮಸ್ಕಾರ ", "language_code": "kn-IN"}))
    m4a = b"\x00\x00\x00\x20ftypM4A " + b"\x00" * 20
    assert sarvam.transcribe(m4a, "kn") == ("ನಮಸ್ಕಾರ", "kn")
    _, kw = calls[0]
    assert kw["files"]["file"][2] == "audio/mp4"
    assert kw["data"]["language_code"] == "kn-IN"


def test_transcribe_without_expected_lang_autodetects(keys, monkeypatch):
    calls = _patch_post(monkeypatch, _resp(body={"transcript": "hello", "language_code": "en-IN"}))
    assert sarvam.transcribe(b"RIFF....WAVE", None) == ("hello", "en")
    assert calls[0][1]["data"]["language_code"] == "unknown"


def test_transcribe_empty_transcript_is_none(keys, monkeypatch):
    _patch_post(monkeypatch, _resp(body={"transcript": "  ", "language_code": "en-IN"}))
    assert sarvam.transcribe(b"RIFF", "en") is None


def test_synthesize_decodes_base64_mp3(keys, monkeypatch):
    mp3 = b"\xff\xf3\xc0\xc4" + b"\x01" * 10
    calls = _patch_post(monkeypatch, _resp(body={"audios": [base64.b64encode(mp3).decode()]}))
    assert sarvam.synthesize("ನೀರು ಹಾಕಿ.", "kn") == mp3
    assert calls[0][1]["json"]["target_language_code"] == "kn-IN"
    assert calls[0][1]["json"]["output_audio_codec"] == "mp3"


def test_synthesize_long_text_is_chunked_and_joined(keys, monkeypatch):
    long_text = " ".join(["Water the field early in the morning."] * 30)
    n = len(sarvam._split_for_tts(long_text))
    assert n > 1
    _patch_post(monkeypatch, *[_resp(body={"audios": [base64.b64encode(b"AB").decode()]}) for _ in range(n)])
    assert sarvam.synthesize(long_text, "en") == b"AB" * n


def test_synthesize_unsupported_language_is_none(keys, monkeypatch):
    calls = _patch_post(monkeypatch)
    assert sarvam.synthesize("x", "ta") is None
    assert calls == []


def test_translate(keys, monkeypatch):
    _patch_post(monkeypatch, _resp(body={"translated_text": "ನೀರು"}))
    assert sarvam.translate("water", "en", "kn") == "ನೀರು"
    assert sarvam.translate("water", "en", "en") == "water"


def test_sniff_audio_mimetype():
    assert sarvam.sniff_audio_mimetype(b"OggSxxxx") == "audio/ogg"
    assert sarvam.sniff_audio_mimetype(b"RIFFxxxxWAVE") == "audio/wav"
    assert sarvam.sniff_audio_mimetype(b"\x00\x00\x00\x20ftypM4A ") == "audio/mp4"
    assert sarvam.sniff_audio_mimetype(b"\xff\xf3\xc0\xc4") == "audio/mpeg"


# --- voice_client prefers Sarvam, falls back to the old paths ---

def test_answer_prefers_sarvam_then_gemini(monkeypatch):
    store = MagicMock()
    store.list_fields.return_value = []
    monkeypatch.setattr(voice_client.sarvam, "sarvam_configured", lambda: True)
    monkeypatch.setattr(voice_client.sarvam, "ask_sarvam", lambda s, q: "sarvam answer")
    monkeypatch.setattr(voice_client, "ask_gemini", lambda p: "gemini answer")
    assert voice_client.answer_farmer_question(store, "f", "q", "kn") == "sarvam answer"

    monkeypatch.setattr(voice_client.sarvam, "ask_sarvam", lambda s, q: None)
    assert voice_client.answer_farmer_question(store, "f", "q", "kn") == "gemini answer"


def test_transcribe_falls_back_to_voice_service(monkeypatch):
    monkeypatch.setattr(voice_client.sarvam, "sarvam_configured", lambda: True)
    monkeypatch.setattr(voice_client.sarvam, "transcribe", lambda a, e: None)
    fake = MagicMock()
    fake.speech_to_text.return_value = ("local text", "en")
    monkeypatch.setattr(voice_client, "get_remote_voice_service", lambda: fake)
    assert voice_client.transcribe_audio(b"RIFF", "en") == ("local text", "en")


def test_speak_prefers_sarvam(monkeypatch):
    monkeypatch.setattr(voice_client.sarvam, "sarvam_configured", lambda: True)
    monkeypatch.setattr(voice_client.sarvam, "synthesize", lambda t, l: b"MP3")
    monkeypatch.setattr(voice_client, "get_remote_voice_service", lambda: pytest.fail("should not be used"))
    assert voice_client.synthesize_answer_audio("hi", "en") == b"MP3"


def test_translate_prefers_sarvam(monkeypatch):
    monkeypatch.setattr(voice_client.sarvam, "sarvam_configured", lambda: True)
    monkeypatch.setattr(voice_client.sarvam, "translate", lambda t, s, g: "TR:" + t)
    monkeypatch.setattr(voice_client, "get_remote_voice_service", lambda: pytest.fail("should not be used"))
    assert voice_client.translate_text("Water now. Then rest.", "en", "kn") == "TR:Water now. Then rest."
