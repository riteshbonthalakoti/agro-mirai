"""``/v2`` voice endpoints — per-advisory TTS audio and STT (Module 23,
Blocker B: the voice stack existed with no client-facing API at all).

Both routes call the standalone Oracle-hosted voice service
(``services/voice``, Module 21) over HTTP via ``voice_client.py`` /
``RemoteVoiceService`` — never AI4Bharat/torch directly, keeping the main
API process free of that dependency weight per
decisions/0019-deployment-architecture.md. Every failure to reach that
service (``VOICE_SERVICE_URL`` unset, unreachable, timeout, malformed
response) is surfaced as a specific 503 ``VOICE_UNAVAILABLE`` error —
never a bare 500, never a silent empty body — so Ritesh's decided mobile
design (pre-cached TTS audio with Android's on-device TTS as the offline
fallback) can key off that response to fall back, the same
client-distinguishable-degradation contract Module 21 established for the
CNN image path (there the fallback happens server-side against the
rule-based model; here there is no server-side substitute for spoken
audio, so the fallback has to happen on the client — see
decisions/0020-v2-value-endpoints-and-voice-api.md).
"""
from __future__ import annotations

import hashlib

from flask import Blueprint, Response, current_app, g, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.session_auth import require_session_auth
from agro_mirai.api.stt_validation import validate_audio_upload
from agro_mirai.api.voice_client import synthesize_advisory_audio, transcribe_audio
from agro_mirai.api.voice_rate_limit import voice_limiter
from agro_mirai.voice.interface import V1_LANGUAGES

voice_v2_bp = Blueprint("voice_v2", __name__, url_prefix="/v2")

#: services/voice's Piper backend produces WAV; that container transcodes
#: to OGG/Vorbis before responding (Module 23 — see services/voice/app.py
#: and decisions/0020's "TTS endpoint shape" section for why OGG over MP3:
#: ffmpeg's libvorbis needs no extra codec install, unlike libmp3lame).
ADVISORY_AUDIO_MIMETYPE = "audio/ogg"

_VOICE_UNAVAILABLE_MESSAGE = (
    "Voice service is unreachable; the client should fall back to on-device TTS/STT."
)


def _resolve_language(store, farmer_id: str) -> str:
    override = request.args.get("language")
    if override:
        if override not in V1_LANGUAGES:
            raise ApiError(
                400, "BAD_REQUEST", f"language must be one of: {', '.join(sorted(V1_LANGUAGES))}"
            )
        return override
    farmer = store.get_farmer(farmer_id)
    lang = (farmer.preferred_language if farmer else None) or "en"
    return lang if lang in V1_LANGUAGES else "en"


@voice_v2_bp.get("/advisories/<advisory_id>/audio")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["TTS_RATE_LIMIT"])
def get_advisory_audio(advisory_id: str):
    store = current_app.extensions["data_store"]
    # DataStore.get_advisory is farmer-scoped — an advisory that exists
    # but belongs to a different farmer is None here, same 404-not-403
    # ownership contract as every other /v2 route (ADR 0003).
    advisory = store.get_advisory(g.farmer_id, advisory_id)
    if advisory is None:
        raise ApiError(404, "NOT_FOUND", "Advisory not found")

    language = _resolve_language(store, g.farmer_id)

    # ETag keyed on advisory id + creation time + language: identical for
    # every request until a *new* advisory is generated for this field or
    # a different language is asked for, so the client can cache
    # aggressively and revalidate for free (pre-caching's whole point).
    etag = hashlib.sha256(f"{advisory.id}:{advisory.created_at.isoformat()}:{language}".encode()).hexdigest()
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304)

    audio = synthesize_advisory_audio(advisory, language)
    if audio is None:
        raise ApiError(503, "VOICE_UNAVAILABLE", _VOICE_UNAVAILABLE_MESSAGE)

    resp = Response(audio, mimetype=ADVISORY_AUDIO_MIMETYPE)
    resp.headers["ETag"] = etag
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@voice_v2_bp.post("/stt")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["STT_RATE_LIMIT"])
def post_stt():
    audio_bytes = validate_audio_upload(request.files.get("audio"))

    expected_lang = request.form.get("expected_lang") or None
    if expected_lang and expected_lang not in V1_LANGUAGES:
        raise ApiError(
            400, "BAD_REQUEST", f"expected_lang must be one of: {', '.join(sorted(V1_LANGUAGES))}"
        )

    result = transcribe_audio(audio_bytes, expected_lang)
    if result is None:
        raise ApiError(503, "VOICE_UNAVAILABLE", _VOICE_UNAVAILABLE_MESSAGE)

    text, detected_lang = result
    return jsonify({"text": text, "detected_lang": detected_lang}), 200
