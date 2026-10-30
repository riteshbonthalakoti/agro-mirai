"""Text-only chat client for the floating assistant (Module 58): OpenRouter
primary, Groq fallback, same cascade shape as vision_client.py (round-robin
a key pool per provider, retry the next key then the next provider on any
retryable failure, return ``None`` on total exhaustion so the caller
degrades honestly instead of raising).

Separate key pool/budget from the vision cascade -- distinct env var names
(``OPENROUTER_CHAT_API_KEY_*`` / ``GROQ_CHAT_API_KEY_*``) per the user's
request, since this is a different allowance of free-tier keys.

Model notes (OpenRouter verified live against this app's actual 3 chat
keys 2026-10-30; free-tier slugs rotate often, re-verify if either starts
404ing):
- OpenRouter: `google/gemma-4-31b-it:free` -- `meta-llama/llama-3.3-8b-
  instruct:free` (the first slug tried) came back 404 "no longer
  available on OpenRouter: no provider serves this model anymore".
  `google/gemma-4-31b-it:free` is live (confirmed via `GET /models`) and
  routes real requests -- every one of the 3 provided keys hit a 429
  "free-models-per-day" response rather than 404, which only happens once
  OpenRouter actually tries to serve the model. IMPORTANT finding: all 3
  keys share the same OpenRouter account (`user_id` identical in every
  response) and OpenRouter's free-tier 50-req/day cap is per ACCOUNT, not
  per key -- so this pool's 3 keys do not multiply the daily free quota
  the way they do for per-minute/per-key rate limits; they were already
  exhausted for the day during verification. A genuine 200 response with
  this exact model has not yet been observed live -- re-verify once the
  daily quota resets (`X-RateLimit-Reset` header) before relying on it in
  production.
- Groq: `openai/gpt-oss-20b` -- `llama-3.1-8b-instant` (the first slug
  tried) 404s "does not exist or you do not have access to it" on the
  provided key. `openai/gpt-oss-20b` was confirmed live with a real 200
  response and a correct, on-topic answer (2026-10-30). Note: this
  model's response includes a separate `message.reasoning` field
  alongside `message.content` -- `_extract_text` reads only `content`,
  which comes back clean (no reasoning text mixed in).
"""
import json as json_module
import logging

import requests

from agro_mirai.api.key_pool import KeyPool

logger = logging.getLogger(__name__)

_TIMEOUT_S = 20
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "openai/gpt-oss-20b"

_openrouter_pool = KeyPool("openrouter_chat", "OPENROUTER_CHAT_API_KEY", max_keys=4)
_groq_pool = KeyPool("groq_chat", "GROQ_CHAT_API_KEY", max_keys=3)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

#: caller-facing contract: at most this many prior turns are sent back to
#: the model, oldest dropped first -- keeps the prompt bounded without a
#: separate truncation step in the route.
MAX_HISTORY_MESSAGES = 12


def _chat_completion(url: str, model: str, api_key: str, messages: list[dict]) -> dict | None:
    payload = {"model": model, "messages": messages}
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=_TIMEOUT_S,
        )
    except requests.RequestException as exc:
        logger.warning("Chat cascade (%s): network error: %s", url, exc)
        return None
    if resp.status_code != 200:
        logger.warning("Chat cascade (%s): HTTP %s", url, resp.status_code)
        return {"__retryable__": resp.status_code in _RETRYABLE_STATUSES, "__status__": resp.status_code}
    try:
        return resp.json()
    except ValueError:
        logger.warning("Chat cascade (%s): 200 but body was not JSON", url)
        return None


def _extract_text(body: dict) -> str | None:
    try:
        return str(body["choices"][0]["message"]["content"]).strip() or None
    except (KeyError, IndexError, TypeError):
        return None


def ask_chat(messages: list[dict]) -> str | None:
    """Tries every OpenRouter key, then every Groq key, on any retryable
    failure. ``messages`` is an OpenAI-style chat list (system + history +
    latest user turn). Returns the model's plain-text reply, or ``None``
    once both providers are exhausted. Never raises."""
    for pool, url, model in ((_openrouter_pool, _OPENROUTER_URL, _OPENROUTER_MODEL),
                              (_groq_pool, _GROQ_URL, _GROQ_MODEL)):
        keys = [pool.get_key() for _ in range(max(pool.key_count(), 1))]
        keys = [k for k in keys if k]
        for key in keys:
            result = _chat_completion(url, model, key, messages)
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
    logger.warning("Chat cascade: exhausted OpenRouter and Groq, every attempt failed")
    return None


_CHART_INSTRUCTION = (
    "If, and only if, a chart would genuinely help answer the farmer's question "
    "(e.g. a trend over time, or comparing two or more values), include ONE JSON "
    "block of this exact shape anywhere in your reply, on its own line:\n"
    '{"chart": {"type": "bar"|"line", "title": "<short title>", "labels": '
    '["<label1>", ...], "values": [<number1>, ...]}}\n'
    "Never invent numbers that are not supported by the farmer's data below or by "
    "your own answer. Omit the chart block entirely for a plain conversational "
    "question that doesn't need one."
)


def build_chat_system_prompt(context: str, language_name: str) -> str:
    """System prompt for the floating chat assistant: same grounded-in-
    real-data contract as voice_client.answer_farmer_question (never
    generic advice -- always this specific farmer's own field/advisory
    data below), tuned further for text chat's lower-literacy audience
    per the user's explicit instruction that this prompt is a first-class
    deliverable, not boilerplate. Plus the structured chart-block
    instruction (Module 58) since this is text-only chat and the client
    renders chart JSON itself."""
    return (
        "You are AGRO MIRAI, a farm advisor chatting with an Indian smallholder farmer "
        "who may have limited literacy or technical background. Follow these rules "
        "strictly:\n"
        "1. Use ONLY the real field data given below -- never invent a crop, soil "
        "value, weather number, or advisory that is not in it. If the data does not "
        "cover the question, say so plainly instead of guessing.\n"
        "2. Use the simplest possible words. No jargon, no scientific names unless the "
        "farmer used one first, no filler phrases like 'it is important to note'.\n"
        "3. Be precise and actionable: say exactly WHAT to do, WHEN, and HOW MUCH (a "
        "number, a day, an amount) whenever the data supports it.\n"
        "4. Keep it short: 2-4 short sentences, each one a complete simple thought. "
        "No markdown, no bullet symbols, no headings.\n"
        f"5. Reply only in {language_name}.\n\n"
        f"{_CHART_INSTRUCTION}\n\nThis farmer's real field data:\n{context}"
    )


_FALLBACK_TRANSLATIONS = {
    # Minimal fixed phrases for the no-LLM rule-based fallback (below) --
    # intentionally not run through the chat models, so this has to carry
    # its own translations rather than depending on a live LLM call.
    "en": {
        "no_fields": "You don't have any fields registered yet. Add a field first so I can help you.",
        "no_advisory": "I don't have a recent advisory for your '{field}' field yet. Check back after your next advisory.",
        "with_advisory": "For your '{field}' field ({crop}): {body}",
        "intro": "The assistant is busy right now, so here is your most recent saved advisory instead of a live answer.",
    },
    "kn": {
        "no_fields": "ನಿಮ್ಮ ಬಳಿ ಇನ್ನೂ ಯಾವುದೇ ಹೊಲ ನೋಂದಣಿಯಾಗಿಲ್ಲ. ಸಹಾಯ ಮಾಡಲು ಮೊದಲು ಒಂದು ಹೊಲ ಸೇರಿಸಿ.",
        "no_advisory": "ನಿಮ್ಮ '{field}' ಹೊಲಕ್ಕೆ ಇನ್ನೂ ಹೊಸ ಸಲಹೆ ಇಲ್ಲ. ಮುಂದಿನ ಸಲಹೆಯ ನಂತರ ಪರಿಶೀಲಿಸಿ.",
        "with_advisory": "ನಿಮ್ಮ '{field}' ಹೊಲಕ್ಕೆ ({crop}): {body}",
        "intro": "ಸಹಾಯಕ ಈಗ busy ಆಗಿದೆ, ಆದ್ದರಿಂದ ನಿಮ್ಮ ಇತ್ತೀಚಿನ ಉಳಿಸಿದ ಸಲಹೆ ಇಲ್ಲಿದೆ.",
    },
    "te": {
        "no_fields": "మీకు ఇంకా ఏ పొలం నమోదు కాలేదు. సహాయం చేయడానికి ముందుగా ఒక పొలం జోడించండి.",
        "no_advisory": "మీ '{field}' పొలానికి ఇంకా కొత్త సలహా లేదు. తర్వాతి సలహా తర్వాత తిరిగి చూడండి.",
        "with_advisory": "మీ '{field}' పొలానికి ({crop}): {body}",
        "intro": "సహాయకుడు ఇప్పుడు busy గా ఉన్నారు, కాబట్టి మీ తాజా సేవ్ చేసిన సలహా ఇక్కడ ఉంది.",
    },
    "hi": {
        "no_fields": "आपके पास अभी कोई खेत दर्ज नहीं है। मदद के लिए पहले एक खेत जोड़ें।",
        "no_advisory": "आपके '{field}' खेत के लिए अभी कोई नई सलाह नहीं है। अगली सलाह के बाद फिर देखें।",
        "with_advisory": "आपके '{field}' खेत के लिए ({crop}): {body}",
        "intro": "सहायक अभी व्यस्त है, इसलिए यह आपकी सबसे हाल की सेव की गई सलाह है।",
    },
}


def rule_based_fallback_reply(store, farmer_id: str, message: str, language: str) -> str:
    """Deterministic, no-LLM fallback for when every OpenRouter/Groq key is
    exhausted (Module 58, user-directed): rather than a bare 503, hand the
    farmer the most relevant already-saved advisory straight from the
    DataStore. Picks the field the farmer's own message names (by name,
    case-insensitively) when there is one, else the farmer's first field.
    Never raises -- a missing field/advisory degrades to a plain, honest
    message in the farmer's own language instead of a crash."""
    phrases = _FALLBACK_TRANSLATIONS.get(language, _FALLBACK_TRANSLATIONS["en"])
    fields = store.list_fields(farmer_id, limit=20)
    if not fields:
        return phrases["no_fields"]

    lowered = message.lower()
    field = next((f for f in fields if f.name and f.name.lower() in lowered), fields[0])

    advisories = store.list_advisories_for_field(farmer_id, field.id, limit=1)
    if not advisories:
        return f"{phrases['intro']} {phrases['no_advisory'].format(field=field.name)}"

    latest = advisories[0]
    return f"{phrases['intro']} {phrases['with_advisory'].format(field=field.name, crop=field.current_crop or '?', body=latest.body)}"


def extract_chart_block(reply: str) -> tuple[str, dict | None]:
    """Pulls the ``{"chart": {...}}`` JSON block (if any) out of ``reply``,
    returning the chart dict (or ``None``) and the reply text with that
    block removed. Malformed/missing chart JSON is never an error -- the
    farmer still gets the prose answer."""
    start = reply.find('{"chart"')
    if start == -1:
        start = reply.find('{ "chart"')
    if start == -1:
        return reply.strip(), None
    depth = 0
    end = None
    for i in range(start, len(reply)):
        if reply[i] == "{":
            depth += 1
        elif reply[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return reply.strip(), None
    block = reply[start:end]
    cleaned = (reply[:start] + reply[end:]).strip()
    try:
        data = json_module.loads(block)
        chart = data.get("chart")
        if not isinstance(chart, dict):
            return cleaned or reply.strip(), None
        chart_type = chart.get("type")
        labels = chart.get("labels")
        values = chart.get("values")
        if chart_type not in ("bar", "line") or not isinstance(labels, list) or not isinstance(values, list):
            return cleaned or reply.strip(), None
        if len(labels) != len(values) or not labels:
            return cleaned or reply.strip(), None
        if not all(isinstance(v, (int, float)) for v in values):
            return cleaned or reply.strip(), None
        return cleaned or reply.strip(), {
            "type": chart_type,
            "title": str(chart.get("title") or ""),
            "labels": [str(l) for l in labels],
            "values": [float(v) for v in values],
        }
    except (json_module.JSONDecodeError, AttributeError, TypeError):
        return cleaned or reply.strip(), None
