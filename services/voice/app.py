"""Voice inference service — standalone Flask app wrapping
``AI4BharatVoiceService`` (Module 12) behind HTTP, Module 21.

Decision: KEEP AI4Bharat rather than switch to faster-whisper + Kokoro —
see decisions/0019-deployment-architecture.md section 3 for the full
reasoning; short version: Kokoro TTS does not support Kannada as of 2026
(confirmed via web search — Kannada is absent from its 8-language set),
which is a hard blocker for this project's v1 language scope
(specs/core/voice-interface.md's V1_LANGUAGES = {en, kn}), and
faster-whisper is a Whisper reimplementation with the same language
coverage as the whisper-tiny.en already used for English ASR — it would
not add Kannada ASR quality the way IndicConformer already provides. This
container solves the actual problem the local .venv/ workaround existed
for (transformers 4.49.0 pin conflicting with the main app's dependency
set) by moving the isolation boundary from "python virtualenv on one
machine" to "separate container" — a real production improvement, not
just a repackaging.

Endpoints adapt to the VoiceService Protocol shape 1:1:
- POST /translate      {text, source_lang, target_lang} -> {text}
- POST /speech-to-text  multipart audio file + expected_lang (optional)
                        -> {text, detected_lang}
- POST /text-to-speech  {text, lang} -> OGG/Vorbis audio bytes (audio/ogg,
                        transcoded here from Piper's native WAV via
                        ffmpeg — Module 23)
- GET /health           mirrors the main API's health route shape

STT fallback chain (Module 39): cloud APIs are tried first so the heavy
AI4Bharat model doesn't need to be loaded just for transcription. Order:
  1. Groq  (GROQ_API_KEY_1..3)   — whisper-large-v3-turbo, 2000 req/day, free, no card
  2. Sarvam AI  (SARVAM_API_KEY_1..3) — native te/kn/hi/en support, 500/day, free, no card
  3. AI4Bharat local — always available, no quota, but needs torch weights

The model is loaded lazily (first request), same pattern as the CNN
service, so /health responds even before AI4Bharat's ~6.8GB of weights
have finished downloading/caching on first boot.
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests as http_requests
from flask import Flask, Response, jsonify, request

logger = logging.getLogger(__name__)

_service = None
_service_load_error: str | None = None

# ---------------------------------------------------------------------------
# STT cloud fallback helpers (Module 39)
# ---------------------------------------------------------------------------

_GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3"),
]
_SARVAM_KEYS = [
    os.environ.get("SARVAM_API_KEY_1"),
    os.environ.get("SARVAM_API_KEY_2"),
    os.environ.get("SARVAM_API_KEY_3"),
]

# Map our internal lang codes to Sarvam's BCP-47 codes
_SARVAM_LANG = {"te": "te-IN", "kn": "kn-IN", "hi": "hi-IN", "en": "en-IN"}


def _groq_stt(audio_bytes: bytes, filename: str, api_key: str) -> str:
    """Transcribe via Groq Whisper (openai-compat multipart upload).
    Raises on any non-200 or network error."""
    resp = http_requests.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (filename, audio_bytes, "audio/mpeg")},
        data={"model": "whisper-large-v3-turbo", "response_format": "text"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text.strip()



def _sarvam_stt(audio_bytes: bytes, filename: str, api_key: str, expected_lang: str | None) -> str:
    """Transcribe via Sarvam AI (native Indian language support).
    Sarvam accepts M4A/AAC/WAV/OGG directly — no conversion needed.
    Use 'unknown' for auto-detect when lang is uncertain.
    Raises on any non-200 or network error."""
    lang_code = _SARVAM_LANG.get(expected_lang or "", "unknown")
    # Sarvam rejects requests without an explicit MIME type on the file part
    mime = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
    resp = http_requests.post(
        "https://api.sarvam.ai/speech-to-text",
        headers={"api-subscription-key": api_key},
        files={"file": (filename, io.BytesIO(audio_bytes), mime)},
        data={"language_code": lang_code, "model": "saaras:v3"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("transcript", "").strip()


def _cloud_stt(audio_bytes: bytes, audio_filename: str, expected_lang: str | None) -> str | None:
    """Try all 9 cloud keys in order: 3 Groq → 3 OpenRouter → 3 Sarvam.
    Returns the transcript string on first success, or None if all 9 fail
    (callers fall back to AI4Bharat local STT in that case)."""
    # Groq
    for key in _GROQ_KEYS:
        if not key:
            continue
        try:
            text = _groq_stt(audio_bytes, audio_filename, key)
            if text:
                logger.info("STT: Groq succeeded")
                return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("STT Groq key failed: %s", exc)

    # Sarvam AI
    for key in _SARVAM_KEYS:
        if not key:
            continue
        try:
            text = _sarvam_stt(audio_bytes, audio_filename, key, expected_lang)
            if text:
                logger.info("STT: Sarvam succeeded")
                return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("STT Sarvam key failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------


def _transcode_wav_to_ogg(wav_bytes: bytes) -> bytes:
    """Module 23: the main API's ``/v2/advisories/{id}/audio`` needs a
    mobile-friendly compressed format, not raw WAV — transcoding happens
    here, in this already-heavy container, rather than adding an audio
    dependency to the main API process (decisions/0019's isolation
    boundary). OGG/Vorbis was chosen over MP3: ffmpeg's built-in libvorbis
    encoder needs no extra codec install, unlike libmp3lame — see
    decisions/0020's "TTS endpoint shape" section. Raises ``RuntimeError``
    if ``ffmpeg`` isn't on ``PATH`` (this container's Dockerfile always
    installs it — see the ``apt-get install ffmpeg`` line there); a bare
    local run without it fails loudly instead of silently mislabeling WAV
    bytes as OGG.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to transcode TTS audio to OGG but is not on PATH")

    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "in.wav"
        ogg_path = Path(tmp) / "out.ogg"
        wav_path.write_bytes(wav_bytes)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libvorbis", "-q:a", "4", str(ogg_path)],
            check=True,
            capture_output=True,
        )
        return ogg_path.read_bytes()


def _normalize_audio_to_wav(audio_bytes: bytes) -> bytes:
    """Module 39: the phone records AAC in an MP4 (M4A) container -- the only
    format expo-audio can produce on Android -- but STT decodes with
    libsndfile, which reads WAV/OGG/FLAC/MP3 and not AAC. Anything that is not
    already WAV/OGG is converted to 16 kHz mono WAV with ffmpeg first. Raises
    ``RuntimeError`` if conversion is needed but ffmpeg is missing/fails."""
    if audio_bytes[:4] == b"RIFF" or audio_bytes[:4] == b"OggS":
        return audio_bytes
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to decode this audio format but is not on PATH")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.bin"
        dst = Path(tmp) / "out.wav"
        src.write_bytes(audio_bytes)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)],
            check=True,
            capture_output=True,
        )
        return dst.read_bytes()


# ---------------------------------------------------------------------------
# AI4Bharat local service (lazy load)
# ---------------------------------------------------------------------------


def _get_service():
    global _service, _service_load_error
    if _service is not None:
        return _service
    if _service_load_error is not None:
        raise RuntimeError(_service_load_error)
    try:
        from agro_mirai.voice.ai4bharat_voice import AI4BharatVoiceService

        _service = AI4BharatVoiceService()
        return _service
    except Exception as exc:  # noqa: BLE001
        _service_load_error = str(exc)
        raise


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------


def create_app(service_factory=None) -> Flask:
    """``service_factory``, if given, overrides ``_get_service`` — used by
    tests to inject a stub VoiceService without needing torch/AI4Bharat
    weights installed."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

    get_service = service_factory or _get_service

    @app.get("/health")
    def health():
        try:
            get_service()
            return jsonify({"status": "ok"}), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify({"status": "degraded", "detail": str(exc)}), 200

    @app.post("/translate")
    def translate():
        body = request.get_json(silent=True) or {}
        for field in ("text", "source_lang", "target_lang"):
            if field not in body:
                return jsonify({"error": {"code": "BAD_REQUEST", "message": f"{field} is required"}}), 400
        try:
            service = get_service()
            result = service.translate(body["text"], body["source_lang"], body["target_lang"])
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "VOICE_ERROR", "message": str(exc)}}), 422
        return jsonify({"text": result}), 200

    @app.post("/speech-to-text")
    def speech_to_text():
        if "audio" not in request.files:
            return jsonify({"error": {"code": "BAD_REQUEST", "message": "audio file is required"}}), 400
        expected_lang = request.form.get("expected_lang") or None
        audio_file = request.files["audio"]
        audio_bytes = audio_file.read()
        filename = audio_file.filename or "audio.wav"

        # --- Cloud fallback chain (Groq → OpenRouter → Sarvam) ---
        # Try cloud first; only load the heavy AI4Bharat model if all 9 keys fail.
        # Audio is sent as-is to cloud APIs (they handle M4A/AAC natively).
        cloud_result = _cloud_stt(audio_bytes, filename, expected_lang)
        if cloud_result:
            detected = expected_lang or "en"
            return jsonify({"text": cloud_result, "detected_lang": detected}), 200

        # --- AI4Bharat local fallback ---
        try:
            service = get_service()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "MODEL_UNAVAILABLE", "message": str(exc)}}), 503

        try:
            wav_bytes = _normalize_audio_to_wav(audio_bytes)
            text, detected_lang = service.speech_to_text(wav_bytes, expected_lang=expected_lang)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "VOICE_ERROR", "message": str(exc)}}), 422
        return jsonify({"text": text, "detected_lang": detected_lang}), 200

    @app.post("/text-to-speech")
    def text_to_speech():
        body = request.get_json(silent=True) or {}
        for field in ("text", "lang"):
            if field not in body:
                return jsonify({"error": {"code": "BAD_REQUEST", "message": f"{field} is required"}}), 400
        try:
            service = get_service()
            wav_bytes = service.text_to_speech(body["text"], body["lang"])
            ogg_bytes = _transcode_wav_to_ogg(wav_bytes)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "VOICE_ERROR", "message": str(exc)}}), 422
        return Response(ogg_bytes, mimetype="audio/ogg"), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8002)))
