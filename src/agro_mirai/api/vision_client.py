"""Vision client for the leaf-scan pipeline: OpenRouter primary, Groq
fallback (replaces Gemini for this flow -- field finding 2026-10-30).

Why the switch: Gemini's `generateContent` endpoint was repeatedly
unreachable live (connection-level read timeouts, reproduced from two
separate networks, not a key or quota issue) and even its own 503s read
"model currently experiencing high demand" -- a real, current reliability
problem for this specific flow, confirmed over multiple attempts the same
day. OpenRouter and Groq were both verified live with real crop-disease
photos (correct, specific diagnoses -- "Downy Mildew of Spinach", not a
generic guess) before wiring this in, not assumed to work from docs alone.

Model notes (both found live, not from stale docs -- model slugs on free
tiers rotate often, so re-verify if either starts 404ing):
- OpenRouter: `dots-studio/dots-3-note-preview:free`. Google's free slugs
  on OpenRouter (gemini-2.5-flash:free, gemma free tiers) repeatedly hit a
  saturated shared pool (429) or were retired (404) -- this one was not.
- Groq: `qwen/qwen3.8-27b`. Groq decommissioned its Llama vision models;
  this is what Groq's own current docs list as vision-capable.

Same shape as gemini_client.py's cascade: round-robin a key pool per
provider, retry the next key (then the next provider) on any failure
(429/5xx/timeout/network error), return `None` on total exhaustion so the
caller degrades honestly instead of raising. Both APIs are OpenAI-
compatible chat completions, so one payload shape covers both.
"""
import base64
import json as json_module
import logging
import os

import requests

from agro_mirai.api.key_pool import KeyPool

logger = logging.getLogger(__name__)

_TIMEOUT_S = 15
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "dots-studio/dots-3-note-preview:free"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "qwen/qwen3.8-27b"

_openrouter_pool = KeyPool("openrouter_vision", "OPENROUTER_VISION_API_KEY", max_keys=5)
_groq_pool = KeyPool("groq_vision", "GROQ_VISION_API_KEY", max_keys=5)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _chat_completion(url: str, model: str, api_key: str, prompt: str, image_bytes: bytes) -> dict | None:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }
        ],
    }
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        logger.warning("Vision cascade (%s): network error: %s", url, exc)
        return None
    if resp.status_code != 200:
        logger.warning("Vision cascade (%s): HTTP %s", url, resp.status_code)
        return {"__retryable__": resp.status_code in _RETRYABLE_STATUSES, "__status__": resp.status_code}
    try:
        return resp.json()
    except ValueError:
        logger.warning("Vision cascade (%s): 200 but body was not JSON", url)
        return None


def _extract_text(body: dict) -> str | None:
    try:
        return str(body["choices"][0]["message"]["content"]).strip() or None
    except (KeyError, IndexError, TypeError):
        return None


def ask_vision(prompt: str, image_bytes: bytes) -> str | None:
    """Tries every OpenRouter key, then every Groq key, on any retryable
    failure. Returns the model's plain-text reply, or `None` once both
    providers are exhausted. Never raises."""
    for pool, url, model in ((_openrouter_pool, _OPENROUTER_URL, _OPENROUTER_MODEL),
                              (_groq_pool, _GROQ_URL, _GROQ_MODEL)):
        keys = [pool.get_key() for _ in range(max(pool.key_count(), 1))]
        keys = [k for k in keys if k]
        for key in keys:
            result = _chat_completion(url, model, key, prompt, image_bytes)
            if result is None:
                continue
            if "__retryable__" in result:
                if result["__status__"] == 429:
                    pool.mark_rate_limited(key)
                continue
            pool.mark_success(key)
            text = _extract_text(result)
            if text is not None:
                return text
    logger.warning("Vision cascade: exhausted OpenRouter and Groq, every attempt failed")
    return None


_IS_PLANT_PROMPT = (
    "Look at this image. Decide ONLY: is this a close-up photo of a real "
    "plant/crop leaf -- visible leaf shape, veins, edges, natural texture?\n\n"
    "REJECT (is_plant: false) for: plain/solid/uniform colored surface or "
    "background (including green), blurry/unrecognizable, non-plant object, "
    "person, screen, document, multiple unrelated items, or anything without "
    "clear leaf structure.\n\n"
    "Only accept (is_plant: true) if you can clearly see an actual single "
    "leaf's shape and surface detail.\n\n"
    'Respond with ONLY this JSON, nothing else: {"is_plant": true} or '
    '{"is_plant": false}'
)


def vision_is_plant_precheck(image_bytes: bytes) -> bool | None:
    """Same contract as gemini_client.gemini_is_plant_precheck: True/False
    on a clear verdict, None when unreachable -- never raises."""
    text = ask_vision(_IS_PLANT_PROMPT, image_bytes)
    if text is None:
        return None
    try:
        data = json_module.loads(text)
        verdict = data["is_plant"]
        return bool(verdict) if isinstance(verdict, bool) else None
    except (json_module.JSONDecodeError, KeyError, TypeError):
        return None


_ANALYZE_LEAF_PROMPT = (
    "This image passed a leaf-detection check. Analyze it as a plant "
    "pathologist.\n\n"
    "Respond with ONLY this JSON, nothing else:\n"
    '{"plant_name": "<your best guess at the plant/crop species, even if '
    'uncertain -- never say unknown, always name your closest guess>", '
    '"has_disease": true|false, "disease_name": "<name if has_disease else '
    '\\"healthy\\">", "confidence": <0.0-1.0>, "description": "<one short '
    'sentence on what you see>", "recommended_action": "<one short '
    'actionable sentence>"}'
)


def vision_analyze_leaf(image_bytes: bytes) -> dict | None:
    """Same contract as gemini_client.gemini_analyze_leaf. Called only
    after vision_is_plant_precheck has confirmed the photo is a leaf."""
    text = ask_vision(_ANALYZE_LEAF_PROMPT, image_bytes)
    if text is None:
        return None
    try:
        data = json_module.loads(text)
        return {
            "plant_name": str(data["plant_name"]),
            "has_disease": bool(data["has_disease"]),
            "disease_name": str(data["disease_name"]),
            "confidence": float(data["confidence"]),
            "description": str(data.get("description") or ""),
            "recommended_action": str(data.get("recommended_action") or ""),
        }
    except (json_module.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
