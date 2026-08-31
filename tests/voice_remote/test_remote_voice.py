"""Tests for RemoteVoiceService (Module 21) — HTTP boundary mocked via
unittest.mock.patch on `requests.post`, no live services/voice container
needed. Fast, runs in the main pytest suite (not gated behind .venv/
like the other tests/voice/ files, since this adapter itself has no
torch dependency)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agro_mirai.voice.interface import VoiceUnavailableError
from agro_mirai.voice.remote_voice import RemoteVoiceService


def test_requires_base_url():
    with pytest.raises(VoiceUnavailableError):
        RemoteVoiceService(base_url="")


def test_translate_success():
    service = RemoteVoiceService(base_url="http://voice.local:8002")
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {"text": "ನಮಸ್ಕಾರ"}
    with patch("agro_mirai.voice.remote_voice.requests.post", return_value=fake_resp) as mock_post:
        result = service.translate("hello", "en", "kn")
    assert result == "ನಮಸ್ಕಾರ"
    assert mock_post.call_args.kwargs["json"] == {"text": "hello", "source_lang": "en", "target_lang": "kn"}


def test_translate_unreachable_raises_voice_unavailable():
    import requests

    service = RemoteVoiceService(base_url="http://voice.local:8002")
    with patch("agro_mirai.voice.remote_voice.requests.post", side_effect=requests.ConnectionError("refused")):
        with pytest.raises(VoiceUnavailableError):
            service.translate("hello", "en", "kn")


def test_translate_non_200_raises_voice_unavailable():
    service = RemoteVoiceService(base_url="http://voice.local:8002")
    fake_resp = MagicMock(status_code=503, text="degraded")
    with patch("agro_mirai.voice.remote_voice.requests.post", return_value=fake_resp):
        with pytest.raises(VoiceUnavailableError):
            service.translate("hello", "en", "kn")


def test_speech_to_text_success():
    service = RemoteVoiceService(base_url="http://voice.local:8002")
    fake_resp = MagicMock(status_code=200)
    fake_resp.json.return_value = {"text": "hello", "detected_lang": "en"}
    with patch("agro_mirai.voice.remote_voice.requests.post", return_value=fake_resp) as mock_post:
        text, lang = service.speech_to_text(b"audio-bytes", expected_lang="en")
    assert (text, lang) == ("hello", "en")
    assert mock_post.call_args.kwargs["data"] == {"expected_lang": "en"}


def test_text_to_speech_success():
    service = RemoteVoiceService(base_url="http://voice.local:8002")
    fake_resp = MagicMock(status_code=200, content=b"RIFF....WAVEfmt ")
    with patch("agro_mirai.voice.remote_voice.requests.post", return_value=fake_resp):
        audio = service.text_to_speech("hello", "en")
    assert audio.startswith(b"RIFF")
