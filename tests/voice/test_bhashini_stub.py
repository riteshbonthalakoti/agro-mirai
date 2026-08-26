"""Unit: BhashiniVoiceAdapter's not-blocked-on-access-clearing behavior.

Every method raises VoiceUnavailableError — with a message naming the
missing env vars when credentials aren't configured, or naming the
unimplemented HTTP client when they are. Nothing is hand-faked: there is
no code path that returns a fabricated translation/transcript/audio.
"""
import pytest

from agro_mirai.voice import BhashiniVoiceAdapter, VoiceUnavailableError
from agro_mirai.voice.bhashini_voice import _REQUIRED_ENV_VARS


def test_translate_raises_when_credentials_missing(monkeypatch):
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    adapter = BhashiniVoiceAdapter()
    with pytest.raises(VoiceUnavailableError) as exc_info:
        adapter.translate("hello", "en", "kn")
    assert "bhashini_credentials_missing" in exc_info.value.reason
    for var in _REQUIRED_ENV_VARS:
        assert var in str(exc_info.value)


def test_speech_to_text_raises_when_credentials_missing(monkeypatch):
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    adapter = BhashiniVoiceAdapter()
    with pytest.raises(VoiceUnavailableError):
        adapter.speech_to_text(b"fake-audio")


def test_text_to_speech_raises_not_implemented_once_credentials_present(monkeypatch):
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.setenv(var, "fake-value-for-test")
    adapter = BhashiniVoiceAdapter()
    with pytest.raises(VoiceUnavailableError) as exc_info:
        adapter.text_to_speech("hello", "kn")
    assert "bhashini_not_implemented" in exc_info.value.reason
