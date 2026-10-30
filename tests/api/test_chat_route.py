"""Module 58: ``POST /v2/chat`` -- the floating chatbot assistant. The
OpenRouter/Groq text cascade boundary is mocked, same convention as
``test_voice_ask_route.py``: no live key, real SQLiteDataStore for
grounding/isolation checks.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.persistence.models import Advisory
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


def _seed_advisory(app, farmer_id: str, field_id: str) -> None:
    store = app.extensions["data_store"]
    advisory = Advisory(
        id="adv-1", field_id=field_id, created_at=_NOW, language="en",
        title="Irrigate soon", body="Apply 12mm within 3 days.", severity="moderate",
    )
    store.save_advisory(farmer_id, advisory)


def _post_chat(client, message="How is my field?", history=None, language="en"):
    return client.post(
        "/v2/chat",
        json={"message": message, "history": history or [], "language": language},
    )


def test_chat_requires_session(client):
    resp = _post_chat(client)
    assert resp.status_code == 401


def test_chat_success_returns_reply(client, monkeypatch):
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


def test_chat_llm_unavailable_returns_503(client, monkeypatch):
    _register_and_login(client)
    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", lambda messages: None)
    resp = _post_chat(client)
    assert resp.status_code == 503
    assert resp.get_json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_chat_empty_message_returns_400(client):
    _register_and_login(client)
    resp = _post_chat(client, message="   ")
    assert resp.status_code == 400


def test_chat_bad_history_shape_returns_400(client):
    _register_and_login(client)
    resp = client.post("/v2/chat", json={"message": "hi", "history": [{"role": "nope", "content": "x"}]})
    assert resp.status_code == 400


def test_chat_prompt_is_scoped_to_this_farmer_only(app, client, monkeypatch):
    """Same ADR 0003 ownership check as test_voice_ask_route's equivalent:
    the grounding context must never leak another farmer's data."""
    _register_and_login(client, phone="+919000000002")
    field_id = _create_field(client)
    farmer_id = list(app.extensions["data_store"]._conn.execute("SELECT id FROM farmers").fetchall())[0][0]
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


def test_chat_includes_history_in_messages(client, monkeypatch):
    _register_and_login(client)
    captured = {}

    def _fake_ask(messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr("agro_mirai.api.routes.chat_v2.ask_chat", _fake_ask)
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    resp = _post_chat(client, message="what next?", history=history)
    assert resp.status_code == 200
    messages = captured["messages"]
    assert messages[1] == {"role": "user", "content": "hi"}
    assert messages[2] == {"role": "assistant", "content": "hello"}
    assert messages[3] == {"role": "user", "content": "what next?"}
