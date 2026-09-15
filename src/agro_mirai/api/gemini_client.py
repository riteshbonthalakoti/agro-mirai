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
"""
from __future__ import annotations

import os

import requests

DEFAULT_TIMEOUT_S = 20
DEFAULT_MODEL = "gemini-2.5-flash"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


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
            params={"key": api_key},
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
