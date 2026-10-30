"""Text chat cascade (``text_chat_client.py``): OpenRouter primary, Groq
fallback for the floating chat assistant (Module 58). The HTTP boundary
(``requests.post``) is mocked, no live key or quota is used -- same
convention as ``test_gemini_cascade.py`` / the vision cascade.
"""
from unittest.mock import MagicMock

import pytest
import requests

from agro_mirai.api import text_chat_client as chat


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_CHAT_API_KEY_1", "ork1")
    monkeypatch.setenv("GROQ_CHAT_API_KEY_1", "gqk1")
    chat._openrouter_pool = chat.KeyPool("openrouter_chat", "OPENROUTER_CHAT_API_KEY", max_keys=3)
    chat._groq_pool = chat.KeyPool("groq_chat", "GROQ_CHAT_API_KEY", max_keys=3)


def _patch_post(monkeypatch, *responses):
    calls = []
    queue = list(responses)

    def fake(url, **kw):
        calls.append((url, kw))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(chat.requests, "post", fake)
    return calls


def test_no_keys_returns_none_no_network(monkeypatch):
    for i in range(1, 4):
        monkeypatch.delenv(f"OPENROUTER_CHAT_API_KEY_{i}", raising=False)
        monkeypatch.delenv(f"GROQ_CHAT_API_KEY_{i}", raising=False)
    chat._openrouter_pool = chat.KeyPool("openrouter_chat", "OPENROUTER_CHAT_API_KEY", max_keys=3)
    chat._groq_pool = chat.KeyPool("groq_chat", "GROQ_CHAT_API_KEY", max_keys=3)
    calls = _patch_post(monkeypatch)
    assert chat.ask_chat([{"role": "user", "content": "hi"}]) is None
    assert calls == []


def test_openrouter_returns_text(keys, monkeypatch):
    body = {"choices": [{"message": {"content": "water your field tomorrow"}}]}
    calls = _patch_post(monkeypatch, _resp(body=body))
    result = chat.ask_chat([{"role": "user", "content": "when to water?"}])
    assert result == "water your field tomorrow"
    url, kw = calls[0]
    assert url == chat._OPENROUTER_URL
    assert kw["headers"]["Authorization"] == "Bearer ork1"


def test_429_falls_through_to_groq(keys, monkeypatch):
    body = {"choices": [{"message": {"content": "from groq"}}]}
    calls = _patch_post(monkeypatch, _resp(status=429), _resp(body=body))
    result = chat.ask_chat([{"role": "user", "content": "hi"}])
    assert result == "from groq"
    assert len(calls) == 2
    assert calls[1][0] == chat._GROQ_URL


def test_network_error_on_both_providers_returns_none(keys, monkeypatch):
    _patch_post(monkeypatch, requests.ConnectionError("boom"), requests.ConnectionError("boom"))
    assert chat.ask_chat([{"role": "user", "content": "hi"}]) is None


def test_extract_chart_block_parses_valid_chart():
    reply = (
        'Your yield rose steadily this season.\n'
        '{"chart": {"type": "line", "title": "Yield", "labels": ["Jun", "Jul"], "values": [1.2, 1.8]}}\n'
        'Keep up the current irrigation schedule.'
    )
    text, chart = chat.extract_chart_block(reply)
    assert "yield rose steadily" in text.lower()
    assert "Keep up the current irrigation" in text
    assert chart == {"type": "line", "title": "Yield", "labels": ["Jun", "Jul"], "values": [1.2, 1.8]}


def test_extract_chart_block_no_chart_present():
    text, chart = chat.extract_chart_block("Just a plain answer, no chart needed.")
    assert text == "Just a plain answer, no chart needed."
    assert chart is None


def test_extract_chart_block_malformed_json_falls_back_to_plain_text():
    reply = 'Here is some info. {"chart": {"type": "bar", "labels": ["a"]}} more text'
    text, chart = chat.extract_chart_block(reply)
    assert chart is None
    assert "Here is some info" in text


class _FakeField:
    def __init__(self, id, name, current_crop):
        self.id, self.name, self.current_crop = id, name, current_crop


class _FakeAdvisory:
    def __init__(self, body):
        self.body = body


def test_rule_based_fallback_no_fields():
    store = MagicMock()
    store.list_fields.return_value = []
    assert "don't have any fields" in chat.rule_based_fallback_reply(store, "f1", "hi", "en")


def test_rule_based_fallback_uses_latest_advisory():
    store = MagicMock()
    store.list_fields.return_value = [_FakeField("fld-1", "North Plot", "cotton")]
    store.list_advisories_for_field.return_value = [_FakeAdvisory("Apply 12mm within 3 days.")]
    reply = chat.rule_based_fallback_reply(store, "f1", "how is my field?", "en")
    assert "North Plot" in reply
    assert "12mm" in reply


def test_rule_based_fallback_no_advisory_yet():
    store = MagicMock()
    store.list_fields.return_value = [_FakeField("fld-1", "North Plot", "cotton")]
    store.list_advisories_for_field.return_value = []
    reply = chat.rule_based_fallback_reply(store, "f1", "how is my field?", "en")
    assert "North Plot" in reply
    assert "don't have a recent advisory" in reply


def test_rule_based_fallback_picks_field_named_in_message():
    store = MagicMock()
    store.list_fields.return_value = [
        _FakeField("fld-1", "North Plot", "cotton"),
        _FakeField("fld-2", "South Plot", "rice"),
    ]
    store.list_advisories_for_field.side_effect = lambda farmer_id, field_id, limit: (
        [_FakeAdvisory("Rice advisory body")] if field_id == "fld-2" else [_FakeAdvisory("Cotton advisory body")]
    )
    reply = chat.rule_based_fallback_reply(store, "f1", "how is my South Plot doing?", "en")
    assert "South Plot" in reply
    assert "Rice advisory body" in reply
