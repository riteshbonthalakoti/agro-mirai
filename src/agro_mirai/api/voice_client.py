"""Main-API-side client for the standalone voice service
(``services/voice``), Module 23 (Blocker B).

Mirrors ``agro_mirai.api.cnn_client``'s never-raise contract: every
function here returns ``None`` on any unavailability (unset
``VOICE_SERVICE_URL``, unreachable, timeout, malformed response) instead
of raising, so route handlers can apply the hard "return a documented,
client-distinguishable degradation response, never a bare 500" contract
without a try/except at every call site. Talks to the service only via
``agro_mirai.voice.remote_voice.RemoteVoiceService`` — an HTTP client, so
AI4Bharat/torch are never imported into this process
(decisions/0019-deployment-architecture.md).
"""
from __future__ import annotations

import os

from agro_mirai.persistence.models import Advisory
from agro_mirai.voice.interface import VoiceUnavailableError
from agro_mirai.voice.remote_voice import RemoteVoiceService


def voice_service_configured() -> bool:
    return bool(os.environ.get("VOICE_SERVICE_URL", "").strip())


def get_remote_voice_service() -> RemoteVoiceService | None:
    if not voice_service_configured():
        return None
    try:
        return RemoteVoiceService()
    except VoiceUnavailableError:
        return None


def synthesize_advisory_audio(advisory: Advisory, language: str) -> bytes | None:
    """Returns spoken audio (whatever format ``services/voice`` returns,
    see ``ADVISORY_AUDIO_MIMETYPE`` in ``routes/voice_v2.py``) for
    ``advisory`` in ``language``, or ``None`` if the voice service is not
    configured/reachable. Translates first when ``language`` differs from
    the language the advisory was generated in — ``Advisory.body`` is
    always in one fixed language (``ExplanationService``'s ``summary_en``
    concatenation, see ADR 0011), so speaking it in a different language
    needs a translate hop before TTS.
    """
    service = get_remote_voice_service()
    if service is None:
        return None

    text = f"{advisory.title}. {advisory.body}"
    try:
        if language != advisory.language:
            text = service.translate(text, advisory.language, language)
        return service.text_to_speech(text, language)
    except VoiceUnavailableError:
        return None


def transcribe_audio(audio_bytes: bytes, expected_lang: str | None = None) -> tuple[str, str] | None:
    """Returns ``(text, detected_lang)``, or ``None`` if the voice service
    is not configured/reachable."""
    service = get_remote_voice_service()
    if service is None:
        return None
    try:
        return service.speech_to_text(audio_bytes, expected_lang)
    except VoiceUnavailableError:
        return None
