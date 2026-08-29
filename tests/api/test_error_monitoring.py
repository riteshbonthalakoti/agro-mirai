"""Sentry wiring: a no-op with no SENTRY_DSN configured (never crashes
without one), initialized with enough context to debug from the
dashboard when a DSN is present.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from conftest import API_KEY, FARMER_ID, _mock_store

import agro_mirai.api.app as app_module


def _make_app(config_extra: dict):
    return app_module.create_app(
        {
            "API_KEY": API_KEY,
            "FARMER_ID": FARMER_ID,
            "TESTING": True,
            "DATA_STORE": _mock_store(),
            **config_extra,
        }
    )


def test_no_dsn_configured_does_not_call_sentry_init(monkeypatch):
    init_mock = MagicMock()
    monkeypatch.setattr(app_module.sentry_sdk, "init", init_mock)

    application = _make_app({"SENTRY_DSN": ""})

    init_mock.assert_not_called()
    assert application is not None


def test_no_dsn_configured_app_runs_fine(monkeypatch):
    init_mock = MagicMock()
    monkeypatch.setattr(app_module.sentry_sdk, "init", init_mock)

    application = _make_app({"SENTRY_DSN": ""})
    client = application.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200


def test_dsn_configured_initializes_sentry_with_flask_integration(monkeypatch):
    init_mock = MagicMock()
    monkeypatch.setattr(app_module.sentry_sdk, "init", init_mock)

    _make_app({"SENTRY_DSN": "https://example@o0.ingest.sentry.io/1"})

    init_mock.assert_called_once()
    _, kwargs = init_mock.call_args
    assert kwargs["dsn"] == "https://example@o0.ingest.sentry.io/1"
    assert any(
        type(i).__name__ == "FlaskIntegration" for i in kwargs.get("integrations", [])
    )


def test_dsn_configured_tags_requests_with_request_id(monkeypatch):
    init_mock = MagicMock()
    monkeypatch.setattr(app_module.sentry_sdk, "init", init_mock)
    set_tag_mock = MagicMock()
    monkeypatch.setattr(app_module.sentry_sdk, "set_tag", set_tag_mock)

    application = _make_app({"SENTRY_DSN": "https://example@o0.ingest.sentry.io/1"})
    client = application.test_client()
    client.get("/health")

    tagged_keys = {call.args[0] for call in set_tag_mock.call_args_list}
    assert "request_id" in tagged_keys
    assert "route" in tagged_keys
