"""Module 58: ``POST /v2/chat`` and the chat-session read endpoints --
the floating chatbot assistant. The OpenRouter/Groq text cascade boundary
is mocked, same convention as ``test_voice_ask_route.py``: no live key,
real SQLiteDataStore for grounding/isolation/persistence checks.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import Advisory, CropRecommendation, DiseaseRiskAlert, IrrigationAdvice
from agro_mirai.persistence.sqlite_store import SQLiteDataStore

_NOW = datetime(2026, 9, 15, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def app():
    store = SQLiteDataStore(":memory:")
    return create_app({"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y"})


@pytest.fixture
def client(app):
    return app.test_client()


def _register_and_login(client, phone="+919000000001"):
    from _otp_helpers import register_and_login

    resp = register_and_login(client, phone)
    assert resp.status_code == 200
    return resp


def _create_field(client) -> str:
    resp = client.post(
        "/v2/fields",
        json={"name": "Plot", "latitude": 15.0, "longitude": 76.0, "area_ha": 1.0},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _farmer_id(app) -> str:
    return list(app.extensions["data_store"]._conn.execute("SELECT id FROM farmers").fetchall())[0][0]


def _seed_advisory(app, farmer_id: str, field_id: str) -> None:
    store = app.extensions["data_store"]
    advisory = Advisory(
        id="adv-1", field_id=field_id, created_at=_NOW, language="en",
        title="Irrigate soon", body="Apply 12mm within 3 days.", severity="moderate",
    )
    store.save_advisory(farmer_id, advisory)


def _post_chat(client, message="How is my field?", session_id=None, language="en"):
    body = {"message": message, "language": language}
    if session_id:
        body["session_id"] = session_id
    return client.post("/v2/chat", json=body)


def test_chat_requires_session(client):
    resp = _post_chat(client)
    assert resp.status_code == 401


def test_chat_success_returns_reply_and_new_session_id(client, monkeypatch):
    _register_and_login(client)
    _create_field(client)
    monkeypatch.setattr(
        "agro_mirai.api.routes.chat_v2.ask_chat",
        lambda messages: "Water your Plot field within 3 days, about 12mm.",
    )
    resp = _post_chat(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert "12mm" in body["reply"]
    assert body["chart"] is None
    assert body["cards"] == []
    assert body["source"] == "llm"
    assert body["session_id"]


def test_chat_second_message_reuses_session_and_sees_history(client, monkeypatch):
    _register_and_login(client)
    _create_field(client)
    captured = []

    def _fake_ask(messages):
        captured.append(messages)
        return "ok"

    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", _fake_ask)

    first = _post_chat(client, message="hi there")
    session_id = first.get_json()["session_id"]
    second = _post_chat(client, message="what next?", session_id=session_id)
    assert second.status_code == 200
    assert second.get_json()["session_id"] == session_id

    second_messages = captured[1]
    joined = " ".join(m["content"] for m in second_messages)
    assert "hi there" in joined
    assert "ok" in joined  # the first assistant reply is in history too


def test_chat_unknown_session_id_returns_404(client, monkeypatch):
    _register_and_login(client)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    resp = _post_chat(client, session_id="does-not-exist")
    assert resp.status_code == 404


def test_chat_returns_chart_when_model_emits_one(client, monkeypatch):
    _register_and_login(client)
    _create_field(client)
    reply = (
        'Rainfall has been rising this week.\n'
        '{"chart": {"type": "bar", "title": "Rainfall (mm)", "labels": ["Mon", "Tue"], "values": [2, 9]}}'
    )
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: reply)
    resp = _post_chat(client, message="show me rainfall this week")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["chart"] == {"type": "bar", "title": "Rainfall (mm)", "labels": ["Mon", "Tue"], "values": [2.0, 9.0]}
    assert "rising" in body["reply"].lower()


def test_chat_attaches_irrigation_card_when_message_mentions_watering(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = _farmer_id(app)
    app.extensions["data_store"].save_irrigation_advice(farmer_id, IrrigationAdvice(
        id="irr-1", field_id=field_id, created_at=_NOW,
        recommended_depth_mm=12.0, window_start_at=_NOW, window_end_at=_NOW, urgency="moderate",
    ))
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    resp = _post_chat(client, message="should I water my field today?")
    assert resp.status_code == 200
    cards = resp.get_json()["cards"]
    assert len(cards) == 1
    assert cards[0]["type"] == "irrigation"
    assert cards[0]["depth_mm"] == 12.0


def test_chat_attaches_disease_card_when_message_mentions_disease(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = _farmer_id(app)
    app.extensions["data_store"].save_disease_risk_alert(farmer_id, DiseaseRiskAlert(
        id="dis-1", field_id=field_id, created_at=_NOW,
        disease="Leaf Blight", risk_level="high", confidence=0.8, recommended_action="Apply fungicide",
    ))
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    resp = _post_chat(client, message="is there a disease risk on my plant?")
    assert resp.status_code == 200
    cards = resp.get_json()["cards"]
    assert cards[0]["type"] == "disease"
    assert cards[0]["disease"] == "Leaf Blight"


def test_chat_attaches_crop_card_when_message_mentions_crop(app, client, monkeypatch):
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = _farmer_id(app)
    app.extensions["data_store"].save_crop_recommendation(farmer_id, CropRecommendation(
        id="crop-1", field_id=field_id, created_at=_NOW, recommended_crop="cotton", confidence=0.9,
    ))
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    resp = _post_chat(client, message="what crop should I grow next season?")
    assert resp.status_code == 200
    cards = resp.get_json()["cards"]
    assert cards[0]["type"] == "crop"
    assert cards[0]["crop"] == "cotton"


def test_chat_no_card_for_plain_question(client, monkeypatch):
    _register_and_login(client)
    _create_field(client)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    resp = _post_chat(client, message="hello, how are you?")
    assert resp.status_code == 200
    assert resp.get_json()["cards"] == []


def test_chat_llm_unavailable_falls_back_to_rule_based_reply(app, client, monkeypatch):
    """Module 58, user-directed: both LLM providers exhausted degrades to
    a deterministic saved-advisory reply, never a bare 503."""
    _register_and_login(client)
    field_id = _create_field(client)
    farmer_id = _farmer_id(app)
    _seed_advisory(app, farmer_id, field_id)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: None)

    resp = _post_chat(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["source"] == "rule_based"
    assert "12mm" in body["reply"]
    assert body["chart"] is None


def test_chat_llm_unavailable_no_fields_still_returns_200(client, monkeypatch):
    _register_and_login(client)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: None)
    resp = _post_chat(client)
    assert resp.status_code == 200
    assert resp.get_json()["source"] == "rule_based"


def test_chat_empty_message_returns_400(client):
    _register_and_login(client)
    resp = _post_chat(client, message="   ")
    assert resp.status_code == 400


def test_chat_prompt_is_scoped_to_this_farmer_only(app, client, monkeypatch):
    """Same ADR 0003 ownership check as test_voice_ask_route's equivalent:
    the grounding context must never leak another farmer's data."""
    _register_and_login(client, phone="+919000000002")
    field_id = _create_field(client)
    farmer_id = _farmer_id(app)
    _seed_advisory(app, farmer_id, field_id)

    captured = {}

    def _fake_ask(messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", _fake_ask)

    resp = _post_chat(client)
    assert resp.status_code == 200
    system_prompt = captured["messages"][0]["content"]
    assert "Apply 12mm within 3 days" in system_prompt


# ---- persisted sessions / messages -----------------------------------------

def test_list_sessions_requires_auth(client):
    resp = client.get("/v2/chat/sessions")
    assert resp.status_code == 401


def test_list_sessions_and_messages_roundtrip(client, monkeypatch):
    _register_and_login(client)
    _create_field(client)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "Water soon.")

    resp = _post_chat(client, message="How is my field?")
    session_id = resp.get_json()["session_id"]

    sessions = client.get("/v2/chat/sessions").get_json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["title"] == "How is my field?"

    msgs_resp = client.get(f"/v2/chat/sessions/{session_id}/messages")
    assert msgs_resp.status_code == 200
    messages = msgs_resp.get_json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "How is my field?"
    assert messages[1]["content"] == "Water soon."


def test_get_messages_for_unknown_session_returns_404(client):
    _register_and_login(client)
    resp = client.get("/v2/chat/sessions/does-not-exist/messages")
    assert resp.status_code == 404


def test_sessions_are_scoped_to_their_own_farmer(client, monkeypatch):
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: "ok")
    _register_and_login(client, phone="+919000000003")
    _create_field(client)
    resp = _post_chat(client, message="farmer A's question")
    session_id = resp.get_json()["session_id"]

    from _otp_helpers import register_and_login

    other = register_and_login(client, "+919000000004")
    assert other.status_code == 200

    assert client.get("/v2/chat/sessions").get_json()["sessions"] == []
    assert client.get(f"/v2/chat/sessions/{session_id}/messages").status_code == 404
