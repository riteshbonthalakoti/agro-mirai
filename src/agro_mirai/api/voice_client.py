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

from agro_mirai.api.gemini_client import ask_gemini
from agro_mirai.persistence.models import Advisory
from agro_mirai.voice.interface import VoiceUnavailableError
from agro_mirai.voice.remote_voice import RemoteVoiceService

_MAX_FIELDS_IN_PROMPT = 5
_MAX_ADVISORIES_PER_FIELD = 1

_LANGUAGE_NAMES = {"en": "English", "kn": "Kannada", "te": "Telugu", "hi": "Hindi"}


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


def translate_text(text: str, source_lang: str, target_lang: str) -> str | None:
    """Never-raise translate for arbitrary short server-generated English
    text (Module 34 follow-up): reuses the same ``RemoteVoiceService``/
    IndicTrans2 path ``synthesize_advisory_audio`` already calls, rather
    than building a second translation call. Returns ``None`` on any
    voice-service unavailability, so callers apply the same degrade-not-
    fail pattern (fall back to the original English text) as every other
    voice-service call in this module."""
    if source_lang == target_lang:
        return text
    service = get_remote_voice_service()
    if service is None:
        return None
    try:
        return service.translate(text, source_lang, target_lang)
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


def _build_grounded_context(store, farmer_id: str) -> str:
    """Renders this farmer's own fields + latest advisory per field into
    plain text for the Gemini prompt — the "grounded in this app's own
    data, not a generic LLM answer" requirement from Module 30's research.
    Farmer-scoped only: every read here goes through the same
    ``farmer_id``-scoped ``DataStore`` methods every other route uses, so
    one farmer's question can never pull another farmer's data into the
    prompt (ADR 0003's ownership rule, unchanged)."""
    fields = store.list_fields(farmer_id, limit=_MAX_FIELDS_IN_PROMPT)
    if not fields:
        return "This farmer has no fields registered yet."

    lines = []
    for field in fields:
        advisories = store.list_advisories_for_field(farmer_id, field.id, limit=_MAX_ADVISORIES_PER_FIELD)
        line = f"- Field '{field.name}' (crop: {field.current_crop or 'unknown'})"
        if advisories:
            latest = advisories[0]
            line += f". Latest advisory (severity {latest.severity}): {latest.body}"
        lines.append(line)
    return "\n".join(lines)


def synthesize_answer_audio(text: str, language: str) -> bytes | None:
    """Never-raise TTS for a Gemini answer (Module 30) — same contract as
    ``synthesize_advisory_audio``, minus the Advisory-specific translate
    step since the answer is already generated in ``language``."""
    service = get_remote_voice_service()
    if service is None:
        return None
    try:
        return service.text_to_speech(text, language)
    except VoiceUnavailableError:
        return None


def answer_farmer_question(store, farmer_id: str, question_text: str, language: str) -> str | None:
    """Grounds ``question_text`` in this farmer's real field/advisory data
    and asks Gemini for a spoken-style answer in ``language``. Returns
    ``None`` on any Gemini unavailability (unset key, unreachable, timeout,
    blocked response) — the never-raise contract every external call in
    this project follows, so the route can return a client-distinguishable
    503 instead of a bare 500."""
    context = _build_grounded_context(store, farmer_id)
    language_name = _LANGUAGE_NAMES.get(language, language)
    prompt = (
        "You are AGRO MIRAI, a farm advisory assistant for a smallholder farmer in India. "
        "Answer the farmer's question using ONLY the real data below about their own fields "
        "and advisories. Keep the answer short (2-4 sentences), practical, and in plain "
        f"{language_name}, since it will be read aloud to the farmer. If the data below "
        "doesn't cover the question, say so honestly instead of guessing.\n\n"
        f"Farmer's data:\n{context}\n\n"
        f"Farmer's question: {question_text}"
    )
    return ask_gemini(prompt)
