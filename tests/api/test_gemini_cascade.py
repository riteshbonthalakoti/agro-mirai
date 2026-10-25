"""Gemini cascade additions (``ask_gemini_vision``/``ask_gemini_structured``):
the HTTP boundary (``requests.post``) is mocked, no live Gemini key or quota
is used. ``ask_gemini`` itself (the existing voice-feature path) is untouched
by this restructure and already has no test coverage of its own, left as-is."""
from unittest.mock import MagicMock

import pytest
import requests

from agro_mirai.api import gemini_client as gemini


def _resp(status=200, body=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = text
    return r


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY_1", "k1")
    monkeypatch.setenv("GEMINI_API_KEY_2", "k2")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gemini._pool = gemini.KeyPool("gemini", "GEMINI_API_KEY", max_keys=9)
    return gemini._pool


def _patch_post(monkeypatch, *responses):
    calls = []
    queue = list(responses)

    def fake(url, **kw):
        calls.append((url, kw))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(gemini.requests, "post", fake)
    return calls


def test_no_keys_returns_none_no_network(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for i in range(1, 10):
        monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
    gemini._pool = gemini.KeyPool("gemini", "GEMINI_API_KEY", max_keys=9)
    calls = _patch_post(monkeypatch)
    assert gemini.ask_gemini_vision(b"img", "what disease?") is None
    assert gemini.ask_gemini_structured("recommend a crop") is None
    assert calls == []


def test_vision_returns_text(keys, monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "leaf blight, high confidence"}]}}]}
    calls = _patch_post(monkeypatch, _resp(body=body))
    assert gemini.ask_gemini_vision(b"img-bytes", "diagnose this leaf") == "leaf blight, high confidence"
    _url, kw = calls[0]
    assert kw["headers"]["X-goog-api-key"] == "k1"
    parts = kw["json"]["contents"][0]["parts"]
    assert parts[0]["text"] == "diagnose this leaf"
    assert parts[1]["inline_data"]["mime_type"] == "image/jpeg"


def test_structured_parses_json(keys, monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": '{"crop": "cotton", "confidence": 0.7}'}]}}]}
    _patch_post(monkeypatch, _resp(body=body))
    result = gemini.ask_gemini_structured("recommend a crop")
    assert result == {"crop": "cotton", "confidence": 0.7}


def test_structured_non_json_returns_none(keys, monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "not json at all"}]}}]}
    _patch_post(monkeypatch, _resp(body=body))
    assert gemini.ask_gemini_structured("recommend a crop") is None


def test_429_falls_through_to_next_key(keys, monkeypatch):
    body = {"candidates": [{"content": {"parts": [{"text": "ok from k2"}]}}]}
    calls = _patch_post(monkeypatch, _resp(status=429), _resp(body=body))
    assert gemini.ask_gemini_vision(b"img", "diagnose") == "ok from k2"
    assert len(calls) == 2
    assert calls[0][1]["headers"]["X-goog-api-key"] == "k1"
    assert calls[1][1]["headers"]["X-goog-api-key"] == "k2"


def test_all_keys_rate_limited_returns_none(keys, monkeypatch):
    _patch_post(monkeypatch, _resp(status=429), _resp(status=429))
    assert gemini.ask_gemini_structured("recommend a crop") is None


def test_network_error_returns_none(keys, monkeypatch):
    _patch_post(monkeypatch, requests.ConnectionError("boom"))
    assert gemini.ask_gemini_vision(b"img", "diagnose") is None


def test_falls_back_to_single_legacy_key_when_no_pool(monkeypatch):
    for i in range(1, 10):
        monkeypatch.delenv(f"GEMINI_API_KEY_{i}", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "legacy-key")
    gemini._pool = gemini.KeyPool("gemini", "GEMINI_API_KEY", max_keys=9)
    body = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    calls = _patch_post(monkeypatch, _resp(body=body))
    assert gemini.ask_gemini_vision(b"img", "diagnose") == "ok"
    assert calls[0][1]["headers"]["X-goog-api-key"] == "legacy-key"
