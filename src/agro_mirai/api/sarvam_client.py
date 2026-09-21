"""HTTP client for Sarvam AI (https://docs.sarvam.ai): speech-to-text, chat,
text-to-speech and translation for Indian languages, all over plain REST.

Why (Module 40): the "Ask by voice" chain used Gemini for the answer, which
returned 503 "high demand" on the free tier, and local AI4Bharat models for
speech, which took 30+ s per call and sounded robotic. Sarvam covers every
step natively for en/kn/te/hi in 1-3 s per call with the keys already in
``.env`` (``SARVAM_API_KEY_1..3``).

Mirrors ``cnn_client.py`` / ``gemini_client.py``'s never-raise contract: every
function returns ``None`` on any unavailability (no keys, network error,
timeout, non-200, malformed body) so callers can fall back. Keys are tried in
order; a key that is rate-limited (429), rejected (401/403) or erroring (5xx)
falls through to the next one.
"""
from __future__ import annotations

import base64
import logging
import os

import requests

logger = logging.getLogger(__name__)

_BASE = "https://api.sarvam.ai"
CHAT_MODEL = "sarvam-105b-conversations"  # non-reasoning: ~1 s. sarvam-105b thinks for 10 s+.
STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
TRANSLATE_MODEL = "sarvam-translate:v1"
TTS_CODEC = "mp3"
TTS_MIMETYPE = "audio/mpeg"

_LANG_TO_BCP47 = {"en": "en-IN", "kn": "kn-IN", "te": "te-IN", "hi": "hi-IN"}
_BCP47_TO_LANG = {v: k for k, v in _LANG_TO_BCP47.items()}
#: Bulbul rejects very long inputs; longer text is split on sentence ends.
_TTS_MAX_CHARS = 450


def sarvam_keys() -> list[str]:
    keys = [os.environ.get(f"SARVAM_API_KEY_{i}", "").strip() for i in (1, 2, 3)]
    single = os.environ.get("SARVAM_API_KEY", "").strip()
    return [k for k in [*keys, single] if k]


def sarvam_configured() -> bool:
    return bool(sarvam_keys())


def _timeout() -> float:
    try:
        return float(os.environ.get("SARVAM_TIMEOUT_S", "") or 30)
    except ValueError:
        return 30.0


def _post(path: str, *, json: dict | None = None, files=None, data=None) -> dict | None:
    """POST to Sarvam trying each key in turn. Returns the parsed JSON body of
    the first 200 response, else ``None``."""
    for key in sarvam_keys():
        try:
            resp = requests.post(
                f"{_BASE}{path}",
                headers={"api-subscription-key": key},
                json=json,
                files=files,
                data=data,
                timeout=_timeout(),
            )
        except requests.RequestException as exc:
            logger.warning("Sarvam %s: network error: %s", path, exc)
            continue
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                logger.warning("Sarvam %s: 200 but body was not JSON", path)
                return None
        logger.warning("Sarvam %s: HTTP %s %s", path, resp.status_code, resp.text[:200])
        if resp.status_code in (400, 413, 422):
            return None  # the request itself is bad; another key will not help
    return None


def sniff_audio_mimetype(data: bytes) -> str:
    """Best-effort MIME type from magic bytes (the API returns mp3 from Sarvam,
    ogg from the local voice service)."""
    if data[:4] == b"RIFF":
        return "audio/wav"
    if data[:4] == b"OggS":
        return "audio/ogg"
    if data[4:8] == b"ftyp":
        return "audio/mp4"
    return "audio/mpeg"


def ask_sarvam(system: str, user: str, max_tokens: int = 500) -> str | None:
    body = _post(
        "/v1/chat/completions",
        json={
            "model": CHAT_MODEL,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        },
    )
    if not body:
        return None
    try:
        text = (body["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        return None
    return text or None


def transcribe(audio_bytes: bytes, expected_lang: str | None = None) -> tuple[str, str] | None:
    """Returns ``(text, lang)`` with ``lang`` one of en/kn/te/hi (the requested
    ``expected_lang`` when Sarvam does not report one), or ``None``."""
    mime = sniff_audio_mimetype(audio_bytes)
    body = _post(
        "/speech-to-text",
        files={"file": ("question", audio_bytes, mime)},
        data={"model": STT_MODEL, "language_code": _LANG_TO_BCP47.get(expected_lang or "", "unknown")},
    )
    if not body:
        return None
    text = (body.get("transcript") or "").strip()
    if not text:
        return None
    lang = _BCP47_TO_LANG.get(body.get("language_code") or "", expected_lang or "en")
    return text, lang


def _split_for_tts(text: str) -> list[str]:
    import re

    parts, cur = [], ""
    for sent in re.split(r"(?<=[.!?।])\s+", text.strip()):
        if cur and len(cur) + 1 + len(sent) > _TTS_MAX_CHARS:
            parts.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        parts.append(cur)
    return parts


def synthesize(text: str, lang: str) -> bytes | None:
    """MP3 speech for ``text`` in ``lang`` (en/kn/te/hi), or ``None``. Long text
    is synthesised in sentence-sized pieces and the MP3 frames concatenated
    (MP3 streams can be joined byte-wise)."""
    code = _LANG_TO_BCP47.get(lang)
    if code is None or not text.strip():
        return None
    out = b""
    for piece in _split_for_tts(text):
        body = _post(
            "/text-to-speech",
            json={"text": piece, "target_language_code": code, "model": TTS_MODEL, "output_audio_codec": TTS_CODEC},
        )
        try:
            out += base64.b64decode(body["audios"][0])  # type: ignore[index]
        except (TypeError, KeyError, IndexError, ValueError):
            return None
    return out or None


def translate(text: str, source_lang: str, target_lang: str) -> str | None:
    src, tgt = _LANG_TO_BCP47.get(source_lang), _LANG_TO_BCP47.get(target_lang)
    if src is None or tgt is None:
        return None
    if source_lang == target_lang or not text.strip():
        return text
    body = _post(
        "/translate",
        json={"input": text, "source_language_code": src, "target_language_code": tgt, "model": TRANSLATE_MODEL},
    )
    out = ((body or {}).get("translated_text") or "").strip()
    return out or None
