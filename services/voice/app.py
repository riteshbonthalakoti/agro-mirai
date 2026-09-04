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

The model is loaded lazily (first request), same pattern as the CNN
service, so /health responds even before AI4Bharat's ~6.8GB of weights
have finished downloading/caching on first boot.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, Response, jsonify, request

_service = None
_service_load_error: str | None = None


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
        try:
            service = get_service()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": {"code": "MODEL_UNAVAILABLE", "message": str(exc)}}), 503

        audio_bytes = audio_file.read()
        try:
            text, detected_lang = service.speech_to_text(audio_bytes, expected_lang=expected_lang)
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
