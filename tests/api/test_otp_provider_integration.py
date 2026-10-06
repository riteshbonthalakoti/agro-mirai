"""Module 56: OTP_PROVIDER wired all the way through create_app() and
POST /v2/auth/request-otp -- the `test` provider's fixed-code whitelist,
a real send failure turning into a clean error (no OTP leak), and the
production start-up guard."""
from __future__ import annotations

import pytest

from agro_mirai.api.app import create_app
from agro_mirai.auth.otp_providers import OtpProviderConfigError
from agro_mirai.persistence.sqlite_store import SQLiteDataStore


def _app(**env):
    store = SQLiteDataStore(":memory:")
    return create_app(
        {"TESTING": True, "DATA_STORE": store, "API_KEY": "x", "FARMER_ID": "y", **env}
    )


def test_production_refuses_log_provider(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("OTP_PROVIDER", raising=False)
    with pytest.raises(OtpProviderConfigError):
        create_app({"DATA_STORE": SQLiteDataStore(":memory:")})


def test_test_provider_whitelisted_number_logs_in_with_fixed_code(monkeypatch):
    monkeypatch.setenv("OTP_PROVIDER", "test")
    monkeypatch.setenv("OTP_TEST_NUMBERS", "+919000000099:555555")

    app = _app()
    client = app.test_client()

    resp = client.post(
        "/v2/auth/request-otp",
        json={"phone": "+919000000099", "name": "Demo", "preferred_language": "en"},
    )
    assert resp.status_code == 200

    verify = client.post(
        "/v2/auth/verify-otp", json={"phone": "+919000000099", "otp": "555555"}
    )
    assert verify.status_code == 200


def test_sms_gateway_send_failure_returns_clean_error_without_leaking_otp(monkeypatch):
    import agro_mirai.auth.otp_providers as providers

    monkeypatch.setenv("OTP_PROVIDER", "sms_gateway")
    monkeypatch.setenv("SMS_GATEWAY_USER", "u")
    monkeypatch.setenv("SMS_GATEWAY_PASS", "p")

    class _AlwaysFailsSender(providers.OtpSender):
        def send(self, phone, code, lang="en"):
            raise providers.OtpSendError("gateway down")

    app = _app()
    app.extensions["otp_sender"] = _AlwaysFailsSender()
    client = app.test_client()

    resp = client.post(
        "/v2/auth/request-otp",
        json={"phone": "+919000000098", "name": "Demo", "preferred_language": "en"},
    )
    assert resp.status_code == 502
    body = resp.get_json()
    assert body["error"]["code"] == "OTP_SEND_FAILED"
    assert "gateway down" not in str(body)  # the real failure reason never leaks to the client
