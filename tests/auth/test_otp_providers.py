from __future__ import annotations

import pytest
import requests

from agro_mirai.auth.otp_providers import (
    LogOtpSender,
    OtpProviderConfigError,
    OtpSendError,
    SmsGatewaySender,
    TestOtpSender,
    build_otp_sender,
    build_otp_text,
    parse_test_numbers,
)


def test_log_provider_is_default_outside_production():
    sender, test_numbers = build_otp_sender({})
    assert isinstance(sender, LogOtpSender)
    assert test_numbers == {}


def test_log_provider_refuses_to_start_in_production():
    with pytest.raises(OtpProviderConfigError):
        build_otp_sender({"FLASK_ENV": "production"})


def test_test_provider_refuses_production_without_allow_flag():
    with pytest.raises(OtpProviderConfigError):
        build_otp_sender({"FLASK_ENV": "production", "OTP_PROVIDER": "test"})


def test_test_provider_allowed_in_production_with_explicit_flag():
    sender, test_numbers = build_otp_sender(
        {
            "FLASK_ENV": "production",
            "OTP_PROVIDER": "test",
            "ALLOW_TEST_OTP": "1",
            "OTP_TEST_NUMBERS": "+919000000001:123456",
        }
    )
    assert isinstance(sender, TestOtpSender)
    assert test_numbers == {"+919000000001": "123456"}


def test_test_provider_sender_sends_nothing():
    sender = TestOtpSender({"+919000000001": "123456"})
    # must not raise, must not touch any network -- pure no-op
    assert sender.send("+919000000001", "123456") is None


def test_sms_gateway_requires_credentials():
    with pytest.raises(OtpProviderConfigError):
        build_otp_sender({"OTP_PROVIDER": "sms_gateway"})


def test_sms_gateway_allowed_with_credentials():
    sender, _ = build_otp_sender(
        {"OTP_PROVIDER": "sms_gateway", "SMS_GATEWAY_USER": "u", "SMS_GATEWAY_PASS": "p"}
    )
    assert isinstance(sender, SmsGatewaySender)


def test_unknown_provider_is_rejected():
    with pytest.raises(OtpProviderConfigError):
        build_otp_sender({"OTP_PROVIDER": "twilio"})


def test_build_otp_text_is_localized_per_language():
    for lang in ("en", "hi", "kn", "te"):
        text = build_otp_text("123456", lang)
        assert "123456" in text
    # each language's template is actually distinct, not all falling back to English
    texts = {lang: build_otp_text("123456", lang) for lang in ("en", "hi", "kn", "te")}
    assert len(set(texts.values())) == 4


def test_build_otp_text_falls_back_to_english_for_unknown_lang():
    assert build_otp_text("123456", "fr") == build_otp_text("123456", "en")


def test_sms_gateway_sender_sends_requested_language(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200

    def fake_post(url, json, auth, timeout):
        captured["text"] = json["textMessage"]["text"]
        return _FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    sender = SmsGatewaySender(username="u", password="p")
    sender.send("+919000000001", "123456", lang="hi")
    assert "123456" in captured["text"]
    assert captured["text"] == build_otp_text("123456", "hi")


def test_parse_test_numbers():
    assert parse_test_numbers("+911111111111:123456, +912222222222:654321") == {
        "+911111111111": "123456",
        "+912222222222": "654321",
    }
    assert parse_test_numbers("") == {}
    assert parse_test_numbers("garbage-no-colon") == {}


class _FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_sms_gateway_sender_posts_expected_body(monkeypatch):
    captured = {}

    def fake_post(url, json, auth, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["auth"] = auth
        return _FakeResponse(200)

    monkeypatch.setattr(requests, "post", fake_post)

    sender = SmsGatewaySender(username="u", password="p")
    sender.send("+919000000001", "123456")

    assert captured["auth"] == ("u", "p")
    assert captured["json"]["phoneNumbers"] == ["+919000000001"]
    assert "123456" in captured["json"]["textMessage"]["text"]


def test_sms_gateway_sender_retries_once_then_raises(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json, auth, timeout):
        calls["n"] += 1
        raise requests.ConnectionError("boom")

    monkeypatch.setattr(requests, "post", fake_post)

    sender = SmsGatewaySender(username="u", password="p")
    with pytest.raises(OtpSendError):
        sender.send("+919000000001", "123456")
    assert calls["n"] == 2


def test_sms_gateway_sender_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(401))

    sender = SmsGatewaySender(username="u", password="p")
    with pytest.raises(OtpSendError):
        sender.send("+919000000001", "123456")


def test_sms_gateway_sender_succeeds_after_one_retry(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, json, auth, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("boom")
        return _FakeResponse(200)

    monkeypatch.setattr(requests, "post", fake_post)

    sender = SmsGatewaySender(username="u", password="p")
    sender.send("+919000000001", "123456")  # should not raise
    assert calls["n"] == 2
