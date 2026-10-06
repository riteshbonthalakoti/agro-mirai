"""Pluggable OTP delivery (Module 56).

``agro_mirai.auth.otp`` only ever generates and stores a code; this
module is the seam that decides what happens to it. One small
``OtpSender`` interface, three implementations, selected by
``OTP_PROVIDER``:

- ``log`` — writes the code to the server's own log output. Local dev
  only; ``build_otp_sender`` refuses to construct one in production
  (``FLASK_ENV=production``), so a misconfigured deploy fails loudly at
  startup instead of silently never sending an SMS.
- ``test`` — a short whitelist of phone numbers (``OTP_TEST_NUMBERS``)
  log in with a fixed code; no SMS is sent, nothing is logged. Allowed
  in production only with the explicit second flag ``ALLOW_TEST_OTP=1``
  (logged loudly at startup when that combination is active).
- ``sms_gateway`` — real SMS via the capcom6 SMS Gateway for Android
  (https://docs.sms-gate.app/), cloud mode: a spare Android phone with
  an Indian SIM runs the gateway app and relays texts sent through its
  cloud API. Free for a demo; carriers may throttle it and the phone
  must stay powered and online (see docs/SMS_OTP_SETUP.md). When
  ``SMS_APP_HASH`` is set, the mobile app's 11-char signature is appended
  to the message so Android's SMS Retriever API (``mobile/modules/sms-
  retriever``) auto-fills the code with no copy-paste at all.

Swapping in a paid provider later (2Factor, MSG91) means adding one
more ``OtpSender`` subclass and one more branch in ``build_otp_sender``
-- callers (``api/routes/auth_v2.py``) only ever see the interface.
"""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger("agro_mirai.auth.otp_providers")

_GATEWAY_URL = "https://api.sms-gate.app/3rdparty/v1/message"
_GATEWAY_TIMEOUT_S = 10.0

# One template per farmer-facing language (mobile/src/i18n.ts's four: en/kn/te/hi).
# {code} is substituted in; keep each under ~130 chars so the hash suffix
# (SMS_APP_HASH) still fits a single 160-char SMS segment.
_OTP_SMS_TEMPLATES = {
    "en": "{code} is your AGRO MIRAI login code. Valid for 5 minutes. Do not share this code with anyone.",
    "hi": "{code} आपका AGRO MIRAI लॉगिन कोड है। यह 5 मिनट तक मान्य है। इस कोड को किसी के साथ साझा न करें।",
    "kn": "{code} ಇದು ನಿಮ್ಮ AGRO MIRAI ಲಾಗಿನ್ ಕೋಡ್. ಇದು 5 ನಿಮಿಷಗಳವರೆಗೆ ಮಾನ್ಯವಾಗಿರುತ್ತದೆ. ಈ ಕೋಡ್ ಅನ್ನು ಯಾರೊಂದಿಗೂ ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.",
    "te": "{code} మీ AGRO MIRAI లాగిన్ కోడ్. ఇది 5 నిమిషాల వరకు చెల్లుతుంది. ఈ కోడ్‌ను ఎవరితోనూ పంచుకోవద్దు.",
}


def build_otp_text(code: str, lang: str) -> str:
    """The farmer-facing SMS body in their own preferred language --
    falls back to English for an unrecognized/missing lang rather than
    failing the send over a cosmetic mismatch."""
    template = _OTP_SMS_TEMPLATES.get(lang, _OTP_SMS_TEMPLATES["en"])
    return template.format(code=code)


class OtpSendError(Exception):
    """A provider could not deliver the code. Callers must show a
    generic failure to the user -- never surface this exception's
    message (which may name a host/status code) or the OTP itself in an
    API response."""


class OtpProviderConfigError(Exception):
    """OTP_PROVIDER is missing, unknown, or not allowed to start in this
    environment (e.g. ``log`` in production)."""


class OtpSender:
    def send(self, phone: str, code: str, lang: str = "en") -> None:
        raise NotImplementedError


class LogOtpSender(OtpSender):
    """Dev/demo only -- the original Module 27 behaviour. Never
    constructed in production (see ``build_otp_sender``)."""

    def send(self, phone: str, code: str, lang: str = "en") -> None:
        logger.info("OTP for %s: %s (valid 5 min, lang=%s)", phone, code, lang)


class TestOtpSender(OtpSender):
    """Fixed codes for a whitelist of demo/evaluator numbers. The fixed
    code is applied by the caller (``request_otp``, which looks the
    phone up in ``test_numbers`` before calling ``otp_store.issue``) --
    this sender's ``send`` is a deliberate no-op so a whitelisted
    number's code is never logged or transmitted anywhere."""

    def __init__(self, test_numbers: dict[str, str]):
        self.test_numbers = test_numbers

    def send(self, phone: str, code: str, lang: str = "en") -> None:
        return None


class SmsGatewaySender(OtpSender):
    """capcom6 SMS Gateway for Android, cloud mode. POSTs to the
    gateway's hosted API, which relays the message to whichever
    Android phone is signed in with these credentials over its own
    channel (not a direct connection to the phone)."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = _GATEWAY_URL,
        timeout_s: float = _GATEWAY_TIMEOUT_S,
        app_hash: str | None = None,
    ):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout_s = timeout_s
        # Module 56: the Android app's 11-char SMS Retriever signature
        # (SMS_APP_HASH, read from the mobile app's own
        # SmsRetriever.getAppSignatures() -- see modules/sms-retriever).
        # Must be the LAST thing in the message, preceded by a space, or
        # the OS never delivers the SMS to the app's listener; purely
        # cosmetic to a human reading the text, so always safe to append.
        self.app_hash = app_hash

    def send(self, phone: str, code: str, lang: str = "en") -> None:
        text = build_otp_text(code, lang)
        if self.app_hash:
            text = f"{text}\n{self.app_hash}"
        last_error: Exception | None = None
        for _attempt in range(2):  # one retry
            try:
                resp = requests.post(
                    self.base_url,
                    json={"textMessage": {"text": text}, "phoneNumbers": [phone]},
                    auth=(self.username, self.password),
                    timeout=self.timeout_s,
                )
            except requests.RequestException as e:
                last_error = e
                continue
            if resp.status_code >= 400:
                last_error = OtpSendError(f"gateway returned HTTP {resp.status_code}")
                continue
            return
        logger.warning("sms_gateway send failed for %s: %s", _mask_phone(phone), last_error)
        raise OtpSendError("sms gateway send failed") from last_error


def _mask_phone(phone: str) -> str:
    """Never log a full phone number (demo privacy requirement) -- keep
    only enough to tell pending codes apart in a log line."""
    return f"***{phone[-4:]}" if len(phone) >= 4 else "***"


def parse_test_numbers(raw: str) -> dict[str, str]:
    """``OTP_TEST_NUMBERS=+91xxxxxxxxxx:123456,+91yyyyyyyyyy:654321``."""
    out: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        phone, _, code = pair.partition(":")
        phone, code = phone.strip(), code.strip()
        if phone and code:
            out[phone] = code
    return out


def build_otp_sender(env: "os._Environ[str] | dict[str, str] | None" = None) -> tuple[OtpSender, dict[str, str]]:
    """Reads ``OTP_PROVIDER`` (and its provider-specific vars) and
    returns ``(sender, test_numbers)`` -- ``test_numbers`` is the
    phone->fixed-code map, empty unless ``provider == "test"``.

    Raises ``OtpProviderConfigError`` instead of starting with a
    provider this environment forbids -- a clean startup failure, not a
    silently-never-sends-SMS production deploy.
    """
    env = os.environ if env is None else env
    provider = env.get("OTP_PROVIDER", "log")
    is_production = env.get("FLASK_ENV") == "production"

    if provider == "log":
        if is_production:
            raise OtpProviderConfigError(
                "OTP_PROVIDER=log cannot run in production -- no SMS is ever sent"
            )
        return LogOtpSender(), {}

    if provider == "test":
        if is_production and env.get("ALLOW_TEST_OTP") != "1":
            raise OtpProviderConfigError(
                "OTP_PROVIDER=test in production requires ALLOW_TEST_OTP=1"
            )
        test_numbers = parse_test_numbers(env.get("OTP_TEST_NUMBERS", ""))
        if is_production:
            logger.warning(
                "ALLOW_TEST_OTP=1: OTP_PROVIDER=test is active in production -- "
                "%d whitelisted number(s) log in with a fixed code, no SMS is sent",
                len(test_numbers),
            )
        return TestOtpSender(test_numbers), test_numbers

    if provider == "sms_gateway":
        username = env.get("SMS_GATEWAY_USER")
        password = env.get("SMS_GATEWAY_PASS")
        if not username or not password:
            raise OtpProviderConfigError(
                "OTP_PROVIDER=sms_gateway requires SMS_GATEWAY_USER and SMS_GATEWAY_PASS"
            )
        return (
            SmsGatewaySender(username=username, password=password, app_hash=env.get("SMS_APP_HASH")),
            {},
        )

    raise OtpProviderConfigError(f"unknown OTP_PROVIDER: {provider!r}")
