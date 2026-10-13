"""Tier fallback for kn/te voice (Module 58): agro-mirai-voice-heavy
first, Sarvam second, None (caller shows text instead) third. en/hi are
untouched by this module (still Sarvam-then-light-service) -- not
re-tested here, no behavior change.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from agro_mirai.api import voice_client
from agro_mirai.voice.interface import VoiceUnavailableError


def _clear_caches():
    voice_client._TRANSLATION_CACHE.clear()
    voice_client._AUDIO_CACHE.clear()


def test_speak_kn_tier1_heavy_service_used_when_healthy():
    _clear_caches()
    heavy = MagicMock()
    heavy.text_to_speech.return_value = b"heavy-audio"
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=True), \
         patch.object(voice_client.sarvam, "synthesize") as sarvam_synth:
        audio = voice_client._speak("ನಮಸ್ಕಾರ", "kn")
    assert audio == b"heavy-audio"
    sarvam_synth.assert_not_called()  # tier 1 served it, tier 2 never tried


def test_speak_kn_tier2_sarvam_used_when_heavy_down():
    _clear_caches()
    heavy = MagicMock()
    heavy.text_to_speech.side_effect = VoiceUnavailableError("502")
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=True), \
         patch.object(voice_client.sarvam, "synthesize", return_value=b"sarvam-audio"):
        audio = voice_client._speak("ನಮಸ್ಕಾರ", "kn")
    assert audio == b"sarvam-audio"


def test_speak_kn_tier3_none_when_both_down():
    _clear_caches()
    heavy = MagicMock()
    heavy.text_to_speech.side_effect = VoiceUnavailableError("502")
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=True), \
         patch.object(voice_client.sarvam, "synthesize", return_value=None):
        audio = voice_client._speak("ನಮಸ್ಕಾರ", "kn")
    assert audio is None


def test_speak_te_same_tiering_as_kn():
    _clear_caches()
    heavy = MagicMock()
    heavy.text_to_speech.return_value = b"heavy-audio-te"
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy):
        audio = voice_client._speak("నమస్కారం", "te")
    assert audio == b"heavy-audio-te"


def test_translate_tier1_heavy_used_when_healthy():
    _clear_caches()
    heavy = MagicMock()
    heavy.translate.return_value = "ನಮಸ್ಕಾರ"
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=True) as sarvam_cfg:
        result = voice_client.translate_text("hello", "en", "kn")
    assert result == "ನಮಸ್ಕಾರ"
    sarvam_cfg.assert_not_called()


def test_translate_tier2_sarvam_used_when_heavy_down():
    _clear_caches()
    heavy = MagicMock()
    heavy.translate.side_effect = VoiceUnavailableError("502")
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=heavy), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=True), \
         patch.object(voice_client.sarvam, "translate", return_value="ನಮಸ್ಕಾರ"):
        result = voice_client.translate_text("hello", "en", "kn")
    assert result == "ನಮಸ್ಕಾರ"


def test_translate_tier3_none_when_both_down():
    _clear_caches()
    with patch.object(voice_client, "get_remote_voice_service_heavy", return_value=None), \
         patch.object(voice_client.sarvam, "sarvam_configured", return_value=False):
        result = voice_client.translate_text("hello", "en", "kn")
    assert result is None
