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

from agro_mirai.api import sarvam_client as sarvam
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


_TRANSLATION_CACHE: dict[tuple[str, str, str], str] = {}
_AUDIO_CACHE: dict[tuple[str, str], bytes] = {}
_PARA_BREAK = chr(10) * 2
_MAX_CHUNK_CHARS = 180  # IndicTrans2 handles short inputs best; long ones can 422


def _chunks(paragraph: str) -> list[str]:
    import re

    sentences = re.split(r"(?<=[.!?;])\s+", paragraph.strip())
    out, cur = [], ""
    for sent in sentences:
        if cur and len(cur) + 1 + len(sent) > _MAX_CHUNK_CHARS:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


_SARVAM_TRANSLATE_CHUNK = 800


def _sarvam_translate(text: str, source_lang: str, target_lang: str) -> str | None:
    """Sarvam translation (~1 s per call vs. tens of seconds locally). Works
    paragraph by paragraph; if any piece fails the whole thing returns
    ``None`` so the caller falls back to the local IndicTrans2 path rather than
    mixing languages in one text."""
    if not sarvam.sarvam_configured():
        return None
    paragraphs = []
    for para in text.split(_PARA_BREAK):
        pieces = []
        for part in _sarvam_pieces(para):
            tr = sarvam.translate(part, source_lang, target_lang)
            if tr is None:
                return None
            pieces.append(tr)
        paragraphs.append(" ".join(pieces))
    return _PARA_BREAK.join(paragraphs)


def _sarvam_pieces(paragraph: str) -> list[str]:
    import re

    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?;])\s+", paragraph.strip()):
        if cur and len(cur) + 1 + len(sent) > _SARVAM_TRANSLATE_CHUNK:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out or [""]


def translate_text(text: str, source_lang: str, target_lang: str) -> str | None:
    """Never-raise translate of server-generated English text (Module 34
    follow-up, reworked in Module 39): reuses ``RemoteVoiceService``/IndicTrans2.
    Long text is split into paragraphs and sentence-sized chunks (a whole
    advisory in one call was rejected with 422) and every result is cached in
    memory, so a repeat request is instant. Returns ``None`` on any
    voice-service unavailability so callers fall back to the original text."""
    if source_lang == target_lang or not text.strip():
        return text
    key = (text, source_lang, target_lang)
    if key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[key]
    sarvam_result = _sarvam_translate(text, source_lang, target_lang)
    if sarvam_result is not None:
        _TRANSLATION_CACHE[key] = sarvam_result
        return sarvam_result
    service = get_remote_voice_service()
    if service is None:
        return None
    try:
        paragraphs = []
        for para in text.split(_PARA_BREAK):
            pieces = [service.translate(c, source_lang, target_lang) for c in _chunks(para)]
            paragraphs.append(" ".join(pieces))
        result = _PARA_BREAK.join(paragraphs)
    except VoiceUnavailableError:
        return None
    _TRANSLATION_CACHE[key] = result
    return result


def synthesize_advisory_audio(advisory: Advisory, language: str) -> bytes | None:
    """Spoken audio for ``advisory`` in ``language`` (plain-language text,
    translated when ``language`` differs from the advisory's own), or ``None``
    if the voice service is unavailable. Audio is cached per (advisory, language)."""
    from agro_mirai.api.farmer_text import plain_advisory

    cache_key = (advisory.id, language)
    if cache_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[cache_key]
    text = f"{advisory.title}. {plain_advisory(advisory.body)}"
    if language != advisory.language:
        text = translate_text(text, advisory.language, language)
        if text is None:
            return None
    audio = _speak(text, language)
    if audio is None:
        return None
    _AUDIO_CACHE[cache_key] = audio
    return audio


def _speak(text: str, language: str) -> bytes | None:
    """Sarvam Bulbul first (~1 s, natural voice), local Piper/VITS second."""
    audio = sarvam.synthesize(text, language) if sarvam.sarvam_configured() else None
    if audio is not None:
        return audio
    service = get_remote_voice_service()
    if service is None:
        return None
    try:
        return service.text_to_speech(text, language)
    except VoiceUnavailableError:
        return None


def transcribe_audio(audio_bytes: bytes, expected_lang: str | None = None) -> tuple[str, str] | None:
    """Returns ``(text, detected_lang)``, or ``None`` if the voice service
    is not configured/reachable. Sarvam first, the voice service second."""
    if sarvam.sarvam_configured():
        result = sarvam.transcribe(audio_bytes, expected_lang)
        if result is not None:
            return result
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
    return _speak(text, language)


def answer_farmer_question(store, farmer_id: str, question_text: str, language: str) -> str | None:
    """Grounds ``question_text`` in this farmer's real field/advisory data
    and asks Gemini for a spoken-style answer in ``language``. Returns
    ``None`` on any Gemini unavailability (unset key, unreachable, timeout,
    blocked response) — the never-raise contract every external call in
    this project follows, so the route can return a client-distinguishable
    503 instead of a bare 500."""
    context = _build_grounded_context(store, farmer_id)
    language_name = _LANGUAGE_NAMES.get(language, language)
    system = (
        "You are AGRO MIRAI, a farm advisory assistant for a smallholder farmer in India. "
        "Answer the farmer's question using ONLY the real data below about their own fields "
        "and advisories. Keep the answer short (2-4 sentences), practical, and in plain "
        f"{language_name}, since it will be read aloud to the farmer. Do not use markdown, "
        "lists or symbols. If the data below doesn't cover the question, say so honestly "
        f"instead of guessing.\n\nFarmer's data:\n{context}"
    )
    if sarvam.sarvam_configured():
        answer = sarvam.ask_sarvam(system, question_text)
        if answer is not None:
            return answer
    return ask_gemini(f"{system}\n\nFarmer's question: {question_text}")
