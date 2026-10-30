"""``/v2/chat`` — the floating chatbot assistant (Module 58): a farmer
types a message (plus recent history for context) and gets a reply
grounded in their own real field/advisory data, same grounding pattern as
``voice_client.answer_farmer_question`` (Module 30), but text-only and via
the OpenRouter/Groq text cascade (``text_chat_client.py``) instead of
Gemini/voice. Session-authenticated like every other ``/v2`` route.
"""
import logging

from flask import Blueprint, current_app, g, jsonify, request

from agro_mirai.api.errors import ApiError
from agro_mirai.api.session_auth import require_session_auth
from agro_mirai.api.text_chat_client import (
    MAX_HISTORY_MESSAGES,
    ask_chat,
    build_chat_system_prompt,
    extract_chart_block,
    rule_based_fallback_reply,
)
from agro_mirai.api.voice_client import _LANGUAGE_NAMES, _build_grounded_context
from agro_mirai.api.voice_rate_limit import voice_limiter
from agro_mirai.voice.interface import V1_LANGUAGES

chat_v2_bp = Blueprint("chat_v2", __name__, url_prefix="/v2")

_log = logging.getLogger("agro_mirai.api.chat_v2")

_MAX_MESSAGE_CHARS = 2000


def _validate_history(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(400, "BAD_REQUEST", "history must be a list of {role, content}")
    out = []
    for item in raw[-MAX_HISTORY_MESSAGES:]:
        if (
            not isinstance(item, dict)
            or item.get("role") not in ("user", "assistant")
            or not isinstance(item.get("content"), str)
            or len(item["content"]) > _MAX_MESSAGE_CHARS
        ):
            raise ApiError(400, "BAD_REQUEST", "each history item must be {role: user|assistant, content: str}")
        out.append({"role": item["role"], "content": item["content"]})
    return out


@chat_v2_bp.post("/chat")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["CHAT_RATE_LIMIT"])
def post_chat():
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "body must be {\"message\": str, \"history\": [...], \"language\": str}")

    message = (body.get("message") or "").strip()
    if not message or len(message) > _MAX_MESSAGE_CHARS:
        raise ApiError(400, "BAD_REQUEST", f"message must be 1-{_MAX_MESSAGE_CHARS} characters")

    language = body.get("language") or "en"
    if language not in V1_LANGUAGES:
        raise ApiError(400, "BAD_REQUEST", f"language must be one of: {', '.join(sorted(V1_LANGUAGES))}")

    history = _validate_history(body.get("history"))

    context = _build_grounded_context(store, g.farmer_id)
    language_name = _LANGUAGE_NAMES.get(language, language)
    system_prompt = build_chat_system_prompt(context, language_name)

    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]
    reply = ask_chat(messages)
    if reply is None:
        # Module 58, user-directed: degrade to a deterministic, already-
        # saved-advisory answer rather than a bare 503 -- the farmer still
        # gets something useful even with both LLM providers exhausted.
        _log.warning("chat cascade exhausted for farmer=%s, using rule-based fallback", g.farmer_id)
        fallback_text = rule_based_fallback_reply(store, g.farmer_id, message, language)
        return jsonify({"reply": fallback_text, "chart": None, "source": "rule_based"}), 200

    answer_text, chart = extract_chart_block(reply)
    return jsonify({"reply": answer_text, "chart": chart, "source": "llm"}), 200
