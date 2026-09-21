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

import base64
import hashlib

from flask import Blueprint, Response, current_app, g, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.sarvam_client import sniff_audio_mimetype
from agro_mirai.api.session_auth import require_session_auth
from agro_mirai.api.stt_validation import validate_audio_upload
from agro_mirai.api.voice_client import (
    translate_text,
    answer_farmer_question,
    synthesize_advisory_audio,
    synthesize_answer_audio,
    transcribe_audio,
)
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

    resp = Response(audio, mimetype=sniff_audio_mimetype(audio))
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


@voice_v2_bp.post("/voice/ask")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["ASK_RATE_LIMIT"])
def post_voice_ask():
    """Module 30, candidate (a): a farmer asks a question by voice, gets a
    spoken answer grounded in their own real field/advisory data. Composes
    three already-verified-independently steps — existing STT (Module 12),
    a new Gemini text call scoped to this farmer's own DataStore rows
    (``voice_client.answer_farmer_question``), existing TTS (Module
    12/25) — rather than a single "realtime" voice API, per
    decisions/0024-realtime-voice-ai-research.md's recommendation. Any
    single step's unavailability degrades to a specific 503, never a bare
    500, same contract as every other voice route."""
    store = current_app.extensions["data_store"]
    audio_bytes = validate_audio_upload(request.files.get("audio"))

    expected_lang = request.form.get("expected_lang") or None
    if expected_lang and expected_lang not in V1_LANGUAGES:
        raise ApiError(
            400, "BAD_REQUEST", f"expected_lang must be one of: {', '.join(sorted(V1_LANGUAGES))}"
        )

    stt_result = transcribe_audio(audio_bytes, expected_lang)
    if stt_result is None:
        raise ApiError(503, "VOICE_UNAVAILABLE", _VOICE_UNAVAILABLE_MESSAGE)
    question_text, detected_lang = stt_result

    # The language the farmer picked in the app wins over the recogniser's
    # guess (a mis-detected language would answer in the wrong tongue).
    if expected_lang:
        language = expected_lang
    elif detected_lang in V1_LANGUAGES:
        language = detected_lang
    else:
        language = _resolve_language(store, g.farmer_id)

    answer_text = answer_farmer_question(store, g.farmer_id, question_text, language)
    if answer_text is None:
        raise ApiError(
            503,
            "LLM_UNAVAILABLE",
            "Question-answering service is unreachable; the client should show the "
            "transcribed question and let the farmer retry or fall back to browsing advisories.",
        )

    answer_audio = synthesize_answer_audio(answer_text, language)
    audio_b64 = base64.b64encode(answer_audio).decode("ascii") if answer_audio is not None else None

    return (
        jsonify(
            {
                "question_text": question_text,
                "detected_lang": detected_lang,
                "answer_text": answer_text,
                "language": language,
                "answer_audio_base64": audio_b64,
                "answer_audio_mimetype": sniff_audio_mimetype(answer_audio) if audio_b64 else None,
            }
        ),
        200,
    )


@voice_v2_bp.post("/translate")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["TTS_RATE_LIMIT"])
def post_translate():
    """Module 39: translate server-generated English text (advisory bodies,
    "why this?" explanations) into the farmer's language for on-screen display.
    Request: ``{"texts": ["..."], "target_lang": "te"}``. Response:
    ``{"texts": [...], "translated": true}``; if the voice service is
    unreachable, ``translated`` is false and the original English is returned
    (degrade-not-fail -- the client keeps showing English)."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("texts"), list):
        raise ApiError(400, "BAD_REQUEST", "body must be {\"texts\": [..], \"target_lang\": \"xx\"}")
    target = body.get("target_lang")
    if target not in V1_LANGUAGES:
        raise ApiError(400, "BAD_REQUEST", f"target_lang must be one of: {', '.join(sorted(V1_LANGUAGES))}")
    texts = body["texts"]
    if len(texts) > 10 or not all(isinstance(t, str) and len(t) <= 3000 for t in texts):
        raise ApiError(400, "BAD_REQUEST", "up to 10 strings of at most 3000 characters")
    out, ok = [], True
    for t in texts:
        tr = translate_text(t, "en", target) if target != "en" else t
        if tr is None:
            ok = False
            out.append(t)
        else:
            out.append(tr)
    return jsonify({"texts": out, "translated": ok and target != "en"}), 200
