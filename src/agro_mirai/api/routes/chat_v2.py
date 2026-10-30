"""``/v2/chat`` — the floating chatbot assistant (Module 58): a farmer
types a message and gets a reply grounded in their own real field/
advisory data, same grounding pattern as
``voice_client.answer_farmer_question`` (Module 30), but text-only and via
the OpenRouter/Groq text cascade (``text_chat_client.py``) instead of
Gemini/voice. Session-authenticated like every other ``/v2`` route.

Threads persist server-side (``chat_sessions``/``chat_messages``, Module
58 user-directed) so a farmer's chat history survives app restarts and
follows them across devices, same contract as ``/v2/conversations`` for
voice Q&A. The server is authoritative for conversation history -- it
loads prior turns from the DB by ``session_id`` rather than trusting a
client-supplied list, so a farmer can never see another session's turns
by passing an arbitrary history array.

Alongside the model's own optional chart block, the route independently
attaches up to one real, already-computed crop/irrigation/disease "card"
per reply when the farmer's message names that topic -- pulled straight
from the farmer's own DecisionEngine/DataStore records, never fabricated
by the LLM, so a card is always exactly as trustworthy as the rest of the
app's advisories.
"""
import logging
import uuid
from datetime import datetime, timezone

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
from agro_mirai.persistence.models import ChatMessage, ChatSession
from agro_mirai.voice.interface import V1_LANGUAGES

chat_v2_bp = Blueprint("chat_v2", __name__, url_prefix="/v2")

_log = logging.getLogger("agro_mirai.api.chat_v2")

_MAX_MESSAGE_CHARS = 2000

_IRRIGATION_WORDS = ("water", "irrigat", "moisture", "drip", "rain")
_DISEASE_WORDS = ("disease", "pest", "blight", "infect", "sick", "fungus", "bug")
_CROP_WORDS = ("crop", "variety", "plant", "grow", "sow", "harvest", "yield")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _pick_field(store, farmer_id: str, message: str):
    fields = store.list_fields(farmer_id, limit=20)
    if not fields:
        return None
    lowered = message.lower()
    return next((f for f in fields if f.name and f.name.lower() in lowered), fields[0])


def _grounded_cards(store, farmer_id: str, message: str) -> list[dict]:
    """Matches the farmer's own message against real, already-computed
    records -- never the LLM's own words -- so a card is only ever as
    trustworthy as the rest of the app. At most one card per reply, picked
    by which topic the message actually names."""
    lowered = message.lower()
    field = _pick_field(store, farmer_id, message)
    if field is None:
        return []

    if any(w in lowered for w in _IRRIGATION_WORDS):
        advice = store.get_latest_irrigation_advice(farmer_id, field.id)
        if advice:
            return [{
                "type": "irrigation",
                "field": field.name,
                "depth_mm": advice.recommended_depth_mm,
                "window_start_at": advice.window_start_at.isoformat(),
                "window_end_at": advice.window_end_at.isoformat(),
                "urgency": advice.urgency,
            }]
    if any(w in lowered for w in _DISEASE_WORDS):
        alerts = store.list_disease_risk_alerts(farmer_id, field.id, limit=1)
        if alerts:
            alert = alerts[0]
            return [{
                "type": "disease",
                "field": field.name,
                "disease": alert.disease,
                "risk_level": alert.risk_level,
                "confidence": alert.confidence,
                "recommended_action": alert.recommended_action,
            }]
    if any(w in lowered for w in _CROP_WORDS):
        rec = store.get_latest_crop_recommendation(farmer_id, field.id)
        if rec:
            return [{
                "type": "crop",
                "field": field.name,
                "crop": rec.recommended_crop,
                "confidence": rec.confidence,
                "rationale": rec.rationale,
            }]
    return []


def _session_to_json(session: ChatSession) -> dict:
    return {
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def _message_to_json(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "chart": message.chart,
        "cards": message.cards,
        "created_at": message.created_at.isoformat(),
    }


@chat_v2_bp.get("/chat/sessions")
@require_session_auth
def get_chat_sessions():
    store = current_app.extensions["data_store"]
    sessions = store.list_chat_sessions(g.farmer_id, limit=50)
    return jsonify({"sessions": [_session_to_json(s) for s in sessions]}), 200


@chat_v2_bp.get("/chat/sessions/<session_id>/messages")
@require_session_auth
def get_chat_session_messages(session_id: str):
    store = current_app.extensions["data_store"]
    session = store.get_chat_session(g.farmer_id, session_id)
    if session is None:
        raise ApiError(404, "NOT_FOUND", "Chat session not found")
    messages = store.list_chat_messages(g.farmer_id, session_id, limit=200)
    return jsonify({"session": _session_to_json(session), "messages": [_message_to_json(m) for m in messages]}), 200


@chat_v2_bp.post("/chat")
@require_session_auth
@voice_limiter.limit(lambda: current_app.config["CHAT_RATE_LIMIT"])
def post_chat():
    store = current_app.extensions["data_store"]
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError(400, "BAD_REQUEST", "body must be {\"message\": str, \"session_id\": str?, \"language\": str}")

    message = (body.get("message") or "").strip()
    if not message or len(message) > _MAX_MESSAGE_CHARS:
        raise ApiError(400, "BAD_REQUEST", f"message must be 1-{_MAX_MESSAGE_CHARS} characters")

    language = body.get("language") or "en"
    if language not in V1_LANGUAGES:
        raise ApiError(400, "BAD_REQUEST", f"language must be one of: {', '.join(sorted(V1_LANGUAGES))}")

    session_id = body.get("session_id")
    now = _utcnow()
    if session_id:
        session = store.get_chat_session(g.farmer_id, session_id)
        if session is None:
            raise ApiError(404, "NOT_FOUND", "Chat session not found")
    else:
        session = ChatSession(id=str(uuid.uuid4()), farmer_id=g.farmer_id, created_at=now, updated_at=now, title=message[:60])
        store.save_chat_session(g.farmer_id, session)

    # Server-authoritative history: loaded from this farmer's own session
    # row, never from client-supplied JSON -- see module docstring.
    prior = store.list_chat_messages(g.farmer_id, session.id, limit=MAX_HISTORY_MESSAGES)
    history = [{"role": m.role, "content": m.content} for m in prior[-MAX_HISTORY_MESSAGES:]]

    store.save_chat_message(g.farmer_id, ChatMessage(
        id=str(uuid.uuid4()), session_id=session.id, farmer_id=g.farmer_id,
        role="user", content=message, created_at=now,
    ))

    context = _build_grounded_context(store, g.farmer_id)
    language_name = _LANGUAGE_NAMES.get(language, language)
    system_prompt = build_chat_system_prompt(context, language_name)

    messages = [{"role": "system", "content": system_prompt}, *history, {"role": "user", "content": message}]
    reply = ask_chat(messages)

    cards = _grounded_cards(store, g.farmer_id, message)

    if reply is None:
        # Module 58, user-directed: degrade to a deterministic, already-
        # saved-advisory answer rather than a bare 503 -- the farmer still
        # gets something useful even with both LLM providers exhausted.
        _log.warning("chat cascade exhausted for farmer=%s, using rule-based fallback", g.farmer_id)
        answer_text, chart, source = rule_based_fallback_reply(store, g.farmer_id, message, language), None, "rule_based"
    else:
        answer_text, chart = extract_chart_block(reply)
        source = "llm"

    reply_at = _utcnow()
    store.save_chat_message(g.farmer_id, ChatMessage(
        id=str(uuid.uuid4()), session_id=session.id, farmer_id=g.farmer_id,
        role="assistant", content=answer_text, chart=chart, cards=cards, created_at=reply_at,
    ))
    session.updated_at = reply_at
    store.save_chat_session(g.farmer_id, session)

    return jsonify({
        "reply": answer_text, "chart": chart, "cards": cards,
        "session_id": session.id, "source": source,
    }), 200
