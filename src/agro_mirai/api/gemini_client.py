"""HTTP client for Google's Gemini API (Module 30, candidate (a)): the
one new integration surface identified in the voice-AI research — a free-tier
LLM call that grounds a farmer's spoken question in their own real
DecisionEngine/DataStore data, sitting between the existing AI4Bharat STT
and TTS paths (Module 12/21/23) rather than replacing either.

Mirrors ``cnn_client.py``'s never-raise contract: ``ask_gemini`` returns
``None`` on any unavailability (unset ``GEMINI_API_KEY``, unreachable,
timeout, non-200, malformed response) instead of raising, so
``voice_client.answer_farmer_question`` can apply the same
client-distinguishable-degradation contract every other external call in
this project already follows (never a bare 500).

Uses ``requests`` against Gemini's plain REST endpoint (no
``google-generativeai`` SDK dependency), same as ``cnn_client.py``/
Module 03's acquisition adapters. Model is Flash-tier — the only tier
covered by Gemini's free (no-card) quota as of this module's research
(decisions/0024-realtime-voice-ai-research.md).

``ask_gemini_vision``/``ask_gemini_structured`` (AI cascade restructure,
scratch/restructure-plan.md) are additions for the new disease/advisory/
crop-recommendation fallback tiers: they round-robin ``GEMINI_API_KEY_1``
.. ``_9`` via ``key_pool.KeyPool`` (same ``_N`` convention as
``sarvam_client.py``'s ``SARVAM_API_KEY_1..3``), falling back to the
single ``GEMINI_API_KEY`` if no numbered keys are set, so existing local
setups with just one key keep working. A 429 response marks that key as
cooling down and retries once with the next key before giving up on the
call (matches ``cnn_client.py``'s "retry once, then give up" shape).
``ask_gemini`` itself is unchanged and keeps using the single key only —
it is the voice feature's existing, already-working path.
"""
import base64
import json as json_module
import logging
import os

import requests

from agro_mirai.api.key_pool import KeyPool

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 20
DEFAULT_MODEL = "gemini-flash-latest"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_CASCADE_TIMEOUT_S = 12


def gemini_api_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key or None


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def gemini_timeout() -> float:
    raw = os.environ.get("GEMINI_TIMEOUT_S", "")
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def ask_gemini(prompt: str) -> str | None:
    """POSTs ``prompt`` to Gemini's ``generateContent`` endpoint.

    Returns the model's plain-text reply, or ``None`` on anything else —
    unset API key, network error, timeout, non-200 status, or a response
    with no usable text part (e.g. blocked by safety filters). Never
    raises.
    """
    api_key = gemini_api_key()
    if not api_key:
        return None

    url = f"{_API_BASE}/{gemini_model()}:generateContent"
    try:
        resp = requests.post(
            url,
            headers={"X-goog-api-key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=gemini_timeout(),
        )
    except requests.RequestException:
        return None

    if resp.status_code != 200:
        return None

    try:
        body = resp.json()
        candidates = body.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except (ValueError, AttributeError, TypeError):
        return None


_pool = KeyPool("gemini", "GEMINI_API_KEY", max_keys=9)


def _cascade_keys() -> list[str]:
    """Numbered pool first, then the single legacy key as a last resort,
    same shape as ``sarvam_client.sarvam_keys()``."""
    pooled = [_pool.get_key() for _ in range(max(_pool.key_count(), 1))]
    pooled = [k for k in pooled if k]
    single = gemini_api_key()
    return pooled or ([single] if single else [])


def _post_generate_content(payload: dict, timeout: float) -> dict | None:
    """POSTs ``payload`` to Gemini's ``generateContent``, trying each
    available key in turn. A 429 marks that key as cooling down (pooled
    keys only -- the legacy single key has nowhere to cool down to) and
    moves to the next key; any other failure (network error, non-200,
    malformed body) returns ``None`` immediately without raising."""
    url = f"{_API_BASE}/{gemini_model()}:generateContent"
    for key in _cascade_keys():
        try:
            resp = requests.post(
                url, headers={"X-goog-api-key": key}, json=payload, timeout=timeout,
            )
        except requests.RequestException as exc:
            logger.warning("Gemini cascade: network error: %s", exc)
            return None
        if resp.status_code == 429:
            logger.warning("Gemini cascade: key rate-limited (429), trying next key")
            _pool.mark_rate_limited(key)
            continue
        if resp.status_code != 200:
            logger.warning("Gemini cascade: HTTP %s", resp.status_code)
            return None
        _pool.mark_success(key)
        try:
            return resp.json()
        except ValueError:
            logger.warning("Gemini cascade: 200 but body was not JSON")
            return None
    return None  # no keys configured, or all keys rate-limited


def _extract_text(body: dict) -> str | None:
    try:
        candidates = body.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except (AttributeError, TypeError):
        return None


def ask_gemini_vision(image_bytes: bytes, prompt: str, mime_type: str = "image/jpeg") -> str | None:
    """Vision call for the disease-detection cascade's new LLM tier: an
    image plus a text prompt, same never-raise contract as ``ask_gemini``.
    Returns the model's plain-text reply, or ``None`` on anything else."""
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
                ]
            }
        ]
    }
    body = _post_generate_content(payload, _CASCADE_TIMEOUT_S)
    return _extract_text(body) if body is not None else None


def ask_gemini_structured(prompt: str, timeout: float = _CASCADE_TIMEOUT_S) -> dict | None:
    """Text-only call for the advisory/crop-recommendation cascades' new
    LLM tier. Asks Gemini for JSON output (``response_mime_type``) and
    parses it; returns ``None`` on any failure including a 200 response
    whose text isn't valid JSON (prompt should ask for JSON explicitly;
    this is defensive, not the primary enforcement)."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    body = _post_generate_content(payload, timeout)
    if body is None:
        return None
    text = _extract_text(body)
    if text is None:
        return None
    try:
        parsed = json_module.loads(text)
    except ValueError:
        logger.warning("Gemini cascade: structured response was not valid JSON")
        return None
    return parsed if isinstance(parsed, dict) else None
